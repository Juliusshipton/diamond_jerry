
from UEIO import *
import time

# get connection to the UEIO800
ueio = UEIO(interface = 'VCP', address = 'COM27')
#ueio = UEIO(interface = 'TELNET', address = '192.168.0.10')

DEGREE = u'\N{DEGREE SIGN}'

SEALEVELPRESSURE = 102230 # sea level pressure in Pa for your position
ALTITUDE = 265 # altitude in m for your position

# define constants
BMP180_ADDRESS                  = 0xef
BMP180_REGISTER_CAL_AC1         = 0xaa  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_AC2         = 0xac  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_AC3         = 0xae  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_AC4         = 0xb0  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_AC5         = 0xb2  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_AC6         = 0xb4  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_B1          = 0xb6  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_B2          = 0xb8  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_MB          = 0xba  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_MC          = 0xbc  # R   Calibration data (16 bits)
BMP180_REGISTER_CAL_MD          = 0xbe  # R   Calibration data (16 bits)

BMP180_REGISTER_CHIPID          = 0xd0
BMP180_REGISTER_VERSION         = 0xD1
BMP180_REGISTER_SOFTRESET       = 0xe0
BMP180_REGISTER_CONTROL         = 0xf4
BMP180_REGISTER_TEMPDATA        = 0xf6
BMP180_REGISTER_PRESSUREDATA    = 0xf6
BMP180_REGISTER_READTEMPCMD     = 0x2e
BMP180_REGISTER_READPRESSURECMD = 0x34

BMP085_MODE_ULTRALOWPOWER       = 0
BMP085_MODE_STANDARD            = 1
BMP085_MODE_HIGHRES             = 2
BMP085_MODE_ULTRAHIGHRES        = 3

# define global variables
ac1, ac2, ac3, ac4, ac5, ac6, b1, b2, mb, mc, md = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
mode = BMP085_MODE_ULTRAHIGHRES

# --------------------------------------------------------------------------

def twos_comp(val, bits):
  """compute the 2's compliment of int value val"""
  if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
      val = val - (1 << bits)        # compute negative value
  return val                         # return positive value as is

def bmp180_read8(reg):
  data = ueio.I2Cread8bit(BMP180_ADDRESS, reg)
  return data
  
def bmp180_read16(reg):
  data = ueio.I2Cread16bit(BMP180_ADDRESS, reg)
  return data
  
def bmp180_readS16(reg):
  data = twos_comp(ueio.I2Cread16bit(BMP180_ADDRESS, reg), 16)
  return data
  
def bmp180_writeCommand(reg=0, val=0):
  ueio.I2Csend8bit(BMP180_ADDRESS, reg, val)
  return
    
def bmp180_readCoefficients():
  global ac1, ac2, ac3, ac4, ac5, ac6, b1, b2, mb, mc, md
  ac1 = bmp180_readS16(BMP180_REGISTER_CAL_AC1)
  ac2 = bmp180_readS16(BMP180_REGISTER_CAL_AC2)
  ac3 = bmp180_readS16(BMP180_REGISTER_CAL_AC3)
  ac4 = bmp180_read16(BMP180_REGISTER_CAL_AC4)
  ac5 = bmp180_read16(BMP180_REGISTER_CAL_AC5)
  ac6 = bmp180_read16(BMP180_REGISTER_CAL_AC6)
  b1 = bmp180_readS16(BMP180_REGISTER_CAL_B1)
  b2 = bmp180_readS16(BMP180_REGISTER_CAL_B2)
  mb = bmp180_readS16(BMP180_REGISTER_CAL_MB)
  mc = bmp180_readS16(BMP180_REGISTER_CAL_MC)
  md = bmp180_readS16(BMP180_REGISTER_CAL_MD)
  return
  
def bmp180_readRawTemperature():
  bmp180_writeCommand(BMP180_REGISTER_CONTROL, BMP180_REGISTER_READTEMPCMD)
  time.sleep(0.005)
  data = bmp180_read16(BMP180_REGISTER_TEMPDATA)
  return data
  
def bmp180_readRawPressure():
  bmp180_writeCommand(BMP180_REGISTER_CONTROL, BMP180_REGISTER_READPRESSURECMD + (mode << 6))
  time.sleep(0.026)
  
  p16 = bmp180_read16(BMP180_REGISTER_PRESSUREDATA)
  p32 = p16 << 8
  p8 = bmp180_read8(BMP180_REGISTER_PRESSUREDATA + 2)
  p32 = p32 + p8
  p32 = p32 >> (8 - mode)
  return p32
  
def bmp180_getTemperature():
  ut = bmp180_readRawTemperature()
  x1 = (ut - ac6) * (ac5 / 32768.0)
  x2 = (mc << 11) / (x1 + md)
  b5 = int(x1 + x2)
  t = (b5 + 8) / 16.0 # temp in 0.1 degC
  return (t / 10.0)

def bmp180_getPressure():
  ut = bmp180_readRawTemperature()
  up = bmp180_readRawPressure()

  # Temperature compensation
  x1 = (ut - ac6) * (ac5 / 32768.0)
  x2 = (mc << 11) / (x1 + md)
  b5 = int(x1 + x2)
  
  # Pressure compensation
  b6 = b5 - 4000
  x1 = (b2 * ((b6 * b6) / 2**12)) / 2**11
  x2 = (ac2 * b6) / 2**11
  x3 = x1 + x2
  b3 = (((ac1 * 4 + x3) << mode) + 2) / 4
  x1 = (ac3 * b6) / 2**13
  x2 = (b1 * ((b6 * b6) / 2**12)) / 2**16
  x3 = ((x1 + x2) + 2) / 4
  b4 = (ac4 * abs(x3 + 32768)) / 2**15
  b7 = ((abs(up) - b3) * (50000 >> mode))
  
  if b7 < 0x80000000:
    p = (b7 * 2) / b4
  else:
    p = (b7 / b4) * 2
  
  x1 = (p / 2**8) * (p / 2**8)
  x1 = (x1 * 3038) / 2**16
  x2 = (-7357 * p) / 2**16
  p = 1.0 * (p + ((x1 + x2 + 3791) / 2**4))
  return p
  
def bmp180_pressureToAltitude(seaLevel, atmospheric):
  # Equation taken from BMP180 datasheet (page 16):
  # http://www.adafruit.com/datasheets/BST-BMP180-DS000-09.pdf
  return (44330.0 * (1.0 - pow(atmospheric / seaLevel, 0.1903)))
  
def bmp180_seaLevelForAltitude(altitude, atmospheric):
  # Equation taken from BMP180 datasheet (page 17):
  # http://www.adafruit.com/datasheets/BST-BMP180-DS000-09.pdf
  return (atmospheric / pow(1.0 - (altitude/44330.0), 5.255))
  
# --------------------------------------------------------------------------

# set voltage level to +5V
ueio.setComVCC(ueio.VCC5V)

bmp180_readCoefficients()

print "T = %.1f" %bmp180_getTemperature() + " " + DEGREE + "C"

#print "p = %d" %bmp180_getPressure()
print "Altitude = %.2f" %bmp180_pressureToAltitude(SEALEVELPRESSURE, bmp180_getPressure()) + " m"


# number = 10
# average = 0.0
# for i in range(number):
  # average += bmp180_getPressure()
# average = average / number
# print "Altitude = %.2f" %bmp180_pressureToAltitude(SEALEVELPRESSURE, average)


print "p0 = %d" %bmp180_seaLevelForAltitude(ALTITUDE, bmp180_getPressure()) + " Pa"











