import numpy as np
from Motordriver import *
import time

class Motor():
    """Provides control of motor."""
    
    def __init__(self, address='/COM6', port=0):
    	self.driver = Motordriver(interface=address)
        self.port = port  # motor 0 is the one with the half wave plate
        self.position = 0.0
    """        
    def checkIDN():
      print "Check IDN"
      saveIDN = self.driver.getIDN()
      self.driver.setIDN("factorytest")
      idn = self.driver.getIDN()
      if idn != "factorytest":
        print "ERROR: IDN test failed"
       
      self.driver.setIDN(saveIDN)
      # return
    
    def checkZeroRun():
      print "Check ZERO RUN"
      self.driver.zeroMotor(self.port)
      time.sleep(15)
      
      self.position = self.driver.getPosition(self.port, self.driver.DEGREE)
      if position > 1e-5:
        print "ERROR: ZERORUN test failed for motor " + str(i)
      # return
    """  
    def moveAbsolute(self, angle):
        self.driver.moveToAbsolutePosition(self.port, angle, self.driver.DEGREE)
        while self.driver.isMoving(self.port):
            pass
        time.sleep(0.5)

    def checkPosition(self):
        self.position = self.driver.getPosition(self.port, self.driver.DEGREE)
        return self.position