import time
import serial
import string



class QDM():
    """ Gives an interface to the Quantum Diamond Magnetometer. """

    VCP = 'VCP'
    __contype = VCP

    IDN = ""

    ON = "1"
    OFF = "0"
    HIGH = "1"
    LOW = "0"

    # linux:   address = '/dev/ttyUSB0'
    # windows: address = 'COM3'
    def __init__(self, interface=VCP, address='COM6'):
        self.__contype = interface

        if self.__contype == self.VCP:
            self.ser = serial.Serial(
                port=address,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=5,
                xonxoff=0,
                rtscts=0,
                dsrdtr=0,
                writeTimeout=5
            )
            self.ser.close()
            self.ser.open()
            time.sleep(0.5)

        else:
            print "error: unknown interface"

    def __del__(self):
        if self.__contype == self.VCP:
            if self.ser.isOpen():
                self.ser.close()


    # low level functionality


    def sendCommand(self, cmd):
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

            if maxtries == 10:
                print "error: unable to send command: " + cmd

            self.ser.flushOutput()

        return

    def readResponse(self):
        out = ""

        if self.__contype == self.VCP:
            while self.ser.inWaiting() > 0:
                c = self.ser.read(1)
                if (c != '\n' and c != '\r'):
                    out += c

            self.ser.flushInput()

        return out.decode("utf-8")


    # command implementation


    def getIDN(self):
        self.sendCommand("*IDN?")
        return str(self.readResponse())

    def setFrequency(self, val):
        if not (val <= 4400.0 and val >= 34.375):
            print "frequency value out of range"
            return
        self.sendCommand("SETFREQ " + "%.3f" % val)
        return

    def setPower(self, val):
        if not (val <= 20.0 and val >= -43.0):
            print "power value out of range"
            return
        self.sendCommand("SETPWR " + "%f" % val)
        return

    def runODMR(self, start, stop, step):
        if not (start <= 4400.0 and start >= 34.375):
            print "start frequency value out of range"
            return
        if not (stop <= 4400.0 and stop >= 34.375):
            print "stop frequency value out of range"
            return
        if (start > stop):
            print "stop frequency must be larger than start frequency"
            return
        if not (isinstance(step, int) and step <= 65535 and step >= 1):
            print "step value out of range"
            return
        self.sendCommand("ODMRRUN " + "%f" % start + " %f" % stop + " %d" % step)
        return

    def readODMR(self, id, num=1):
        if not (isinstance(id, int) and id <= 1023 and id >= 0):
            print "id value out of range"
            return
        if not (isinstance(num, int) and num <= 1023 and num >= 1):
            print "num value out of range"
            return
        self.sendCommand("ODMRREAD %d %d" % (id, num))
        time.sleep(0.02)  # the received data packets are quite large and take a bit more time
        dataString = string.split(str(self.readResponse()))
        data = []
        for i in range(len(dataString)):
            data.append(int(dataString[i], 16))
        return data














