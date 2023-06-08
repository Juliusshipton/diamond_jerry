
# ----------------------------------------------------------------------------
#
# ----------------------------------------------------------------------------

import time
import serial
import numpy
import string
import sys
import telnetlib

class UEIO():
  
  """ Gives an interface to the UEIO800. """
  
  VCP     = 'VCP'
  TELNET  = 'TELNET'
  __contype = VCP
  
  IDN = ""
  
  ON     = "1"
  OFF    = "0"
  HIGH   = "1"
  LOW    = "0"
  
  INPUT  = "0"
  OUTPUT = "1"
  
  VCCEXT = "0"
  VCC3V3 = "1"
  VCC5V  = "2"
  
  MODE0  = 0
  MODE1  = 1
  MODE2  = 2
  MODE3  = 3
  
  MSB    = "0"
  LSB    = "1"
  
  # counter status flags
  CY  = 0  # Carry latch
  BW  = 1  # Borrow latch
  CMP = 2  # Compare latch
  CEN = 3  # Count enable status
  UD  = 4  # Count direction indicator
  
  # counter modes
  CNTRMODE = 0
  CNTRSIZE = 1
  
  MODE_FREE_RUN    = 0 # free-running count mode
  MODE_SINGE_CYCLE = 1 # single-cycle count mode
  MODE_RANGE_LIMIT = 2 # range-limit count mode
  MODE_MODULO_N    = 3 # modulo-n count mode
  
  
  
  # --------------------------------------------------------------------------
  # linux:   address = '/dev/ttyUSB0'
  # windows: address = 'COM3'
  def __init__(self, interface = VCP, address = 'COM3'):
    self.__contype = interface
  
    if self.__contype == self.VCP:
      self.ser = serial.Serial(
        port = address,
        baudrate = 115200,
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
      
    elif self.__contype == self.TELNET:
      self.tn = telnetlib.Telnet(
        host = address,
        port = 23,
        timeout = 5
      )
      time.sleep(0.5)
      
    else:
      print "error: unknown interface"
    
    
  # --------------------------------------------------------------------------
  def __del__(self):
    if self.__contype == self.VCP:
      if self.ser.isOpen():
        self.ser.close()
    elif self.__contype == self.TELNET:
      self.tn.close()

  # --------------------------------------------------------------------------
  # low level functionality
  # --------------------------------------------------------------------------
  
  # --------------------------------------------------------------------------
  def __sendCommand(self, cmd):    
    ack = "A"
    maxtries = 0
    
    if self.__contype == self.VCP:
      self.ser.flushOutput()
      
      while ord(ack) != 6 and maxtries < 10:
        self.ser.write(cmd + '\n')
        self.ser.flush()
        time.sleep(0.05)
        maxtries += 1
        while self.ser.inWaiting() == 0:
          pass
        
        if self.ser.inWaiting() > 0:
          ack = self.ser.read(1)
          
      if maxtries == 9:
        print "error: unable to send command: " + cmd
      
      self.ser.flushOutput()
      
    elif self.__contype == self.TELNET:
      while ord(ack) != 6 and maxtries < 10:
        self.tn.write(cmd + '\n')
        #time.sleep(0.05)
        maxtries += 1
        ack = self.tn.read_until('\x06')
          
      if maxtries == 9:
        print "error: unable to send command: " + cmd
    
    return
  
  # --------------------------------------------------------------------------
  def __readResponse(self):
    out = ""

    if self.__contype == self.VCP:    
      while self.ser.inWaiting() > 0:
        c = self.ser.read(1)
        if (c != '\n' and c != '\r'):
          out += c
      
      self.ser.flushInput()
    elif self.__contype == self.TELNET:
      out = self.tn.read_until("\r\n")
      out = string.rstrip(out, "\r\n")
    
    return out.decode("utf-8")

  # --------------------------------------------------------------------------
  # command implementation
  # --------------------------------------------------------------------------
  
  # --------------------------------------------------------------------------
  def reset(self):
    self.__sendCommand("*RST")
    return
  
  # --------------------------------------------------------------------------
  def factoryReset(self):
    self.__sendCommand("FACTORYRESET")
    return
  
  # --------------------------------------------------------------------------
  def getIDN(self):
    self.__sendCommand("*IDN?")
    return str(self.__readResponse())
  
  # --------------------------------------------------------------------------
  def getFirmwareVersion(self):
    self.__sendCommand("FWVERSION?")
    return str(self.__readResponse())

  # --------------------------------------------------------------------------
  def setIOdir(self, block=0, dir=INPUT):
    if not (isinstance(block, int) and block <= 1 and block >= 0):
      print "unknown IO block"
      return
      
    self.__sendCommand("SETIODIR " + str(block) + " " +  dir)
    return
    
  # --------------------------------------------------------------------------
  def setIOVCC(self, block=0, val=VCCEXT):
    if not (isinstance(block, int) and block <= 1 and block >= 0):
      print "unknown IO block"
      return
      
    self.__sendCommand("SETIOVCC " + str(block) + " " +  val)
    return
    
  # --------------------------------------------------------------------------
  def setIOpin(self, pin=0, val=LOW):
    if not (isinstance(pin, int) and pin <= 15 and pin >= 0):
      print "unknown IO pin"
      return
      
    self.__sendCommand("SETIOPIN " + str(pin) + " " + val)
    return
    
  # --------------------------------------------------------------------------
  def getIOpin(self, pin=0):
    if not (isinstance(pin, int) and pin <= 15 and pin >= 0):
      print "unknown IO pin"
      return
      
    self.__sendCommand("GETIOPIN " + str(pin))
    return int(self.__readResponse())
    
  # --------------------------------------------------------------------------
  def toggleIOpin(self, pin=0):
    if not (isinstance(pin, int) and pin <= 15 and pin >= 0):
      print "unknown IO pin"
      return
      
    self.__sendCommand("TOGGLEIOPIN " + str(pin))
    return
    
  # --------------------------------------------------------------------------
  def setIOpins(self, mask=0, val=0):
    if not isinstance(mask, int):
      print "bit mask must be given as integer number"
      return
      
    if not isinstance(val, int):
      print "pin values must be given as integer number"
      return
      
    self.__sendCommand("SETIOPINS " + "%X" %(mask & 0xffff) + " %X" %(val & 0xffff))
    return
    
  # --------------------------------------------------------------------------
  def getIOpins(self):
    self.__sendCommand("GETIOPINS")
    return int(self.__readResponse(), 16)

  # --------------------------------------------------------------------------
  def toggleIOpins(self, mask=0):
    if not isinstance(mask, int):
      print "bit mask must be given as integer number"
      return
      
    self.__sendCommand("TOGGLEIOPINS " + "%X" %(mask & 0xffff))
    return
    
  # --------------------------------------------------------------------------
  def initPWM(self, prd=0xffff, pre=0xffff, pol=HIGH):
    if not isinstance(prd, int):
      print "periode must be given as integer number"
      return
      
    if not isinstance(pre, int):
      print "prescaler must be given as integer number"
      return
      
    self.__sendCommand("INITPWM " + "%X " %(prd & 0xffff) + "%X " %(pre & 0xffff) + pol)
    return
    
  # --------------------------------------------------------------------------
  def setPWM(self, pin=12, val=0):
    if not (isinstance(pin, int) and pin <= 15 and pin >= 12):
      print "unknown IO pin"
      return
      
    if not isinstance(val, int):
      print "PWM value must be given as integer number"
      return
      
    self.__sendCommand("SETPWM " + str(pin) + " %X" %(val & 0xffff))
    return
    
  # --------------------------------------------------------------------------
  def getPWM(self):
    self.__sendCommand("GETPWM")
    return int(self.__readResponse(), 16)
    
  # --------------------------------------------------------------------------
  def initPulse(self, res=250, base=1500, prd=0, pol=HIGH):
    reslist = [250, 500, 1000, 1250, 2000, 2500, 5000, 10000, 12500, 20000, 25000, 50000, 100000, 125000, 200000, 250000, 500000]    
    if not (res in reslist):
      print "invalid timebase resolution"
      return
    if not (isinstance(base, int) and base <= 0xffff and base >= 2):
      print "timebase must be given as integer number"
      return
      
    if not isinstance(prd, int):
      print "periode must be given as integer number"
      return

    self.__sendCommand("INITPULSE " + str(res) + " %X" %(base & 0xffff) + " %X " %(prd & 0xfff) + pol)
    return
    
  # --------------------------------------------------------------------------
  def setPulse(self, num=0, val=0):
    if not isinstance(num, int):
      print "pulse number must be given as integer number"
      return
      
    if not isinstance(val, int):
      print "value must be given as integer number"
      return
      
    self.__sendCommand("SETPULSE " +"%X" %(num & 0xfff) + " %X" %(val & 0xffff))
    return
    
  # --------------------------------------------------------------------------
  def getPulse(self, num=0):     
    if not isinstance(num, int):
      print "pulse number must be given as integer number"
      return
      
    self.__sendCommand("GETPULSE " + "%X" %(num & 0xffff))
    return int(self.__readResponse(), 16)
    
  # --------------------------------------------------------------------------
  def clearPulse(self, val=LOW):
    self.__sendCommand("CLRPULSE " + val)
    return
    
  # --------------------------------------------------------------------------
  def startPulse(self, mask=0, num=0):
    if not isinstance(mask, int):
      print "bit mask must be given as integer number"
      return
      
    if not isinstance(num, int):
      print "number of periodes must be given as integer number"
      return

    self.__sendCommand("STARTPULSE " + "%X" %(mask & 0xffff) + " %X" %(num & 0xffff))
    return
    
  # --------------------------------------------------------------------------
  def stopPulse(self):     
    self.__sendCommand("STOPPULSE")
    return    

  # --------------------------------------------------------------------------
  def setDAC(self, dac=1, data=0):
    if not (isinstance(dac, int) and dac <= 2 and dac >= 1):
      print "unknown DAC"
      return
      
    if not isinstance(data, int):
      print "data must be given as integer number"
      return
      
    self.__sendCommand("SETDAC " + str(dac) + " %X" %(data & 0xfff))
    return
    
  # --------------------------------------------------------------------------
  def setDACs(self, data1=0, data2=0):
    if not isinstance(data1, int):
      print "data must be given as integer number"
      return
      
    if not isinstance(data2, int):
      print "data must be given as integer number"
      return
      
    self.__sendCommand("SETDACS" + " %X" %(data1 & 0xfff) + " %X" %(data2 & 0xfff))
    return
    
  # --------------------------------------------------------------------------
  def getDACs(self):
    self.__sendCommand("GETDACS")
    dacstring = string.split(str(self.__readResponse()))
    
    dacvals = []
    for i in range(len(dacstring)):
      dacvals.append(int(dacstring[i], 16))
    
    return dacvals
    
  # --------------------------------------------------------------------------
  def getADCs(self, average=1):
    averagelist = [1,2,4,8,16,32,64,128]    
    if not (average in averagelist):
      print "invalid average"
      return
    self.__sendCommand("GETADCS " + str(average))
    adcstring = string.split(str(self.__readResponse()))
    
    adcvals = []
    for i in range(len(adcstring)):
      adcvals.append(int(adcstring[i], 16))
    
    return adcvals
        
  # --------------------------------------------------------------------------
  def setComVCC(self, val=VCCEXT):     
    self.__sendCommand("SETCOMVCC " + val)
    return
    
  # --------------------------------------------------------------------------
  def setComDir(self, pin=0, dir=INPUT):
    if not (isinstance(pin, int) and pin <= 3 and pin >= 0):
      print "unknown IO line"
      return
      
    self.__sendCommand("SETCOMDIR " + str(pin) + " " +  dir)
    return
    
  # --------------------------------------------------------------------------
  def setComPin(self, pin=0, val=LOW):
    if not (isinstance(pin, int) and pin <= 3 and pin >= 0):
      print "unknown IO line"
      return
      
    self.__sendCommand("SETCOMPIN " + str(pin) + " " + val)
    return
    
  # --------------------------------------------------------------------------
  def getComPin(self, pin=0):
    if not (isinstance(pin, int) and pin <= 3 and pin >= 0):
      print "unknown IO line"
      return
      
    self.__sendCommand("GETCOMPIN " + str(pin))
    return int(self.__readResponse())
    
  # --------------------------------------------------------------------------
  def toggleComPin(self, pin=0):
    if not (isinstance(pin, int) and pin <= 3 and pin >= 0):
      print "unknown IO line"
      return
      
    self.__sendCommand("TOGGLECOMPIN " + str(pin))
    return
    
  # --------------------------------------------------------------------------
  def I2Cread8bit(self, adr=0, reg=0):
    if not isinstance(adr, int):
      print "address must be given as integer number"
      return
      
    if not isinstance(reg, int):
      print "register must be given as integer number"
      return
      
    self.__sendCommand("I2CR "+ "%X " %(adr & 0xff) + "%X " %(reg & 0xff) + "1")
    return int(self.__readResponse(), 16)
    
  # --------------------------------------------------------------------------
  def I2Csend8bit(self, adr=0, reg=0, data=0):
    if not isinstance(adr, int):
      print "address must be given as integer number"
      return
      
    if not isinstance(reg, int):
      print "register must be given as integer number"
      return
      
    if not isinstance(data, int):
      print "data must be given as integer number"
      return
      
    self.__sendCommand("I2CS "+ "%X " %(adr & 0xff) + "%X " %(reg & 0xff) + "%X" %(data & 0xff))
    return
    
  # --------------------------------------------------------------------------
  def I2Cread16bit(self, adr=0, reg=0):
    if not isinstance(adr, int):
      print "address must be given as integer number"
      return
      
    if not isinstance(reg, int):
      print "register must be given as integer number"
      return
      
    #self.__sendCommand("I2CR "+ "%X " %(adr & 0xff) + "%X " %(reg & 0xff) + "1")
    #highdata = int(self.__readResponse(), 16)
    #self.__sendCommand("I2CR "+ "%X " %(adr & 0xff) + "%X " %((reg + 1) & 0xff) + "1")
    #lowdata = int(self.__readResponse(), 16)
    #return ((highdata << 8) | lowdata)
    
    self.__sendCommand("I2CR "+ "%X " %(adr & 0xff) + "%X " %(reg & 0xff) + "2")
    readstring = string.split(str(self.__readResponse()))
    vals = []
    for i in range(len(readstring)):
      vals.append(int(readstring[i], 16))
    
    return ((vals[0] << 8) | vals[1])
    
  # --------------------------------------------------------------------------
  def I2Csend16bit(self, adr=0, reg=0, data=0):
    if not isinstance(adr, int):
      print "address must be given as integer number"
      return
      
    if not isinstance(reg, int):
      print "register must be given as integer number"
      return
      
    if not isinstance(data, int):
      print "data must be given as integer number"
      return
      
    datac = (data >> 8) & 0xff # The value of data shifted 8 bits to the right, creating coarse.
    dataf = data & 0xff        # The remainder of data / 256, creating fine.
      
    self.__sendCommand("I2CS "+ "%X " %(adr & 0xff) + "%X " %(reg & 0xff) + "%X" %(datac & 0xff))
    self.__sendCommand("I2CS "+ "%X " %(adr & 0xff) + "%X " %((reg + 1) & 0xff) + "%X" %(dataf & 0xff))
    return
    
  # --------------------------------------------------------------------------
  def InitSPI(self, mode=MODE0, prescaler=64, firstBit=MSB):
    if not isinstance(prescaler, int):
      print "prescaler must be given as integer number"
      return
    
    prescalerlist = [2,4,8,16,32,64,128,256]    
    if not (prescaler in prescalerlist):
      print "invalid prescaler"
      return
    
    if not (isinstance(mode, int) and mode <= 4 and mode >= 0):
      print "unknown SPI mode"
      return
    
    if not (firstBit == self.MSB or firstBit == self.LSB):
      print "unknown First Bit"
      return
    
    self.__sendCommand("SPIINIT " + str(mode) + " " + str(prescaler) + " " + firstBit)
    return
  
  # --------------------------------------------------------------------------
  def SPICS(self, state=HIGH):
    self.__sendCommand("SPICS " + state)
    return
    
  # --------------------------------------------------------------------------
  def SPI8bit(self, data=0):
    if not isinstance(data, int):
      print "data must be given as integer number"
      return
      
    self.__sendCommand("SPI %X" %(data & 0xff))
    return
    
  # --------------------------------------------------------------------------
  def SPI16bit(self, data=0):
    if not isinstance(data, int):
      print "data must be given as integer number"
      return
      
    datac = (data >> 8) & 0xff # The value of data shifted 8 bits to the right, creating coarse.
    dataf = data & 0xff        # The remainder of data / 256, creating fine.
      
    self.__sendCommand("SPI %X" %(datac) + " %X" %(dataf))
    return
    
  # --------------------------------------------------------------------------
  def InitUART(self, baud=115200):
    baudratelist = [4800, 9600, 19200, 38400, 57600, 115200]    
    if not (baud in baudratelist):
      print "invalid baud rate"
      return
    
    self.__sendCommand("UARTINIT " + str(baud))
    return
    
  # --------------------------------------------------------------------------
  def UARTsend(self, data):    
    self.__sendCommand("UARTS " + data)
    return
    
  # --------------------------------------------------------------------------
  def UARTread(self):
    self.__sendCommand("UARTR")  
    return str(self.__readResponse())
    
  # --------------------------------------------------------------------------
  def getCounterStatus(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("CNTRSTATUS " + str(cntr))
    statusString = string.split(str(self.__readResponse()))
    
    statusFlags = []
    for i in range(len(statusString)):
      statusFlags.append(int(statusString[i]))
    
    return statusFlags
  
  # --------------------------------------------------------------------------
  def clearCounterStatus(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("CLRCNTRSTATUS " + str(cntr))
    return
    
  # --------------------------------------------------------------------------
  def setCounterMode(self, cntr=1, mode=0, size=4):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return
      
    if not (isinstance(mode, int) and mode <= 3 and mode >= 0):
      print "unknown counter mode"
      return
      
    if not (isinstance(size, int) and size <= 4 and size >= 1):
      print "unknown counter size"
      return
      
    self.__sendCommand("SETCNTRMODE " + str(cntr) + " " + str(mode) + " " + str(size))
    return
    
  # --------------------------------------------------------------------------
  def getCounterMode(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("GETCNTRMODE " + str(cntr))
    modeString = string.split(str(self.__readResponse()))
    
    counterMode = []
    for i in range(len(modeString)):
      counterMode.append(int(modeString[i]))
    
    return counterMode
    
  # --------------------------------------------------------------------------
  def enableCounter(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("ENABLECNTR " + str(cntr) + " " + self.ON)
    return
    
  # --------------------------------------------------------------------------
  def disableCounter(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("ENABLECNTR " + str(cntr) + " " + self.OFF)
    return
    
  # --------------------------------------------------------------------------
  def clearCounter(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("CLRCNTR " + str(cntr))
    return
    
  # --------------------------------------------------------------------------
  def readCounter(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("RDCNTR " + str(cntr))
    return int(self.__readResponse(), 16)
    
  # --------------------------------------------------------------------------
  def loadCounter(self, cntr=1):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
    self.__sendCommand("LOADCNTR " + str(cntr))
    return int(self.__readResponse(), 16)
    
  # --------------------------------------------------------------------------
  def writeCounter(self, cntr=1, data=0):
    if not (isinstance(cntr, int) and cntr <= 2 and cntr >= 1):
      print "unknown counter"
      return 
      
    if not isinstance(data, int):
      print "data must be given as integer number"
      return
      
    self.__sendCommand("WRCNTR " + str(cntr) + " %X" %(data & 0xffffffff))
    return
   
  # --------------------------------------------------------------------------
  def getMAC(self):
    self.__sendCommand("GETMAC")
    return str(self.__readResponse())
    
  # --------------------------------------------------------------------------
  def setIP(self, ip):
    if not isinstance(ip, basestring):
      print "IP must be given as a string."
      return
    
    if len(ip) > 15:
      print "IP too long."
      return
    
    if len(ip) < 7:
      print "IP too short."
      return
    
    self.__sendCommand("SETIP " + ip)
    return
    
  # --------------------------------------------------------------------------
  def getIP(self):
    self.__sendCommand("GETIP")
    return str(self.__readResponse())

  # --------------------------------------------------------------------------
  def setNetmask(self, mask):
    if not isinstance(mask, basestring):
      print "Netmask must be given as a string."
      return
    
    if len(mask) > 15:
      print "Netmask too long."
      return
    
    if len(mask) < 7:
      print "Netmask too short."
      return
    
    self.__sendCommand("SETNETMASK " + mask)
    return
    
  # --------------------------------------------------------------------------
  def getNetmask(self):
    self.__sendCommand("GETNETMASK")
    return str(self.__readResponse())

  # --------------------------------------------------------------------------
  def setGateway(self, gw):
    if not isinstance(gw, basestring):
      print "Gateway must be given as a string."
      return
    
    if len(gw) > 15:
      print "Gateway too long."
      return
    
    if len(gw) < 7:
      print "Gateway too short."
      return
    
    self.__sendCommand("SETGW " + gw)
    return
    
  # --------------------------------------------------------------------------
  def getGateway(self):
    self.__sendCommand("GETGW")
    return str(self.__readResponse())
    
    
  # --------------------------------------------------------------------------
  def setLED(self, r=0, g=0, b=0):
    self.__sendCommand("LED %d %d %d" %(r, g, b))
    return
    
    
    
    
    
    