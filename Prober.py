#!/usr/bin/python
"""   
    This file is subject to the terms and conditions of the GNU General
    Public License. See the file COPYING in the main directory of this
    archive for more details.

"""


import time
import socket
import re
from datetime import datetime
from time import sleep
from subprocess import Popen, PIPE
from random import randrange, shuffle, Random

from ResultSet import *


class Prober:
    ResultValid = 0  #store valid measurement (e.g. ICMP // time exceeded)
    ResultValidLasthop = 2   #store valid measurement, this is last hop (e.g. ICMP port unreachable)
    ResultFiltered = 3   #packets filtered, give up (e.g.ICMP prohibited)
    ResultTimeout = 4    #Timeout
    ResultAbort = 255 # huh?  we haven't a clue

    def __init__(self, resultset):
        
        self.resultset = resultset
        
        # Default config values
        self.gap = 0.25
        self.maxHops = 30
        self.increment = 32
        self.mtu = 1500
        self.numericFlag = False
        self.timeout = 3
        self.verboseLevel = 1
        self.targetHost = ""
        self.maxHopReps = 20
        self.discoveryIterations = 1

        # Internal variables
        self.aCumulativeLast = 0.0
        self.bCumulativeLast = 0.0
        self.packetsLost = 0
        self.packetsSent = 0
        self.hopsRequired = 0
        self.hopAddresses = []


    #
    # start
    #
    # Input:  None
    #
    # Output:  None.
    #
    # Start probing using the set parameters
    # Figgers out if data for all hops is converged. If not, it starts
    # a full test to converge to the minimum observed values. 
    # Otherwise a limited test to estimate current queue delay.
    #
    def start (self):
        hoplist = self.hoplist()
        self.hopsRequired = len(hoplist)
        self.resultset.updateHoplist(hoplist)

        # if we're not fully converged, we should to a complete 
        # probe to converge.
    #    if not self.resultset.fullyConverged():
    #        print "Doing full probe"
    #        self.__fullProbe()
        
        print "checking queuedelay"
        # gather data to estimate the current queuedelay
        self.__queueCheck()

    #
    # Sends probes to each hop according to the set parameters.
    # Continues until data for each hop is converged or until
    # the configured maximum.
    #
    def __fullProbe (self):
        # Generate set of packet sizes to test.  We'll test packets
        # from Increment to the maximum multiple of Increment that
        # that will still fit in Mtu bytes.  We weakly randomize
        # the packet sizes (we just don't want a sequence of
        # packet sizes that is *too* predictable).
        #
        # Note that if increment is small (in particular, if it's
        # smaller than a UDP/IP header), the protocol-specific code
        # will refuse to generate packets smaller than the minimum
        # possible.
        packetSize = range(50,self.mtu,self.increment)
        shuffle(packetSize)

        if self.verboseLevel > 0:
            print "Starting buffchar to {0}".format(self.targetHost)
            print "Packet size increments from minimum to {0} by {1}".format(self.mtu,self.increment) 
        


        # ICMP packets to figure out the source address.  But now we
        # have that information up-front.
        if self.verboseLevel > 0:
            print "00: OriginHost"
        

        # Initilize some values and start testing
        roundTimeStamp = time.time()

        for i in range (1,self.hopsRequired+1):
            self.hopAddresses = []
            self.packetsSent = 0
            self.packetsLost = 0

            resultsGood = False
            hopRep = 0
            while not resultsGood:
                for k in range (len(packetSize)):

                    output = Popen (["traceroute", "-n", "-f", str (i), "-m", str (i), "-q", "1", self.targetHost], stdout=PIPE).communicate()[0]
                    self.packetsSent += 1

                    #if status > 0:
                    #    raise Exception ("Traceroute failed, you must be root to do TCP traceroute",command)

                    traceroute = output.splitlines()[1].split()

                    # If the packet timed out
                    if len (traceroute) < 3:
                        result = self.ResultTimeout
                        tracerouteRTT = self.timeout
                        self.packetsLost += 1
                        continue

                    # interperating the stuff we got back from traceroute
                    tracerouteHop = traceroute[0].strip() 
                    tracerouteIP  = traceroute[1].strip().lstrip("(").rstrip(")")
                    tracerouteRTT = traceroute[2].strip() # this is still a string, not a float

                    # if the response time is a valid number
                    if re.match("\d*\.\d*", tracerouteRTT):
                        tracerouteRTT = float (tracerouteRTT) / 1000.0
                        self.resultset.add(i, packetSize[k], float (tracerouteRTT), roundTimeStamp)

                    if self.verboseLevel > 2:
                        print "bytes={0}, rtt={1}, ip_src={2}".format(
                                packetSize[k],
                                tracerouteRTT,
                                tracerouteIP)
                    
                    if not tracerouteIP in self.hopAddresses:
                            self.hopAddresses.append(tracerouteIP)




                hopRep += 1
                if (hopRep%2) == 0:
                    # checking with our adaptive probing magic whether we should probe more
                    resultsGood = self.resultset.isGood(i)

                #
                # We do not want to go on forever to converge, so we stop even 
                # without convergin if we reach this counter
                #
                if (self.maxHopReps < hopRep):
                    resultsGood = True
            
            self.endreps(i)

        # wrapping up 
        self.resultset.printEndOfRun(i)    

    def endreps(self,i):
        
        # Get cumulative delay and bandwidth
        aCumulative, bCumulative = self.resultset.slr(i)

        # Figure the per-hop delay and bandwidth. This computation's
        # correctness relies on aCumulativeLast and bCumulativeLast
        # being initialized to 0.0.
        if (aCumulative > 0.0):
            aHop = aCumulative - self.aCumulativeLast
            bHop = bCumulative - self.bCumulativeLast
        else:
            aHop = 0.0
            bHop = 0.0
        
        # Update our idea of the minimum bandwidth found so far.
        # Clearly we only take into account hop bandwidths that
        # make some sense (positive).
        hopBandwidth = 0.0
        if (bHop != 0.0):
            hopBandwidth = (1.0/bHop) * 8.0 / 1000.0
        else:
            hopBandwidth = 0.0

        # Per-hop output
        if self.verboseLevel > 0:
            print "    Partial loss:      {0:d} / {1:d} ({2:d}%)".format(
                    self.packetsLost, 
                    self.resultset.getCount(i), 
                    (self.packetsLost*100/self.packetsSent))

            print "    Partial char:      rtt = {0:f} ms, (b = {1:f} ms/B)".format(
                    aCumulative*1000.0,
                    bCumulative*1000.0)

            string = "    Hop char:          rtt = "
            if (aHop >= 0.0):
                string += "{0:f}".format(aHop*1000.0)
            else:
                string += "--.---"
            string += " ms, bw = "
            if (hopBandwidth >= 0.0):
                string += "{0:f}".format(hopBandwidth)
            else:
                string += "--.---"
            string += " Kbps"

            print string
        

        if len (self.hopAddresses) > 0:
            for m in self.hopAddresses:
                host = ""
                if not self.numericFlag:
                    #host = "("+socket.gethostbyaddr(m)[0]+")"
                    host = ""
                
                print "{0:2d}: {1} {2}".format(i,m,host)
        else:
            print "{0:2d}: no probe responses".format(i)

        # Update inter-hop state
        self.aCumulativeLast = aCumulative
        self.bCumulativeLast = bCumulative

    def showStats(self):
        for hop in self.resultset.data:
            for size in self.resultset.data[hop]:
                self.packetsSent += len (self.resultset.data[hop][size])
            self.endreps(hop)
        self.endOfRun(hop)
    

    def __queueCheck (self):
        """This method runs over each hop in a route and checks the latency 
        of all hops"""
        
        print "Going for a quick run using one packetsize, to check the queue delay"
        
        roundTimeStamp = time.time()

        for packetCount in range (self.maxHopReps):
            sleep (0.5)
            for hop in range (1,self.hopsRequired+1):
                output = Popen (["traceroute", "-n", "-q", "1", "-T", "-f", str (hop), "-m", str (hop), self.targetHost, "1042"], stdout=PIPE).communicate()[0]
                print output

                for line in output.splitlines()[1:]:
                    
                    traceroute = line.split()
                    self.packetsSent += 1
                    # If the packet timed out
                    if len (traceroute) < 3:
                        self.packetsLost += 1
                        continue

                    # interperating the stuff we got back from traceroute
                    tracerouteHop = traceroute[0].strip() 
                    tracerouteIP  = traceroute[1].strip().lstrip("(").rstrip(")")
                    tracerouteRTT = traceroute[2].strip() # this is still a string, not a float
                    
                    tracerouteRTT = float (tracerouteRTT) / 1000.0        
                    self.resultset.add (tracerouteHop, 1098, tracerouteRTT, roundTimeStamp)
        
        print "Queuecheck done"
        print "Send {0} packets, lost {1}".format(self.packetsSent,self.packetsLost)



    # returns the amount of hops needed to reach targethost
    def hoplist(self):
        #status, output = commands.getstatusoutput ("traceroute -n -q 1 {0}".format (self.targetHost))
        output = Popen (["traceroute", "-n", "-q", "1", "-m", str(self.maxHops), self.targetHost], stdout=PIPE).communicate()[0]
        print "maxHops",self.maxHops
	hoplist = []
        for line in output.splitlines()[1:]:
            line = line.split()
            #if the packet timed out
            if len(line) < 3:
                hoplist.append("Timeout")
                continue
            
            hoplist.append(line[1].strip())
            
        # We're doing TCP probes, so skip the last hop.
        # Last hop = targetHost and won't respond to tcp packets
        hoplist.pop()
        
        return hoplist
