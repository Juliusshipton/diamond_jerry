
from UEIO import *
import time
#import string

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM10')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')


#define which counter to use
COUNTER = 1

# --------------------------------------------------------------------------

ueio.setCounterMode(COUNTER, ueio.MODE_FREE_RUN, 4)

ueio.enableCounter(COUNTER)

mode = ueio.getCounterMode(COUNTER)
print "Mode: %d" %mode[ueio.CNTRMODE]
print "Size: %d" %mode[ueio.CNTRSIZE]

flags = ueio.getCounterStatus(COUNTER)
print "Carry:     %d" %flags[ueio.CY]
print "Borrow:    %d" %flags[ueio.BW]
print "Compare:   %d" %flags[ueio.CMP]
print "Enable:    %d" %flags[ueio.CEN]
print "Direction: %d" %flags[ueio.UD]

for i in range(100):
  ueio.writeCounter(COUNTER, 0)
  ueio.loadCounter(COUNTER)
  #print "OTR = %d" %ueio.loadCounter(COUNTER)
  time.sleep(1)
  print "CNTR = %d" %ueio.readCounter(COUNTER)


#print "CNTR = %d" %ueio.readCounter(COUNTER)

#ueio.clearCounter(COUNTER)
#print "clear counter"

#print "CNTR = %d" %ueio.readCounter(COUNTER)























