
from UEIO import *
import time
#import string

# get connection to the UEIO800
#ueio = UEIO(interface = 'VCP', address = 'COM27')
ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')



def idnTest(number=0):
  errornumber = 0
  for i in range(number):
    idn = ueio.getIDN()
    if idn != "test":
      print "IDN test failed at " + str(i)
      print "read IDN is " + str(idn)
      errornumber += 1
    
  print "run " + str(number) + " times"   
  print "with " + str(errornumber)+ " errors"
  return
  
def LEDtest(number=0):
  for i in range(number):
    ueio.setLED(0, 0, 0)
    time.sleep(0.5)
    ueio.setLED(1, 1, 1)
    time.sleep(0.5)
  return

# --------------------------------------------------------------------------

#idnTest(10)

#LEDtest(5)

#print ueio.getIDN()












