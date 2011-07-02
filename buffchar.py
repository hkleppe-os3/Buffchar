#!/usr/bin/python
"""   
    This file is subject to the terms and conditions of the GNU General
    Public License. See the file COPYING in the main directory of this
    archive for more details.

"""

import time
import pickle
from socket import gethostname
from datetime import datetime

from Prober import *
from Plotter import *
from ResultSet import *

verboseFlag = 1
resultset = None
prober = None
dbHost = ""
dbUser = ""
dbPass = ""


def VersionInfo():
    print "dunno which version"



"""
 Usage

 Input:  program name (argv0)

 Output:  None

 Print out invocation information
"""
def main():
    import getopt
    import sys
    import time
    
    global verboseFlag
    global prober
    global resultset
    
    plotCharts = False
    dbIsConnected = False
    plotting = False
    dbName = ""

    resultset = ResultSet()
    prober = Prober(resultset)

    c = 0           # getopt
    # Parse command-line arguments using getopt
    optlist,args = getopt.getopt(sys.argv[1:], "d:h:H:pR:t:v:V")

    for c, optarg in optlist:
        # connecting to a specific DB
        if c == "-d":
            dbName = optarg
        # Check for the different command-line flags we accept
        # Targethost
        elif c == "-h":
            if not optarg:
                print "error: you have to specify the hostname or ip address"
            else:
                prober.targetHost = optarg
        # H: Maximum hops
        elif c == "-H": 
            prober.maxHops = int (optarg)
            if prober.maxHops > 255: 
                print "Warning: Maximum hops " + prober.hops + " too large, resetting to 30"
                prober.maxHops = 30
        # p: create plots and results
        elif c == "-p":
            plotting = True
        # R: Repetitions per hop
        elif c == "-R": 
            prober.maxHopReps = int(optarg)
        # t: ICMP timeout
        elif c == "-t": 
            prober.timeout = int(optarg)
            if prober.timeout < 1:
                print "Warning: timeout value %d too small, resetting to 1"
                prober.timeout = 1
        # v: verbose
        elif c == "-v": 
            resultset.verboseLevel = int (optarg)
            prober.verboseLevel = int(optarg)
        # V: version information
        elif c == "-V": 
            VersionInfo()
            sys.exit(0)
        else:
            print c + ": "+optarg
            print "Received unknown flag. Might also be that we have accidentially removed or chosen not to implement what you want. sorry"
            sys.exit(1)
    
    if dbName:
        resultset.dbConnect (dbHost,dbUser,dbPass,dbName )
    else:
        resultset.dbConnect (dbHost,dbUser,dbPass,"bufferbloat_" + gethostname())


    # Starting to probe if a targetHost is given
    if prober.targetHost:
        prober.start()
        resultset.dbCommit()
        resultset.dbClose()
    else:
        print "not probing, no host given"

    if plotting:
        print "Creating output for", dbName
        p = Plotter(dbHost,dbUser,dbPass,dbName)
        p.bufferbloatScore()
        p.queueData()
        p.rttHistogram (p.numberOfHops, p.totalRtt, filename=dbName)
        commands.getstatusoutput('gnuplot ./buffchar-output/rttHistogram.gnu')
    
    sys.exit(0)

if __name__ == "__main__":
    main()
