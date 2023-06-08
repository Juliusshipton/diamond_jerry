
from UEIO import *
import time
#import string

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')



# --------------------------------------------------------------------------


ueio.setIOdir(0, ueio.OUTPUT)

ueio.setIOVCC(0, ueio.VCC5V)


for i in range(1000):
  ueio.toggleIOpin(0)


# resulting pulse signal: 
# via VCP
# pulse width < 63ms

# via Telnet:
# pulse width < 250us








