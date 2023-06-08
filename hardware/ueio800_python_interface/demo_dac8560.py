
from M9803R import *
from UEIO import *
import time

# get connection to the multimeter
meter = M9803R(interface = 'COM1')

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')


# --------------------------------------------------------------------------

f = open('data.dat', 'w')
f.write("# " + "val " + "voltage" + "\n")

ueio.InitSPI(ueio.MODE2)

i = 0
val = 0

while (val < 0xffff):
  val = i * 4096
  
  ueio.SPICS(ueio.LOW)  # set Chip Select low
  ueio.SPI8bit(0)       # send start code
  ueio.SPI16bit(val)    # send 16-bit value
  ueio.SPICS(ueio.HIGH) # set Chip Select high
  
  time.sleep(0.1)
  tmp = meter.getValue()
  #tmp = 0
  #print "#" + str(i) + " val= " + str(val) + " voltage " + str(tmp)
  tmp2 = str(i) + " " + str(val) + " " + str(tmp) + "\n"
  f.write(tmp2)
  i += 1

f.close()

print "done"
