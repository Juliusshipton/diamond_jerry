# for tis example connect a RC servo as follows:
# yellow wire to IO pin 15
# black wire to GND of UEIO and external power supply
# red wire to externally provided supply voltage


from UEIO import *
import time

# get connection to the UEIO800
#ueio = UEIO(interface = 'VCP', address = 'COM27')
ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')

#define which counter to use
COUNTER = 1

# --------------------------------------------------------------------------

# set IO direction of block 0 as output
ueio.setIOdir(0, ueio.OUTPUT)

# set IO voltage level of block 0 to +5V
ueio.setIOVCC(0, ueio.VCC5V)

# init pulse pattern
# Timebase: 1ms
# Periode: 100ms
# Polarity: high
#ueio.initPulse(100000, 10, 19, ueio.HIGH)
ueio.initPulse(250, 6, 19, ueio.HIGH)

ueio.clearPulse(ueio.LOW) # clear to low
#ueio.clearPulse(ueio.HIGH) # clear to high

for i in range(0, 10):
  ueio.setPulse(i, 1) # pin 0 high

# set up counter, enable and clear
ueio.setCounterMode(COUNTER, ueio.MODE_FREE_RUN, 4)
ueio.enableCounter(COUNTER)
ueio.clearCounter(COUNTER)
  
print "CNTR = %d" %ueio.readCounter(COUNTER)
  
# start pulse pattern on pin 0
ueio.startPulse(1, 12345)

time.sleep(2)

print "CNTR = %d" %ueio.readCounter(COUNTER)




