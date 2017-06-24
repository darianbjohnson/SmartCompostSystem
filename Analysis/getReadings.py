##################################################################
#GetReadings.py is part of the Smart Compost system
#This code runs on an Intel Edison and performs analysis
#The script also outputs data (and metadata) for the UI
#######
#Questions: @darianbjohnson (Twitter) or darianbjohnson.com
#
#FYI - you may need to run this code in the bluepy folder location
#
##################################################################


from bluepy.btle import Scanner, DefaultDelegate, UUID, Peripheral
import time
import binascii
import struct

from datetime import timedelta, datetime
import json
import sqlite3
import time
import math
import io
import os
#from scipy.stats import linregress 
#for sudo apt-get install python-numpy 
#for sudo apt-get install python-scipy 
import numpy as np

#*************************************************************
#Custom Dictionary for creating JSON from Sqlite
#*************************************************************
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

#*************************************************************
#BTLE Settings
#*************************************************************
deviceNameCompost = "Compost"
sleepIfFound = 3600  #secs - 1 hr
sleepIfNotFound = 300 #secs - 5 mins

#*************************************************************
#Compost Analysis Settings
#*************************************************************
database = 'smart_compost.db'
json_output = '/www/pages/currentReadings.json'
now_epoch = time.time()
today = datetime.today() 
daysWhenReady = 35
daysAtSafeTempLevel = 25
baselineTemp = 140
ambientTempCold = 40 #degrees F
width = 25 #in cm
length = 10 # cm
partOfVolumeEq = width * length

#Limits--------
tempDanger = 175
tempHigh = 160
tempOK = baselineTemp #140
tempLow = 90
moistHigh = 60
moistLow = 40
scrapHigh = 20
scrapMedium = 10


#Return Values
needWater = 0
ventAngle = 0



#*************************************************************
#Compost Messages Settings
#*************************************************************
tempMessageArray = [
    "Your compost is at optimal levels.", #0
    "Your compost is ready for use. At your convenience, move your sensors to a new compost pile/layer.", #1
    "Your compost heating cycle is complete and is in a 'curing stage'.", #2
    "Your compost has reached an unsafe temperature. Immediately turn the compost and add water.", #3
    "Your compost has reached unhealthily temperature. At your convenience, turn compost and add 'brown' (Carbon-rich) materials.", #4
    "Your compost temperature is slightly higher than optimal. You may want to turn the compost and add 'brown' materials.", #5
    "Your compost temperature is slightly higher than optimal, but is staring to cool off. I will let you know if any action is required.", #6
    "Your compost is at optimal temperature.", #7
    "Your compost temperature is lower than optimal, but is staring to warm up. I will let you know if any action is required.", #8
    "Your compost temperature is lower than optimal, and is continuing to cool. At your convenience, turn compost and add 'green' (Nitrogen-rich) materials.", #9
    "Your compost temperature is lower than optimal, and is continuing to cool. The ambient temperature is low, so you should cover your compost to continue aerobic composting." #10
    ]
        
moistureMessageArray = [
    "Your compost moisture is too wet. Turn your compost and add 'green' (Nitrogen-rich) materials.", #0
    "Your compost moisture content is too wet but is starting to dry out. I will let you know if any action is required.", #1
    "Your compost is at optimal moisture levels.", #2
    "Your compost moisture content is too dry, but is starting to reach optimal moisture. I will let you know if any action is required.", #3
    "Your compost is too dry and requires your attention. You need to turn and water your compost." #4
    ]
    
#Warnings---------
success = "alert alert-success"
info = "alert alert-info"
warning = "alert alert-warning"
danger = "alert alert-danger"
	

#*************************************************************
#Define BTLE UUIDs
#*************************************************************
validUUIDs = []

validUUIDs.append([])
validUUIDs[0].append("0411dc92-895b-4639-b627-c663f6726c3c")
validUUIDs[0].append("compostTempF")

validUUIDs.append([])
validUUIDs[1].append("0411dc91-895b-4639-b627-c663f6726c3c")
validUUIDs[1].append("datetime")

validUUIDs.append([])
validUUIDs[2].append("0411dc93-895b-4639-b627-c663f6726c3c")
validUUIDs[2].append("ambientTempF")

validUUIDs.append([])
validUUIDs[3].append("0411dc94-895b-4639-b627-c663f6726c3c")
validUUIDs[3].append("compostMoisture")

