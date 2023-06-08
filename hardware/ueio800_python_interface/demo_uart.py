
from UEIO import *
import time

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')

  
# --------------------------------------------------------------------------

# set voltage level to +5V
ueio.setComVCC(ueio.VCC5V)

ueio.InitUART(9600)


while 1:
  tmp = ueio.UARTread()
  if tmp != "":
    print tmp

  time.sleep(0.005)
  