"""
Dummy hardware classes for testing.
"""

import numpy as np
import logging
import time

class Scanner(  ):
    def getXRange(self):
        return (0.,100.)
    def getYRange(self):
        return (0.,100.)
    def getZRange(self):
        return (-20.,20.)
    def setx(self, x):
        pass
    def sety(self, y):
        pass
    def setz(self, z):
        pass
    def setPosition(self, x, y, z):
        """Move stage to x, y, z"""
        pass
    def scanLine(self, Line, SecondsPerPoint, return_speed=None):
        time.sleep(0.1)
        return (1000*np.sin(Line[0,:])*np.sin(Line[1,:])*np.exp(-Line[2,:]**2)).astype(int)
        #return np.random.random(Line.shape[1])

class Counter(  ):
    def configure(self, n, SecondsPerPoint, DutyCycle=0.8):
        x = np.arange(n)
        a = 100.
        c = 50.
        x0 = n/2.
        g = n/10.
        y = np.int32( c - a / np.pi * (  g**2 / ( (x-x0)**2 + g**2 )  ) )
        Counter._sweeps = 0
        Counter._y = y
    def run(self):
        time.sleep(1)
        Counter._sweeps+=1
        return np.random.poisson(Counter._sweeps*Counter._y)
    def clear(self):
        pass

class Microwave(  ):
    def setPower(self, power):
        logging.getLogger().debug('Setting microwave power to '+str(power)+'.')
    def setOutput(self, power, frequency):
        logging.getLogger().debug('Setting microwave to p='+str(power)+' f='+str(frequency)+'.')
    def initSweep(self, f, p):
        logging.getLogger().debug('Setting microwave to sweep between frequencies %e .. %e with power %f.'%(f[0],f[-1],p[0]))
    def resetListPos(self):
        pass

class PulseGenerator():
    def Sequence(self, sequence, loop=True):
        pass
    def Light(self):
        pass
    def Night(self):
        pass
    def Open(self):
        pass
    def High(self):
        pass
    def checkUnderflow(self):
        return False
        #return np.random.random()<0.1
        
class MagCoilControl():
    """Provides Control over the magnetic field of all three coils with HMP2030 and BipolarHMP2030"""
    def set_field_cartesian(self, bx, by, bz):
        pass
    
    def save_stop():
        pass
    
class Laser():
    """Provides control of the laser power."""
    voltage = 0.

class PowerMeter():
    """Provides an optical power meter."""
    power = 0.
    def getPower(self):
        """Return the optical power in Watt."""
        PowerMeter.power += 1
        return PowerMeter.power*1e-3

class Coil():
    def set_output(self,channel,current):
        pass

class RotationStage():
    def set_angle(self, angle):
        pass
    
class TimeTagger( ):

    class Pulsed( ):
        def __init__(self, n_bins, bin_width, n_slots, channel, shot_trigger, sequence_trigger=None):
            self.n_bins = n_bins
            self.n_slots = n_slots
            self.clear()
        def clear(self):
            n_slots = self.n_slots
            n_bins = self.n_bins       
            data = np.zeros((n_slots,n_bins))
            m0 = int(n_bins/5)
            m = float(n_bins-m0)
            M = np.arange(m, dtype=float)
            n = float(n_slots)
            k = n_slots/2
            for i in range(n_slots):
                """Rabi Data"""
                data[i,m0:] = 30*np.cos(3*2*np.pi*i/n)*np.exp(-5*M/m)+100
                """Hahn Data        
                data[i,m0:] = 30*np.exp(-9*i**2/n**2)*np.exp(-5*M/m)+100
                """
                """Hahn 3pi2 Data
                if i < k:
                    data[i,m0:] = 30*np.exp(-9*i**2/float(k**2))*np.exp(-5*M/m)+100
                else:
                    data[i,m0:] = -30*np.exp(-9*(i-k)**2/float(k**2))*np.exp(-5*M/m)+100
                """
                """T1 Data
                data[i,m0:] = 30*np.exp(-3*i/n)*np.exp(-5*M/m)+100
                """
            self.data = data
            self.counter = 1
        def setMaxCounts(self,arg):
            pass
        def ready(self):
            time.sleep(0.1)
            return True
        def getData(self):
            self.counter += 1
            return np.random.poisson(self.counter*self.data)
        def getCounts(self):
            return self.counter
        def start(self):
            pass
        def stop(self):
            pass

    class Countrate( ):
        def __init__(self, channel):
            self.rate = 0.
        def getData(self):
            self.rate += 1.
            return 1e5/(1+20./self.rate)
        def clear(self):
            pass
    
    class Counter( ):
        def __init__(self, channel, bins_per_point, length):
            self.channel = channel
            self.seconds_per_point = float(bins_per_point)/800000000
            self.length = length
        def getData(self):
            return np.random.random_integers(100000,120000, self.length)*self.seconds_per_point

