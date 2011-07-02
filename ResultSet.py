"""   
    This file is subject to the terms and conditions of the GNU General
    Public License. See the file COPYING in the main directory of this
    archive for more details.

"""

import math
import datetime
from copy import copy
from socket import gethostname
from time import sleep, localtime

import MySQLdb

#
# Constructor
#
# Input: None
#
# Output:  None
#
class ResultSet:
    def __init__(self):
        # initialize a new dictionary to hold the data
        self.data = {}
        self.verboseLevel = 1
        self.hoplist = None
        
        #self.plot = Gnuplot.Gnuplot(debug=1)
    
    
    def updateHoplist(self,hoplist):
        self.hoplist = hoplist
        
        # check if the hoplist matches with the dataset we got
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM hoplist")
        r = c.fetchone()
        
        print "new",len(hoplist),"old",r[0]

        # if there are no hop stats in our dataset,
        # then we're good. + we insert them while we're here
        if r[0] == 0:
            print "hoplist matches"
            hopCounter = 1
            for t in self.hoplist:
                print type (t), t
                c.execute("INSERT INTO hoplist VALUES (%s,%s)",(hopCounter,t))
                hopCounter += 1

            return
        elif r[0] != len(hoplist):
            print "ERROR: length of the hoplist doesn't match our dataset"
            sys.exit(1)

    #
    # DB related functions
    #

    def dbCommit (self):
        """ Commit changes to the DB file

        As committing each recieved packet would kill both performance and 
        some HDDs are changes commited (written) to file in batches
        """
        self.conn.commit()


    def dbConnect (self, hostname, username, password, dbName):
        """Connecting to a database

        Attaching to a file which holds the sqlite3 database

        Keyword arguments:
        dbfile -- relative path to the db file
        """
        
        # this block could probably have been done a bit neater,
        # for ex move this to a config file - but it's OKAY for now. 
        try:
            self.conn = MySQLdb.connect( 
                host=hostname,
                user=username,
                passwd=password,
                db=dbName)

        except ValueError:
            raise Exception( "I crashed horribly, probably because the database {0} does not exist.".format(dbName))


        # initializing tables if needed
        c = self.conn.cursor ()
        c.execute ("CREATE TABLE IF NOT EXISTS data (hop INTEGER, time TEXT, packetsize INTEGER, rtt FLOAT)")
        c.execute ("CREATE TABLE IF NOT EXISTS hoplist (hop INTEGER PRIMARY KEY, ip TEXT)")

    def dbClose (self):
        self.conn.close()

    #
    # General methods
    #
    def add (self, hop, size, rtt, time):
        """Saves a new observation to the database
        
        Keyword arguments:
        hop -- hop number (int)
        size -- packetsize
        rtt -- observed rtt
        time -- timestamp of when the round was started
        """
        query = "INSERT INTO data VALUES ({0}, {1}, {2}, {3})".format(hop, time, size, rtt)
        c = self.conn.cursor ()
        c.execute (query)



    # Find the percentile of a list of values.
    # @parameter N - is a list of values. Note N MUST BE already sorted.
    # @parameter percent - a float value from 0.0 to 1.0.
    # @parameter key - optional key function to compute value from each element of N.
    # @return - the percentile of the values
    def percentile (self, N, percent, key=lambda x:x):
        if not N:
            return None
        k = (len(N)-1)*percent
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return key(N[int(k)])
        d0 = key(N[int(f)]) * (c-k)
        d1 = key(N[int(c)]) * (k-f)
        return d0+d1


    #
    # ResultTable::median
    #
    # Input:
    #
    # Output: Median value
    #
    # Compute the median of an array of doubles.  
    # As a side effect, the input array is sorted
    # 
    def median (self, values, numValues=0):
        
        values = values.sort()
        return self.percentile(values,0.5)

