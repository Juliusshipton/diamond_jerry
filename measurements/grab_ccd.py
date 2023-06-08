# import matplotlib.pyplot as plt
import numpy as np
from pypylon import pylon as py
import hardware.api as ha
import time

exposure_offset = 15 #in us (intrinsic to the ccd, for trigger width only)
exposure_start_delay_12 = 21 #in us
exposure_start_delay_8 = 17 #in us
'''
Binning:
1:(1200, 1920)
2:(600, 960)
3:(400,640)
4:(300, 480)


'''

#if using trigger width there are propagation delay from both falling and rising edge
def grab_ccd():
    tlf = py.TlFactory.GetInstance()
    devices = tlf.EnumerateDevices()
    #print(devices[0].GetModelName(), devices[0].GetSerialNumber())


    # the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
    #to open the camera need to tell transport layer to create a device
    cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
    cam.Open()

    # to get consistant results it is always good to start from "power-on" state
    cam.UserSetSelector = "Default"
    cam.UserSetLoad.Execute()
    
    cam.ExposureTime = 10000
    cam.StartGrabbing(py.GrabStrategy_OneByOne)
    res = cam.RetrieveResult(5000, py.TimeoutHandling_ThrowException)#cam.GrabOne(1000)
    img = res.Array
    #print(time.time(),img.shape) #gives array dimensions (x,y,3),img.size gives number of pixels
    np.savetxt('ccd_raw.txt', img)
    cam.Close()
    return

