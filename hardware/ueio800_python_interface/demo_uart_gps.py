
from UEIO import *
import time

from pynmea import nmea

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')



# --------------------------------------------------------------------------
#calculate checksum from string
def calculateChecksum(string):
  checksum = ord(string[0])
  for i in range(1, len(string)):
    checksum = checksum ^ ord(string[i])
  return checksum
  
# --------------------------------------------------------------------------

# set voltage level to +5V
ueio.setComVCC(ueio.VCC5V)

ueio.InitUART(9600)


#turn on only the second sentence (GPRMC)
#ueio.UARTsend("$PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*29")


status = True
while status:
  nmeaString = ueio.UARTread()
  if nmeaString != "":
    print nmeaString
    time.sleep(0.005)
    
    if nmeaString[1:6] == "GPRMC":
      status = False

data = nmeaString
      
# This is an example GPRMC sentence
#data = "$GPRMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68"

# Create the object
gprmc = nmea.GPRMC()

# Ask the object to parse the data
gprmc.parse(data)


print "Timestamp: %f" %float(gprmc.timestamp)
print "Data Validity: %s" %(gprmc.data_validity)
print "Latitude: %f" %float(gprmc.lat)
print "Latitude Direction: %s" %(gprmc.lat_dir)
print "Longitude: %f" %float(gprmc.lon)
print "Longitude Direction: %s" %(gprmc.lon_dir)
print "Speed Over Ground: %f" %float(gprmc.spd_over_grnd)
print "True Course: %f" %float(gprmc.true_course)
print "Datestamp: %d" %float(gprmc.datestamp)
print "Magnetic Variation: %f" %float(gprmc.mag_variation)
print "Magnetic Variation Direction: %s" %(gprmc.mag_var_dir)



  