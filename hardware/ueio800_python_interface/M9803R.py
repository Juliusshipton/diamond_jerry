
# ----------------------------------------------------------------------------
#
# ----------------------------------------------------------------------------

import time
import serial
import numpy

class M9803R():
  
  """ Gives an interface to the M9803R Multimeter. """
  
  
  VZ  = 3
  BAT = 2
  OR  = 0

  RANGE = 6
  RANGEMASK = 0b00000111
  
  
  # --------------------------------------------------------------------------
  # linux: interface='/dev/ttyUSB0'
  # windows: interface='COM3'
  def __init__(self, interface='COM1'):
    self.ser = serial.Serial(
      port = interface,
      baudrate = 9600,
      bytesize = serial.EIGHTBITS,
      parity = serial.PARITY_NONE,
      stopbits = serial.STOPBITS_ONE,
      timeout = 5,      
      xonxoff = 0,
      rtscts = 0,
      dsrdtr = 0,
      writeTimeout = 5
    )
    self.ser.close()
    self.ser.open()
    time.sleep(0.5)
    
  # --------------------------------------------------------------------------
  def __del__(self):
    if self.ser.isOpen():
      self.ser.close()

  # --------------------------------------------------------------------------
  # functionality
  # --------------------------------------------------------------------------

  # --------------------------------------------------------------------------
  def __readLine(self):
    out = self.ser.readline()
    self.ser.flushInput()
    return out
    
    
  # --------------------------------------------------------------------------
  def __getLine(self):
    length = 0
    while (length != 11):
      out = self.__readLine()
      length = len( out )
      #print "length: " + str(length)
    return map(ord, out)
    
  # -------------------------------------------------------------------------- 
  def getValue(self):
    line = self.__getLine()
    out = 0.0
    
    #this is only true for V DC
    out += 1000.0 * line[4]
    out += 100.0 * line[3]
    out += 10.0 * line[2]
    out += line[1]
    
    if (line[0] & (1 << self.VZ)):
      out = -out
    
    if ((line[self.RANGE] & self.RANGEMASK) == 0):
      out = out / 10000.0
    elif ((line[self.RANGE] & self.RANGEMASK) == 1):
      out = out / 1000.0
    elif ((line[self.RANGE] & self.RANGEMASK) == 2):
      out = out / 100.0
    elif ((line[self.RANGE] & self.RANGEMASK) == 3):
      out = out / 10.0
    else:
      out = out
    return out
    