def grab_ccd_triggered(cam, exposure, wait):
    # start_time=time.time()
    # tlf = py.TlFactory.GetInstance()
    # devices = tlf.EnumerateDevices()
    # print(devices[0].GetModelName(), devices[0].GetSerialNumber())

    # the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
    # to open the camera need to tell transport layer to create a device
    # cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
    # cam.Open()
    # ha.PulseGenerator().Night()#must be night before trigger mode is on
    # to get consistant results it is always good to start from "power-on" state
    # cam.UserSetSelector = "Default"
    # cam.UserSetLoad.Execute()
    # cam.AcquisitionMode.SetValue('SingleFrame')
    # cam.ExposureAuto.SetValue('Off')
    # cam.TriggerSelector.SetValue('FrameStart')    
    # cam.TriggerMode.SetValue("On")
    # cam.TriggerSource.SetValue("Line1")
    # cam.TriggerActivation.SetValue('RisingEdge')
    # cam.ExposureMode.SetValue('TriggerWidth')    
    cam.StartGrabbing()
    
    ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2' , 'mw_x'],exposure*10**3),([],wait*10**3)], loop=False) #we need longer initialization to attain enough Fluroscence counts
    if ha.PulseGenerator().checkUnderflow():
        logging.getLogger().info('Underflow in pulse generator.')
        ha.PulseGenerator().Night()
        ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2' , 'mw_x'],exposure*10**3),([],wait*10**3)], loop=False)
        print('underflow before grabbing')
        print(time.time())

    while cam.IsGrabbing():
        grabResult = cam.RetrieveResult(10000,py.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            # Access the image data
            image = grabResult.Array
            break
    #print('close{}'.format(time.time()-start_time))
    grabResult.Release()
    cam.StopGrabbing()
    # cam.Close()
    ha.PulseGenerator().Night()
    
    return image

def grab_ccd_triggered2(cam, exposure, wait):
    cam.StartGrabbing(1)
    
    ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2','mw_x'],exposure*10**3-exposure_offset*10**3),(['mw_x'],exposure_offset*10**3),([],wait*10**3)]) #we need longer initialization to attain enough Fluroscence counts
    # if ha.PulseGenerator().checkUnderflow():
        # logging.getLogger().info('Underflow in pulse generator.')
        # ha.PulseGenerator().Night()
        # ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2' , 'mw_x'],exposure*10**3),([],wait*10**3)])
        # print('underflow before grabbing')
        # print(time.time())

    # while cam.IsGrabbing():
    grabResult = cam.RetrieveResult(10000,py.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        # Access the image data
        image = grabResult.Array
    else:
        print('grab failed')
        return 101
    #print('close{}'.format(time.time()-start_time))
    grabResult.Release()
    cam.StopGrabbing()
    # cam.Close()
    ha.PulseGenerator().Night()
    
    return image

def grab_ccd_fast(cam, exposure, wait):
    cam.StartGrabbing(1)
    
    ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),(['mw_x'],exposure*10**3)],loop=False) #we need longer initialization to attain enough Fluroscence counts

    grabResult = cam.RetrieveResult(10000,py.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        # Access the image data
        image = grabResult.Array
    else:
        print('grab failed')
        return 101

    grabResult.Release()
    cam.StopGrabbing()

    ha.PulseGenerator().Night()
    
    return image

def grab_ccd_multiple(cam, exposure, wait, nacc):
    # tlf = py.TlFactory.GetInstance()
    # devices = tlf.EnumerateDevices()
    # print(devices[0].GetModelName(), devices[0].GetSerialNumber())

    # the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
    # to open the camera need to tell transport layer to create a device
    # cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
    # cam.Open()
    ha.PulseGenerator().Night()#must be night before trigger mode is on
    # cam.ExposureAuto.SetValue('Off')
    # cam.TriggerSelector.SetValue('FrameStart')    
    # cam.TriggerMode.SetValue("On")
    # cam.TriggerSource.SetValue("Line1")
    # cam.TriggerActivation.SetValue('RisingEdge')
    # cam.ExposureMode.SetValue('Timed')    
    # cam.ExposureTime = exposure
    cam.StartGrabbing(py.GrabStrategy_OneByOne)
    ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),(['mw_x'],exposure*10**3)]) #we need longer initialization to attain enough Fluroscence counts
    count = 0
    while cam.IsGrabbing() and count<nacc:
        grabResult = cam.RetrieveResult(10000,py.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            if count<1:
                image=np.array(grabResult.Array, dtype=np.int32)
            else:
                image+=np.array(grabResult.Array, dtype=np.int32)
            count+=1
        else:
            print('grab failed')
            return 101

    grabResult.Release()
    cam.StopGrabbing()

    ha.PulseGenerator().Night()
    return image

def grab_ccd_multipleSing(cam, exposure, wait, nacc):
    # tlf = py.TlFactory.GetInstance()
    # devices = tlf.EnumerateDevices()
    # print(devices[0].GetModelName(), devices[0].GetSerialNumber())

    # the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
    # to open the camera need to tell transport layer to create a device
    # cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
    # cam.Open()
    ha.PulseGenerator().Night()#must be night before trigger mode is on
    # cam.ExposureAuto.SetValue('Off')
    # cam.TriggerSelector.SetValue('FrameStart')    
    # cam.TriggerMode.SetValue("On")
    # cam.TriggerSource.SetValue("Line1")
    # cam.TriggerActivation.SetValue('RisingEdge')
    # cam.ExposureMode.SetValue('Timed')    
    # cam.ExposureTime = exposure
    cam.StartGrabbing(py.GrabStrategy_OneByOne)
    ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),(['mw_x'],exposure*10**3)]) #we need longer initialization to attain enough Fluroscence counts
    count = 0
    while cam.IsGrabbing() and count<nacc:
        grabResult = cam.RetrieveResult(10000,py.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            # Access the image data
            if count<1:
                image=np.array(grabResult.Array, dtype=np.int32)
            else:
                image+=np.array(grabResult.Array, dtype=np.int32)
            # print()
            count+=1
        else:
            print('grab failed')
            return 101

    grabResult.Release()
    cam.StopGrabbing()

    ha.PulseGenerator().Night()
    
    return image

def grab_ccd_multiple_ref(cam, exposure, wait, nacc):
    # tlf = py.TlFactory.GetInstance()
    # devices = tlf.EnumerateDevices()
    # print(devices[0].GetModelName(), devices[0].GetSerialNumber())

    # the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
    # to open the camera need to tell transport layer to create a device
    # cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
    # cam.Open()
    ha.PulseGenerator().Night()#must be night before trigger mode is on
    cam.AcquisitionMode.SetValue('Continuous')
    cam.ExposureAuto.SetValue('Off')
    cam.TriggerSelector.SetValue('FrameStart')    
    cam.TriggerMode.SetValue("On")
    cam.TriggerSource.SetValue("Line1")
    cam.TriggerActivation.SetValue('RisingEdge')
    cam.ExposureMode.SetValue('Timed')    
    cam.ExposureTime = exposure
    cam.MaxNumBuffer = 2
    cam.OutputQueueSize = 2
    count = 0
    cam.StartGrabbing(py.GrabStrategy_OneByOne)
    # time.sleep(0.5)
    # if cam.GetGrabResultWaitObject().Wait(0):
        # print("Grab results wait in the output queue.")
    while cam.IsGrabbing() and count<nacc:
        ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),(['mw_x'],exposure*10**3),([],wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),([],exposure*10**3)],loop=False) #we need longer initialization to attain enough Fluroscence counts
        try:
            grabResult1 = cam.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
            grabResult2 = cam.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
            if grabResult1.GrabSucceeded():
                refimage = np.array(grabResult2.Array, dtype=np.float32)
                if count<1:
                    image=np.array(grabResult1.Array, dtype=np.float32)
                    image-=refimage
                    image = 1-image/refimage
                else:
                    image+=np.array(grabResult1.Array, dtype=np.float32)
                    image-=refimage
                    image = 1-image/refimage
            grabResult1.Release()
            grabResult2.Release()
            count+=1
        except:
            ha.PulseGenerator().Sequence([([], wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),(['mw_x'],exposure*10**3),([],wait*10**3),(['mw_2'],exposure_start_delay_12*10**3),([],exposure*10**3)],loop=False) #we need longer initialization to attain enough Fluroscence counts
            grabResult1 = cam.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
            grabResult2 = cam.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
            if grabResult1.GrabSucceeded():
                refimage = np.array(grabResult2.Array, dtype=np.float32)
                if count<1:
                    image=np.array(grabResult1.Array, dtype=np.float32)
                    image-=refimage
                    image = 1-image/refimage
                else:
                    image+=np.array(grabResult1.Array, dtype=np.float32)
                    image-=refimage
                    image = 1-image/refimage
            grabResult1.Release()
            grabResult2.Release()
            count+=1

    cam.StopGrabbing()
    ha.PulseGenerator().Night()
    return image

