
from UEIO import *
import time

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')

# --------------------------------------------------------------------------

f = open('data.dat', 'w')
f.write("# " + "val " + "ADC1 " + "ADC2" + "\n")

i = 0
val = 0

while (val <= 0xfff):
  val = i * 8
  
  ueio.setDACs(val, val)
  
  time.sleep(0.5)
  adcvals = ueio.getADCs(128)
  #print "#" + str(i) + " val=" + str(val) + " ADC1=" + str(adcvals[0]) + " ADC2=" + str(adcvals[1])
  tmp2 = str(i) + " " + str(val) + " " + str(adcvals[0]) + " " + str(adcvals[1]) + "\n"
  f.write(tmp2)
  i += 1

f.close()

print "done"