validUUIDs.append([])
validUUIDs[4].append("0411dc95-895b-4639-b627-c663f6726c3c")
validUUIDs[4].append("methanePPM")

validUUIDs.append([])
validUUIDs[5].append("0411dc96-895b-4639-b627-c663f6726c3c")
validUUIDs[5].append("waterLevel")


#("0411dc97-895b-4639-b627-c663f6726c3c")
#("ventAngle")

#BLECharacteristic startPump("0411dc98-895b-4639-b627-c663f6726c3c", BLERead | BLEWrite, 2 );

uuidCount = len(validUUIDs)

#*************************************************************
#Main program to provide recommendations and update UI
#*************************************************************
def analyzeData(tempF, tempC, ambientTemp, moisture, methane, waterLevel):  

    #get inputs for analysis
    trendDataJSON = getTrendData()
    scrapDataJSON = getScrapData()
    days = handleDateLogic()
    
    lastScrapLevel = scrapDataJSON["lastScrapLevel"]
    totalScraps = scrapDataJSON["totalScraps"]
    
    tempTrend = trendDataJSON['tempTrend']
    moistTrend = trendDataJSON['moistTrend']
        
    tempAlert = info
    moistAlert = info
    methaneAlert = info
    waterLevelAlert = info
    scrapLevelAlert =  info
    scrapLevelMsg = ""
    waterLevelMsg = ""	
    OverallMsg = tempMessageArray[0]
    msgPriority = 3 #1 = trumps all other actions, #2 additive
	
    ventAngle = 0
    needWater = 0
	
	#######################
    #Handle Scrap Level
    if lastScrapLevel > scrapHigh:
        scrapLevelAlert = danger
        scrapLevelMsg = "Please empty"
    elif scrapHigh >= lastScrapLevel > scrapMedium:
        scrapLevelAlert = warning
        scrapLevelMsg = "Empty soon"
    else:
        scrapLevelAlert = success
        scrapLevelMsg = "Ok"
		
    #######################
    #Handle Water Level
    if waterLevel <= 0:
        waterLevelMsg = "Refill"
        waterLevelAlert = danger

    else:
        waterLevelMsg = "Ok"
        waterLevelAlert = success
            
    #######################
    #Handle Methane Level
    if methane > 50000:
        methaneAlert = danger
    elif 50000 >= methane > 10000:
        methaneAlert = warning
    else:
        methaneAlert = success

	#######################
    #Handle Temperature and Moisture
    if days >= daysWhenReady:
        OverallMsg = tempMessageArray[1]
        
    elif days >= daysAtSafeTempLevel:
        OverallMsg = tempMessageArray[2]
        
    else: # the compost is not ready
    
        ################################################################
        #Handle Temperatures
        if tempF > tempDanger:
            needWater = 1
            ventAngle = 1
            tempAlert = danger
            OverallMsg = tempMessageArray[3]
            msgPriority = 1
            
        elif tempDanger >= tempF > tempHigh:
            needWater = 1
            ventAngle = 1
            tempAlert = danger
            OverallMsg = tempMessageArray[4]
            msgPriority = 1
            
        elif tempHigh >= tempF > tempOK:

            if tempTrend < 1:
                ventAngle = 1
                tempAlert = warning
                OverallMsg = tempMessageArray[5]
                msgPriority = 2
            else:
                tempAlert = warning
                OverallMsg = tempMessageArray[6]
                msgPriority = 2
        
        elif tempOK >= tempF > tempLow:
            tempAlert = success
            OverallMsg = tempMessageArray[7]
            msgPriority = 3
        
        else:
            ventAngle = 0
            if tempTrend > 0:
                tempAlert = warning
                OverallMsg = tempMessageArray[8]
                msgPriority = 2
            else:
                if ambientTemp =="low":
                    tempAlert = danger
                    OverallMsg = tempMessageArray[10]
                    msgPriority = 1
                else:
                    tempAlert = warning
                    OverallMsg = tempMessageArray[9]
                    msgPriority = 2
        
        #######################################################################
        #handle Moisture content
        if moisture> moistHigh:
            if moistTrend>=0:
                moistAlert = danger
                if msgPriority > 1: #this message will trump any other message besides temp priority 3
                    OverallMsg = moistureMessageArray[0]
                    ventAngle = 1
                    msgPriority = 1
            else:
                moistAlert = warning
                if msgPriority == 2: # this message is appended to any existing P2 messages
                    OverallMsg = OverallMsg + " " + moistureMessageArray[1]
                    ventAngle = 1
                    msgPriority = 2
                elif msgPriority == 3:#this message is replaces any P3 messages
                    OverallMsg = moistureMessageArray[1]
                    ventAngle = 1
                    msgPriority = 2
        elif moistHigh >=moisture> moistLow:
            moistAlert = success
        else:
            if moistTrend<1:
                moistAlert = danger
                if msgPriority > 1: #this message will trump any other message besides priority 1
                    OverallMsg = moistureMessageArray[4]
                    ventAngle = 0
                    needWater = 1
                    msgPriority = 1
            else:
                moistAlert = warning
                if msgPriority == 2: # this message is appended to any existing P2 messages
                    OverallMsg = OverallMsg + " " + moistureMessageArray[3]
                    needWater = 1
                    msgPriority = 2
                elif msgPriority == 3:#this message is replaces any P3 messages
                    OverallMsg = moistureMessageArray[3]
                    needWater = 1
                    msgPriority = 2
                                   
    writeToUI(days, tempF, tempC, moisture, methane, waterLevelMsg, scrapLevelMsg, totalScraps, OverallMsg , tempAlert , moistAlert , methaneAlert , waterLevelAlert, scrapLevelAlert)
    setIndicators()
    return OverallMsg, ventAngle, needWater



