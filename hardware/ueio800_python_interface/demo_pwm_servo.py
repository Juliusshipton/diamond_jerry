# for tis example connect a RC servo as follows:
# yellow wire to IO pin 15
# black wire to GND of UEIO and external power supply
# red wire to externally provided supply voltage


from UEIO import *
import time

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')

MIN = 1000
MAX = 2000
PIN = 15
  
def initServo():
  # set IO direction of block 1 as output
  ueio.setIOdir(1, ueio.OUTPUT)
  
  # set IO voltage level of block 1 to +5V
  ueio.setIOVCC(1, ueio.VCC5V)
  
  # init PWM with a period of 20ms
  ueio.initPWM(20000, 83, ueio.HIGH)
  return
  
# set servo to position in degree
def setServo(pos=0):
  # calculate pulse length
  pulse = (MAX - MIN) * pos / 180 + MIN
  
  # set servo to position
  ueio.setPWM(PIN, pulse)
  return

# --------------------------------------------------------------------------

initServo()

setServo(0)

time.sleep(2)

setServo(180)

time.sleep(2)

setServo(90)
