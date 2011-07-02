"""   
    This file is subject to the terms and conditions of the GNU General
    Public License. See the file COPYING in the main directory of this
    archive for more details.

"""

import MySQLdb
import commands
import os

from time import ctime

from ResultSet import *

class Plotter:
    def __init__(self, dbHost,dbUser,dbPass,dbName):
        self.dbName = dbName
        self.resultSet = ResultSet()
        self.conn = MySQLdb.connect( 
            host=dbHost,
            user=dbUser,
            passwd=dbPass,
            db=dbName)

        self.path = "./buffchar-output/" # path to the folder where stuff should be saved
        if not os.path.exists(self.path):
                os.makedirs(self.path)
        self.totalRtt = 0

    def timestamps (self):
        c.execute ("SELECT DISTINCT timestamp FROM data ORDER by timestamp")

        for timestamp in c.fetchall():
            toTime = float (timestamp[0])
            ts = ctime(toTime)

            print ts
    
    def bufferbloatScore (self):
        c = self.conn.cursor()
        good = 0.025
    
        c.execute ("SELECT hop, MIN(rtt) FROM data GROUP BY hop ORDER BY hop DESC LIMIT 1")
        a = c.fetchone()
        lastHop = a[0]
        minRTT = a[1]

        c.execute ("SELECT time, COUNT(*) FROM data where hop=%s GROUP BY time ORDER BY time DESC LIMIT 40",(lastHop,))
        
        times = c.fetchall()
        totalTimes = len(times)
        grade = 0.0
        for time in times:
            k = math.floor((time[1]-1)/2)
            
            c.execute ("SELECT rtt FROM data WHERE hop=%s AND time=%s ORDER BY rtt LIMIT %s,1",(lastHop,time[0],k))

            median = c.fetchone()[0]-minRTT
            grade += (1/float(totalTimes)) * ((median/good) *1.75)
        
        
        if grade > 10:
            #grade = "10+"
            pass
        else:
            grade = "{0:.2f}".format(grade)
        print "Bufferbloat score:",grade

    
    def queueData(self, numIntervals=False):
        """Generates data and gnuplot files for the line diagram with queue delays"""
        print "queueData..."
        c = self.conn.cursor ()
        datafile = open (self.path+"queuedelay.data", "w")

        # this list will contain:
        # times [timestamps] [hops] [datapoints in the hop]
        times = {}
        

        # Fetching the minimum RTTs
        minRTTs = []
        c.execute ("SELECT hop, MIN(rtt) FROM data GROUP BY hop ORDER BY hop")
        hop = 0
        for h in c.fetchall():
            while hop+1 < h[0]:
                minRTTs.append (0)
                hop +=1
            minRTTs.append (h[1])
            hop +=1
        
        totalRtt = minRTTs[-1]
        self.totalRtt = totalRtt
        
        numberOfHops = len(minRTTs)
        self.numberOfHops = numberOfHops 
        
        # writing header line to the datafile
        datafile.write("minute timestamp \"Min path\" ")
        for i in range (numberOfHops):
            datafile.write ("\"Link "+ str (i+1)+"\" ")
        datafile.write ("\n")


        timestamps = []
        c.execute ("SELECT MIN(time), MAX(time) FROM data")
        minimum, maximum = c.fetchone()
        minimum = int ( float (minimum)) -1 
        maximum = int (float (maximum)) +1

        # fetching every timestamp
        c.execute("SELECT time, COUNT(*) FROM data GROUP BY time ORDER BY time DESC LIMIT 40")
        for t in c.fetchall():
            timestamps.insert (0,t[0])


        previousTime = 0
        for timestamp in timestamps:

            # for each timestamp, getting every datapoint
            c.execute ("SELECT hop, rtt, packetsize FROM data WHERE time BETWEEN %s AND %s", (previousTime,timestamp))

            
            if not times.has_key(timestamp):
                times[timestamp] = {}

            # for each datapoint, calculate queue delay and save in a list
            for hop in c.fetchall():
                hopNr = hop[0] # first hop = 1
                rtt = hop[1]
                packetsize = hop[2]
                queueDelay = rtt - minRTTs[hopNr-1]

                if queueDelay >= 0: #filter out negative values
                    if not times[timestamp].has_key(hopNr):
                        times[timestamp][hopNr] = [queueDelay]
                    else:
                        times[timestamp][hopNr].append(queueDelay)
            previousTime = timestamp

        #
        # Looping the list and making sense of it
        # 
        keylist = times.keys()
        numberOfTimes = len (keylist)
        keylist.sort()
        hopsOnTimestamp = 0
        firstTime = float (keylist[0])
        counter = 0
        xticCounter = 0
        for time in keylist:

            # The counter is an integer which represents the number of 
            # minutes since the start. 
            #
            # We find the number of minutes from the start to this 
            # datapoint by substracting the first timestamp from the 
            # current timestamp, where we add one second to compensate 
            # for the lack of floating  point number accuracy.
            counter = int (math.floor ((float (time)+1 - firstTime) / 60))


            # This is a hack since gnuplot cannot simply plot time as
            # x tics in a histogram. so we write the xtic labels we want
            # to the file manually
            if counter % 10 == 0:
                toTime = float (time)
                ts = ctime(toTime).split()

                # printing only month, day, hh:mm
                ts = "{0} {1} {2}".format (ts[1], ts[2], ts[3].rsplit(":",1)[0])

                #ts = counter
            else:
                ts = " "


            # first value is the timestamp
            medianOut = "\"" + str (ts) + "\" " +str (time)+" "+str (totalRtt*1000)

            previousMedian = 0
            previousHop = 0
            # median for every hop
            for hop in times[time]:
                while previousHop+1 < hop:
                    previousHop +=1
                    medianOut = medianOut + " 0"

                previousHop +=1

                times[time][hop].sort()
                median = self.resultSet.percentile (times[time][hop], 0.5) 

                # this is actually average
                median = float (sum (times[time][hop]))/ len (times[time][hop])

                medianDiff = (median - previousMedian) * 1000
                if medianDiff <= 0:
                    medianDiff = 0

                medianOut = medianOut + " " + str (medianDiff)
                previousMedian = median

            while previousHop+1 <= numberOfHops:
                previousHop +=1
                medianOut = medianOut + " 0"

            if medianOut != "":
                xticCounter += 1

            # appending line break afer each line
            datafile.write (medianOut + "\n")


    def rttHistogram (self, numberOfHops, totalRtt, filename="rttHistogram"):

        gnufile = open (self.path+"rttHistogram.gnu", "w")
        
        gnufile.write ('set terminal postscript enhanced color\n')
        gnufile.write ('set output "'+self.path+filename+'.ps"\n')
        gnufile.write ('set title "Queue delay on top of minimum path RTT - {0}"\n'.format (self.dbName.replace("_","-")))
        gnufile.write ('set xlabel "Time"\n')
        #gnufile.write ('set xtics rotate by -45 nomirror\n')
        gnufile.write ('set ylabel "Added Queue delay(ms)"\n')
        gnufile.write ('set grid ytics lw 3\n')
        gnufile.write ('set key below samplen 1 spacing 1\n')
        gnufile.write('set style histogram rowstacked\n')
        gnufile.write('set style data histograms\n')
        gnufile.write('set style fill solid 1.00 border -1\n')
        gnufile.write("plot '"+self.path+"queuedelay.data' using 3:xticlabel(1)  title columnhead, for [i=4:{0}] '' using i title columnhead\n".format(numberOfHops+3) )