#*************************************************************
#Function to get the scrap data. This us updated in a seperate function
#*************************************************************    
def getScrapData():

	#first we initialize the variables
    lastScrapLevel = 0
    totalScraps = 0

    #then we get the last saved levels
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT lastScrapLevel, totalScraps from kitchenScraps")
    rows = c.fetchall()
    for row in rows:
        lastScrapLevel = row[0]
        totalScraps = row[1]	
    conn.commit()
    c.close()
    return {"lastScrapLevel":lastScrapLevel, "totalScraps":totalScraps} 
	
def getScrapDataFromSensor(scrapLevel):#save scrap data to database
	
	#first we initialize the variables
    lastScrapLevel = 0
    totalScraps = 0

    #then we get the last saved levels
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT lastScrapLevel, totalScraps from kitchenScraps")
    rows = c.fetchall()
    for row in rows:
        lastScrapLevel = row[0]
        totalScraps = row[1]	

    if scrapLevel <1: #scrap may have been emptied, get the last amount and add to total
	    #300 lb = 1 cubic yard (loosly packed)
		#1 cubic yard = 764555 cubic cm
		#
        lbsAdded = lastScrapLevel * partOfVolumeEq * (300/764555)
        print lbsAdded
        totalScraps = totalScraps + lbsAdded
        scrapLevel = 0
    
    c.execute("DELETE FROM kitchenScraps");
    c.execute("INSERT into kitchenScraps (lastScrapLevel, totalScraps) values (?, ?)", (scrapLevel, totalScraps))
    conn.commit()
    c.close()
    

#*************************************************************
#Function to calculate trends: analyze historical data to determine if temp/moisture is rising or falling
#*************************************************************    
def getTrendData():
    days = []
    temps = []
    moisture = []
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT round(AVG(tempF),0) AS avgTempF, round(AVG(moisture),0) AS avgMoisture, date(datetime, 'unixepoch', 'localtime') as day FROM readings GROUP BY date(datetime, 'unixepoch', 'localtime') order by day DESC LIMIT 7") #order by day ASC	
    rows = c.fetchall()
    for row in rows:
        readingDay = datetime.strptime(row[2], "%Y-%m-%d")		
        if abs((readingDay-today).days) <5: #we only want to look at records up to 4 days old
            temps.append(row[0])
            moisture.append(row[1])
            days.append((readingDay-today).days + 5)
    if len(days)>1:
        tempTrend =  best_fit(days, temps)
        moistTrend = best_fit(days, moisture)
        best_fit(days, temps)		
    else:
        tempTrend = 0
        moistTrend = 0
    c.close()	
    return {"tempTrend":tempTrend,"moistTrend":moistTrend}

