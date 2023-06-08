# for tis example connect a RC servo as follows:
# yellow wire to IO pin 15
# black wire to GND of UEIO and external power supply
# red wire to externally provided supply voltage


from UEIO import *
import time

# get connection to the UEIO800
#ueio = UEIO(interface = 'VCP', address = 'COM27')
ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')



# --------------------------------------------------------------------------

# set IO direction of block 0 as output
ueio.setIOdir(0, ueio.OUTPUT)

# set IO voltage level of block 0 to +5V
ueio.setIOVCC(0, ueio.VCC5V)

# init pulse pattern
# Timebase: 1ms
# Periode: 100ms
# Polarity: high
ueio.initPulse(100000, 10, 99, ueio.HIGH)
#ueio.initPulse(250, 6, 99, ueio.HIGH)

ueio.clearPulse(ueio.LOW) # clear to low
#ueio.clearPulse(ueio.HIGH) # clear to high

for i in range(0, 10):
  ueio.setPulse(i, 3) # pin 0 and pin 1 high

for i in range(10, 20):
  ueio.setPulse(i, 2) # pin 1 high
  
for i in range(20, 40):
  ueio.setPulse(i, 1) # pin 0 high
  
for i in range(60, 80):
  ueio.setPulse(i, 1) # pin 0 high
  
for i in range(0, 50):
  print "pulse[%d] = %X" %(i, ueio.getPulse(i))


# start pulse pattern on pin 0 and pin 1
ueio.startPulse(3, 0)