#*************************************************************
#Function to determine compost readiness
#*************************************************************      
def handleDateLogic(): 	
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT round(AVG(tempF),0) AS avgTempF, date(datetime, "unixepoch", "localtime") as day FROM readings GROUP BY date(datetime, "unixepoch", "localtime")') #order by day DESC	
    rows = c.fetchall()
    calcDaysAtSafeTempLevel = 0
    for row in rows:
        if row[0] > baselineTemp and calcDaysAtSafeTempLevel<= daysAtSafeTempLevel:
            calcDaysAtSafeTempLevel+= 1
            date = row[1] 
            dateOfLastTemp = datetime.strptime(date, "%Y-%m-%d") #will need to read from database
    
    if calcDaysAtSafeTempLevel >= daysAtSafeTempLevel:
        daysSince25th = abs((today - dateOfLastTemp).days) 
        
        return daysSince25th + daysAtSafeTempLevel       

    else:
        return calcDaysAtSafeTempLevel
            
    

#*************************************************************
#Function to write JSON of values for website
#*************************************************************  		
def writeToUI(days, tempF, tempC, moisture, methane, waterLevelMsg, scrapLevelMsg, totalScraps, messages , tempAlert , moistAlert , methaneAlert , waterLevelAlert, scrapLevelAlert): 
	#write values to database for UI
	conn = sqlite3.connect(database)
	c = conn.cursor()
	c.execute("DELETE FROM ui");
	c.execute("INSERT OR REPLACE into UI (days, tempF, tempC, moisture, methane, waterLevelMsg, scrapLevelMsg, totalScraps, messages , tempAlert , moistAlert , methaneAlert , waterLevelAlert, scrapLevelAlert, datetime)values (?, ?, ?, ?, ?, ?, ?, ?, ? , ? , ? , ? , ?, ?, ? )", (days, tempF, tempC, moisture, methane, waterLevelMsg, scrapLevelMsg, totalScraps, messages , tempAlert , moistAlert , methaneAlert , waterLevelAlert, scrapLevelAlert, now_epoch))
	conn.commit()
	#c.close()
	
	
	#connection = sqlite3.connect(database)
	conn.row_factory = dict_factory
	c = conn.cursor()
	c.execute("select * from ui")
	# fetch all or one we'll go for all.
	results = c.fetchall()
	#print results[0]
	conn.close()	
	with io.open(json_output, 'w', encoding='utf-8') as f:
	    f.write(json.dumps(results[0], ensure_ascii=False))
	
	return 'ok'
    
def setIndicators(): #stub to set sensor data
    return 'ok'

#*************************************************************
#Function to write data to database
#*************************************************************      
def persistSensorData(tempF, tempC, ambientTempF, ambientTempC, moisture, methane, waterLevel): 
    #write values to database for trend analysis and history
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("INSERT into readings (tempF, tempC, ambientTempF, ambientTempC, moisture, methane, waterLevel, datetime)values (?, ?, ?, ?, ?, ?, ?, ?)", (tempF, tempC, ambientTempF, ambientTempC, moisture, methane, waterLevel, now_epoch))
    conn.commit()
    c.close()
    return 'ok'

#*************************************************************
#Function to determine slope of data points (for trend analysis)
#*************************************************************      
def best_fit(X,Y):
    #Y = [141, 158]
    #X = [-1, 0]	
    x = np.array(X)
    y = np.array(Y)	
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, y)[0]
    return m

#*************************************************************
#Function to determine BTLE devices available
#*************************************************************    
class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print "Discovered device", dev.addr
        elif isNewData:
            print "Received new data from", dev.addr


class MyDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        print("A notification was received: %s" %data)


        val = binascii.b2a_hex(data)
        val = binascii.unhexlify(val)
        val = str(val).strip()
        val = int(val)
        getScrapDataFromSensor(val)
        print "Amount in bin : "  + str(val)
			
def connectToDevice(MAC):
    p = Peripheral(MAC) #p = Peripheral("98:4f:ee:0f:84:1f")
    for x in range(0, uuidCount):
        uuidVal = validUUIDs[x][0]
        try:
            ch = p.getCharacteristics(uuid=uuidVal)[0]
            if (ch.supportsRead()):
                val = binascii.b2a_hex(ch.read())
                val = binascii.unhexlify(val)
                val = str(val).strip()
                val = int(val)
                print validUUIDs[x][1]+ ": "  + str(val)

                if validUUIDs[x][1] == "compostTempF":
                    tempF = val
                    tempC = (tempF - 32) * 5/9
                elif validUUIDs[x][1] == "ambientTempF":
                    ambientTempF = val
                    ambientTempC = (ambientTempF - 32) * 5/9
                    if ambientTempF <=ambientTempCold:
                        ambientTemp = "low"
                    else:
                        ambientTemp = "high"
                elif validUUIDs[x][1] == "compostMoisture":
                    moisture = val
                elif validUUIDs[x][1] == "methanePPM" :
		            methane = val
                elif validUUIDs[x][1] == "waterLevel" :
		            waterLevel = val
        finally:
            print "Done"
    persistSensorData(tempF, tempC, ambientTempF, ambientTempC, moisture, methane, waterLevel)
    overallMsg, ventAngle, needWater = analyzeData(tempF, tempC, ambientTemp, moisture, methane, waterLevel)
    print str(needWater) + " : Need Water?"
    print str(ventAngle) + " : Vent Angle"	
    if needWater == 1:
        ch = p.getCharacteristics(uuid="0411dc98-895b-4639-b627-c663f6726c3c")[0]
        ch.write("1")
    if ventAngle == 1:
        ch = p.getCharacteristics(uuid="0411dc97-895b-4639-b627-c663f6726c3c")[0]
        ch.write("1")
    else:
        ch = p.getCharacteristics(uuid="0411dc97-895b-4639-b627-c663f6726c3c")[0]
        ch.write("0")
    p.disconnect()
    return overallMsg


def getMAC(valueName):
    scanner = Scanner().withDelegate(ScanDelegate())
    devices = scanner.scan(4.0)

    MAC = "empty"
			
    for dev in devices:
        for (adtype, desc, value) in dev.getScanData():
            if (desc == "Complete Local Name" and value == valueName):
                print "Device %s (%s), RSSI=%d dB" % (dev.addr, dev.addrType, dev.rssi)		
                print "  %s = %s" % (desc, value)
                MAC = dev.addr
    return MAC

				
    
	
#*************************************************************
#Code that starts the process
# 1 - Scan devices and determine if Kitchen Bin system is available
# 2  If device is available, registers for notifications
# 3 - Scan devices and determine if Compost system is available
# 4a - If available, reads sensor data, saves to database
# 4b - performs analysis and writes json file for UI
# 5 - waits an hour and reconnects.
#
# If a system cannot be found, attepts again in 5 mins
#************************************************************* 


#Enable bluetooth
print "Turning on Bluetooth"
os.system("rfkill unblock bluetooth")
time.sleep(3)

nowSecs = 0
nowKitchenSecs = 0
connectedToKitchen = False

kitchenMAC= "empty"
kitchenMAC = getMAC("KitchenBin")
kitchenPConnected = False

if kitchenMAC != "empty":
    kitchenP = Peripheral(kitchenMAC)
    kitchenP.setDelegate( MyDelegate() )
	# Setup to turn notifications on, e.g.
    svc = kitchenP.getServiceByUUID('9a4587b1-4d85-4c75-b88b-faa619295a18')
    ch = svc.getCharacteristics()[0]
    print(ch.valHandle)

    kitchenP.writeCharacteristic(ch.valHandle+1, "\x01\x00")
    kitchenPConnected = True

    print("connected to KitchenBin and waiting for notifications")

while 1:
    
    if kitchenPConnected == True:
        if kitchenP.waitForNotifications(1.0):
            continue
    else:
        while nowKitchenSecs < time.time():
            kitchenMAC = getMAC("KitchenBin")
            if kitchenMAC != "empty":
                kitchenP = btle.Peripheral(kitchenMAC)
                kitchenP.setDelegate( MyDelegate() )
                kitchenPConnected = true

                print("connected to KitchenBin and waiting for notifications")
            else:
                nowKitchenSecs = time.time() + sleepIfNotFound
	
    while nowSecs < time.time():
        MAC = getMAC("Compost")		
		
        if (MAC != "empty"):
            print "found it"
            try:
                print connectToDevice(MAC)
                nowSecs = time.time() + sleepIfFound
                MAC = "empty"	
                print "We got the readings, wait for an hour"
            except:
                MAC = "empty"		
        else:
            print "We didn't find, need to look again in 5 mins"
            nowSecs = time.time() + sleepIfNotFound
		
		

