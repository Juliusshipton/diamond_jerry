import numpy as np
import random
import cPickle

from traits.api import SingletonHasTraits, Trait, Instance, Property, String, Range, Float, Int, Bool, Array, Enum, Button, on_trait_change, cached_property, Code, List, NO_COMPARE, Str
from traitsui.api import View, Item, HGroup, VGroup, VSplit, Tabbed, EnumEditor, TextEditor, Group
from enable.api import Component, ComponentEditor
from chaco.api import ArrayPlotData, Plot, Spectral, PlotLabel, jet, CMapImagePlot
from chaco.tools.cursor_tool import CursorTool2D
#customized zoom tool to keep aspect ratio
from tools.utility import AspectZoomTool

from traitsui.file_dialog import save_file, open_file
from traitsui.menu import Action, Menu, MenuBar
from grab_ccd import grab_ccd_triggered, grab_ccd_triggered2

import time
import threading
import logging

from tools.emod import ManagedJob
from tools.cron import CronDaemon, CronEvent

import hardware.api as ha

from analysis import fitting

from tools.utility import GetSetItemsHandler, GetSetItemsMixin
import matplotlib.pyplot as plt
from pypylon import pylon as py


x_pixel = 820
x_min_pixel = 325
y_pixel = 1140
y_min_pixel = 588

class CCDODMRHandler(GetSetItemsHandler):

    def saveLinePlot(self, info):
        filename = save_file(title='Save Line Plot')
        if filename is '':
            return
        else:
            if filename.find('.png') == -1:
                filename = filename + '.png'
            info.object.save_line_plot(filename)

    def saveCCDPlot(self, info):
        filename = save_file(title='Save CCD Plot')
        if filename is '':
            return
        else:
            if filename.find('.png') == -1:
                filename = filename + '.png'
            info.object.save_ccd_plot(filename)
    
    def saveAll(self, info):
        filename = save_file(title='Save All')
        if filename is '':
            return
        else:
            info.object.save_all(filename)
    #'''starts here'''        
    def loadcomp(self, info):
        filename = open_file(title='Load Comparison')
        if filename is '':
            return
        else:
            info.object.load_comp(filename)
    #'''ends here'''


class CCDODMR_test(ManagedJob, GetSetItemsMixin):
    """Provides ODMR measurements."""
    '''
    goals: movable cursor which can provide the current index of the point it is pointing to.
            An image plot for ccd and a line plot of ODMR for a selected pixel point
    '''
    
    # starting and stopping
    keep_data = Bool(False) # helper variable to decide whether to keep existing data
    resubmit_button = Button(label='resubmit', desc='Submits the measurement to the job manager. Tries to keep previously acquired data. Behaves like a normal submit if sequence or time bins have changed since previous run.')    
    
    # measurement parameters
    power = Range(low= -100., high=25., value= -10, desc='Power [dBm]', label='Power [dBm]', mode='text', auto_set=False, enter_set=True)
    frequency_begin = Range(low=1, high=20e9, value=2.85e9, desc='Start Frequency [Hz]', label='Begin [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    frequency_end = Range(low=1, high=20e9, value=2.90e9, desc='Stop Frequency [Hz]', label='End [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    frequency_delta = Range(low=1e-3, high=20e9, value=1e6, desc='frequency step [Hz]', label='Delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    laser = Range(low=1., high=10000., value=300., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    seconds_per_point = Range(low=1e-6, high=1, value=10e-3, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
    stop_time = Range(low=1., value=np.inf, desc='Time after which the experiment stops by itself [s]', label='Stop time [s]', mode='text', auto_set=False, enter_set=True)
       
    # control data fitting
    perform_fit = Bool(False, label='perform fit')
    number_of_resonances = Trait('auto', String('auto', auto_set=False, enter_set=True), Int(10000., desc='Number of Lorentzians used in fit', label='N', auto_set=False, enter_set=True))
    threshold = Range(low= -99, high=99., value= -50., desc='Threshold for detection of resonances [%]. The sign of the threshold specifies whether the resonances are negative or positive.', label='threshold [%]', mode='text', auto_set=False, enter_set=True)
    
    
    
    # fit result
    fit_parameters = Array(value=np.array((np.nan, np.nan, np.nan, np.nan)))
    fit_frequencies = Array(value=np.array((np.nan,)), label='frequency [Hz]') 
    fit_line_width = Array(value=np.array((np.nan,)), label='line_width [Hz]') 
    fit_contrast = Array(value=np.array((np.nan,)), label='contrast [%]')

    #ccd control
    ccd_single_shot = Button(label='single')
    ccd_con_shot = Button(label='continuous')
    ccdstop = Bool(False, label='stop continuous')
    tlf = py.TlFactory.GetInstance()
    devices = tlf.EnumerateDevices()
    # the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
    #to open the camera need to tell transport layer to create a device
    cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
    
    exposure = Range(low= 20, high=10000000, value= 3000, desc='ccd exposure [us]', label='ccd exposure [us]', mode='text', auto_set=False, enter_set=True)
    ccdwait = Range(low= 5, high=10000000, value= 50, desc='ccd wait [us]', label='ccd wait [us]', mode='text', auto_set=False, enter_set=True)

    # measurement data    
    frequency = Array()
    #counts = Array()
    counts_ccd = Array()
    counts_ccd_data = Array()
    counts_ccd_line = Array()
    run_time = Float(value=0.0, desc='Run time [s]', label='Run time [s]')
    mix = Int(value=0, label='mix')
        
    # plotting
    line_label = Instance(PlotLabel)
    line_data = Instance(ArrayPlotData)
    matrix_data = Instance(ArrayPlotData)
    line_plot = Instance(Plot, editor=ComponentEditor())
    ccd_plot = Instance(Plot, editor=ComponentEditor())
    scan_plot = Instance( CMapImagePlot )
    thresh_high = Trait( 'auto', Str('auto'), Float(10000.), desc='High Limit of image plot', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
    thresh_low = Trait( 'auto', Str('auto'), Float(0.), desc='Low Limit of image plot', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
    colormaps = Enum('jet')

    # scanner position
    y = Range(low=y_min_pixel, high=y_pixel, value=int((y_pixel+y_min_pixel)/2), desc='y [Pixel]', label='y [Pixel]', mode='slider')
    x = Range(low=x_min_pixel, high=x_pixel, value=int((x_pixel+x_min_pixel)/2), desc='x [Pixel]', label='x [Pixel]', mode='slider')
    cursor = Instance( CursorTool2D )
    cursor_position = Property(depends_on=['x','y'])#,'z','constant_axis'])
    
    
    def __init__(self):
        super(CCDODMR_test, self).__init__()
        self._create_ccd_plot()
        self._create_line_plot()
        self.sync_trait('cursor_position', self.cursor, 'current_position')
        self.sync_trait('thresh_high', self.scan_plot.value_range, 'high_setting')
        self.sync_trait('thresh_low', self.scan_plot.value_range, 'low_setting')
        self.on_trait_change(self.scan_plot.request_redraw, 'thresh_high,thresh_low', dispatch='ui')
        self.on_trait_change(self._update_line_data_index, 'frequency', dispatch='ui')
        self.on_trait_change(self._update_line_data_value, 'counts_ccd_data,x,y', dispatch='ui')
        self.on_trait_change(self._update_line_data_fit, 'fit_parameters', dispatch='ui')
        self.on_trait_change(self._update_ccd_data_value, 'counts_ccd', dispatch='ui')
        #self.on_trait_change(self._update_matrix_data_index, 'n_lines,frequency', dispatch='ui')
        self.on_trait_change(self._update_fit, 'counts_ccd_line,x,y,perform_fit,number_of_resonances,threshold', dispatch='ui')

        
    @cached_property
    def _get_cursor_position(self): #update the cursor when moving x/y
        return self.x, self.y
    
    def _set_cursor_position(self, position): #update x/y when moving cursor
        self.x, self.y = (int(position[0]),int(position[1]))
            
    def _frequency_default(self):
        freq = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)
        return freq
            
    def _counts_ccd_default(self):
        return np.zeros((600, 600))
    
    def _counts_ccd_data_default(self):
        return np.zeros((len(self.frequency), 600, 600))
    
    def _counts_default(self):
        return np.zeros(self.frequency.shape)
        
    def _counts_ccd_line_default(self):
        return np.zeros(self.frequency.shape)
        
    # data acquisition                
    # def freq_mixer2(self, freq, mix):
        # a = np.copy(freq)
        # random.seed(mix)
        # b = random.choice(range(0,len(a)))
        # c = np.array(())
        # if len(a[:b])>len(a[b:]):
            # for i in range(len(a[b:])):
                # c = np.append(c,a[:b][i])
                # c = np.append(c,a[b:][i])
            # c = np.append(c,a[:b][len(a[b:]):])
        # elif len(a[:b]) == len(a[b:]):
            # for i in range(len(a[b:])):
                # c = np.append(c,a[:b][i])
                # c = np.append(c,a[b:][i])
        # else:
            # for i in range(len(a[:b])):
                # c = np.append(c,a[b:][i])
                # c = np.append(c,a[:b][i])
            # c = np.append(c,a[b:][len(a[:b]):])
        # return c
    
    # def counts_resolve2(self, counts, mix):
        # a = np.copy(counts)
        # random.seed(mix)
        # b = random.choice(range(0,len(a)))
        # c = np.array(())
        # d = np.array(())
        # if b < len(a[b:]) and b != 0:
            # for i in range(0,2*b,2):
                # c = np.append(c,a[i+1])
                # d = np.append(d,a[i])
            # d = np.append(d,a[2*b:])
            # c = np.append(c,d)
            # return c
        # elif b == 0:
            # return a
        # elif len(a[b:]) == len(a[:b]):
            # for i in range(0,2*b,2):
                # c = np.append(c,a[i+1])
                # d = np.append(d,a[i])
            # c = np.append(d,c)
            # return c
        # else:
            # for i in range(0,2*len(a[b:]),2):
                # c = np.append(c,a[i+1])
                # d = np.append(d,a[i])
            # d = np.append(d,a[len(a[b:])*2:])
            # d = np.append(d,c)
            # c = d
            # return c
        
    def apply_parameters(self):
        """Apply the current parameters and decide whether to keep previous data."""
        frequency = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)
        if not self.keep_data or np.any(frequency != self.frequency):
            self.frequency = frequency
            self.counts_ccd_data = np.zeros(shape=(len(self.frequency), x_pixel-x_min_pixel,y_pixel-y_min_pixel))#original:1200x1920
            self.run_time = 0.0
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.

    def _run(self):
        try:
            self.state = 'run'
            self.apply_parameters()

            if self.run_time >= self.stop_time:
                self.state = 'done'
                return
            
                
            n = len(self.frequency)
            time.sleep(0.5)
            self.cam.Open()
            # ha.PulseGenerator().Light()#must be night before trigger mode is on
            # to get consistant results it is always good to start from "power-on" state
            self.cam.UserSetSelector = "Default"
            self.cam.UserSetLoad.Execute()
            self.cam.AcquisitionMode.SetValue('SingleFrame')
            self.cam.ExposureAuto.SetValue('Off')
            self.cam.TriggerSelector.SetValue('FrameStart')    
            self.cam.TriggerMode.SetValue("On")
            self.cam.TriggerSource.SetValue("Line1")
            self.cam.TriggerActivation.SetValue('RisingEdge')
            self.cam.ExposureMode.SetValue('TriggerWidth')    

            self.counts_ccd = grab_ccd_triggered2(self.cam, self.exposure, self.ccdwait)[x_min_pixel:x_pixel,y_min_pixel:y_pixel]
            counts_ccd = np.zeros((n,x_pixel-x_min_pixel,y_pixel-y_min_pixel)) #original:1200x1920
            while self.run_time < self.stop_time:
                start_time = time.time()
                random.seed(int(time.time()))
                #self.mix = random.choice(range(0,1000))
                #self.frequency = self.freq_mixer2(self.freq_mixer2(self.freq_mixer2(self.frequency, self.mix), int(self.mix/2)), int(self.mix/3))
                
                for i in range(n):
                    ha.Microwave().setOutput(self.power, self.frequency[i])
                    counts_ccd[i] = grab_ccd_triggered2(self.cam, self.exposure, self.ccdwait)[x_min_pixel:x_pixel,y_min_pixel:y_pixel]#+np.random.normal(127, 9, size=(1200, 1920))#self.laser, self.exposure, self.wait)
                    if threading.currentThread().stop_request.isSet():
                        break
                    time.sleep(0.1)
                    
                if threading.currentThread().stop_request.isSet():
                    break

                self.counts_ccd_data += counts_ccd
                self.trait_property_changed('counts_ccd_data', self.counts_ccd_data)
                self.run_time += time.time() - start_time
            self.cam.Close()
            if self.run_time < self.stop_time:
                self.state = 'idle'
            else:
                self.state = 'done'

            ha.Microwave().setOutput(None, self.frequency_begin)
            ha.PulseGenerator().Light()
        except:
            logging.getLogger().exception('Error in ccdodmr.')
            self.state = 'error'
        finally:
            ha.Microwave().setOutput(None, self.frequency_begin)

    def _update_fit(self):
        if self.perform_fit:
            N = self.number_of_resonances 
            if N != 'auto':
                N = int(N)
            try:
                p = fitting.fit_multiple_lorentzians(self.frequency, self.line_data['counts_ccd_line'], N, threshold=self.threshold * 0.01)
            except Exception:
                logging.getLogger().debug('ODMR fit failed.', exc_info=True)
                p = np.nan * np.empty(4)
        else:
            p = np.nan * np.empty(4)        
        self.fit_parameters = p
        self.fit_frequencies = p[1::3]
        self.fit_line_width = p[2::3]
        N = len(p) / 3
        contrast = np.empty(N)
        c = p[0]
        pp = p[1:].reshape((N, 3))
        for i, pi in enumerate(pp):
            a = pi[2]
            g = pi[1]
            A = np.abs(a / (np.pi * g))
            if a > 0:
                contrast[i] = 100 * A / (A + c)
            else:
                contrast[i] = 100 * A / c
        self.fit_contrast = contrast
    
    
    #plotting
        
    def _create_line_plot(self):
        line_data = ArrayPlotData(frequency=np.array((0., 1.)), counts_ccd_line=np.array((0., 0.)), fit=np.array((0., 0.))) 
        line_plot = Plot(line_data, padding=8, padding_left=64, padding_bottom=32)
        line_plot.plot(('frequency', 'counts_ccd_line'), style='line', color='blue')
        line_plot.index_axis.title = 'Frequency [MHz]'
        line_plot.value_axis.title = 'Fluorescence counts'
        line_label = PlotLabel(text='', hjustify='left', vjustify='bottom', position=[64, 128])
        line_plot.overlays.append(line_label)
        self.line_label = line_label
        self.line_data = line_data
        self.line_plot = line_plot
                
    def _create_ccd_plot(self):
        ccd_data = ArrayPlotData(image=np.zeros((x_pixel-x_min_pixel, y_pixel-y_min_pixel)))#original:1200x1920
        ccd_plot = Plot(ccd_data, width=500, height=500, resizable='hv', aspect_ratio=1.0,padding=8, padding_left=64, padding_bottom=32)
        ccd_plot.img_plot('image',  colormap=jet, xbounds=(x_min_pixel,x_pixel), ybounds=(y_min_pixel,y_pixel), name='image')
        image = ccd_plot.plots['image'][0]
        image.x_mapper.domain_limits = (0,x_pixel)
        image.y_mapper.domain_limits = (0,y_pixel)
        zoom = AspectZoomTool(image, enable_wheel=False)
        cursor = CursorTool2D(image, drag_button='left', color='white', marker_size=1.0, line_width=1.0 )
        image.overlays.append(cursor)
        image.overlays.append(zoom)
        self.cursor = cursor
        self.zoom = zoom
        self.scan_plot = image
        self.ccd_data = ccd_data
        self.ccd_plot = ccd_plot

    def _perform_fit_changed(self, new):
        plot = self.line_plot
        if new:
            plot.plot(('frequency', 'fit'), style='line', color='red', name='fit')
            self.line_label.visible = True
        else:
            plot.delplot('fit')
            self.line_label.visible = False
        plot.request_redraw()
    
    def _update_line_data_index(self):
        self.line_data.set_data('frequency', self.frequency * 1e-6)
        #self.counts_ccd = self._counts_ccd_default()
        

    def _update_line_data_value(self):
        self.line_data.set_data('counts_ccd_line', self.counts_ccd_data[:,self.x-x_min_pixel,self.y-y_min_pixel])
    
    def _update_line_data_fit(self):
        if not np.isnan(self.fit_parameters[0]):
            self.line_data.set_data('fit', fitting.NLorentzians(*self.fit_parameters)(self.frequency))
            p = self.fit_parameters
            f = p[1::3]
            w = p[2::3]
            N = len(p) / 3
            contrast = np.empty(N)
            c = p[0]
            pp = p[1:].reshape((N, 3))
            for i, pi in enumerate(pp):
                a = pi[2]
                g = pi[1]
                A = np.abs(a / (np.pi * g))
                if a > 0:
                    contrast[i] = 100 * A / (A + c)
                else:
                    contrast[i] = 100 * A / c
            s = ''
            for i, fi in enumerate(f):
                s += 'f %i: %.6e Hz, FWHM %.3e Hz, contrast %.1f%%\n' % (i + 1, fi, w[i]*2, contrast[i])
            self.line_label.text = s

    def _update_ccd_data_value(self):
        self.ccd_data.set_data('image', self.counts_ccd)

    # def _update_matrix_data_index(self):
        # if self.n_lines > self.counts_matrix.shape[0]:
            # self.counts_matrix = np.vstack((self.counts_matrix, np.zeros((self.n_lines - self.counts_matrix.shape[0], self.counts_matrix.shape[1]))))
        # else:
            # self.counts_matrix = self.counts_matrix[:self.n_lines]
        # self.matrix_plot.components[0].index.set_data((self.frequency[0] * 1e-6, self.frequency[-1] * 1e-6), (0.0, float(self.n_lines)))

    # saving data
    
    def save_line_plot(self, filename):
        plt.plot(self.frequency, self.line_data['counts_ccd_line'])
        plt.xlim(self.frequency[0],self.frequency[-1])
        plt.ylim(np.min(self.line_data['counts_ccd_line']),np.max(self.line_data['counts_ccd_line']))
        plt.savefig(filename)
        #self.save_figure(self.line_plot, filename)

    def save_ccd_plot(self, filename):
        #self.save_figure(self.ccd_plot, filename)
        plt.imshow(X=self.ccd_data['image'], interpolation="none",origin="lower")
    
    def save_all(self, filename):
        plt.figure()
        plt.plot(self.frequency, self.line_data['counts_ccd_line'])
        plt.xlim(self.frequency[0],self.frequency[-1])
        plt.ylim(np.min(self.line_data['counts_ccd_line']),np.max(self.line_data['counts_ccd_line']))
        plt.savefig(filename+'CCDODMR_Line_Plot.png')
        #self.save_line_plot(filename + '_CCDODMR_Line_Plot.png')
        #self.save_ccd_plot(filename + '_CCDODMR_Matrix_Plot.png')
        self.save(filename + '_CCDODMR.pys')
        #data = cPickle.load(open(filename + '_CCDODMR.pys','rb'))
        plt.close()
        plt.figure()
        counts = self.line_data['counts_ccd_line']
        frequency = self.frequency
        output = np.column_stack((frequency,counts))
        plt.imshow(X=self.ccd_data['image'], interpolation="none",origin="lower")
        plt.savefig(filename+'CCD_Plot.png')
        plt.close()
        # with open('test.txt', 'w') as f:
            # np.save(f, output)
        #np.save(filename + '.txt', output)
        
    # react to GUI events

    def submit(self):
        """Submit the job to the JobManager."""
        self.keep_data = False
        ManagedJob.submit(self)

    def resubmit(self):
        """Submit the job to the JobManager."""
        self.keep_data = True
        ManagedJob.submit(self)

    def _resubmit_button_fired(self):
        """React to start button. Submit the Job."""
        self.resubmit() 
        
    def _ccd_single_shot_fired(self):
        self.cam.Open()
        self.cam.UserSetSelector = "Default"
        self.cam.UserSetLoad.Execute()
        self.cam.AcquisitionMode.SetValue('SingleFrame')
        self.cam.ExposureAuto.SetValue('Off')
        self.cam.TriggerSelector.SetValue('FrameStart')    
        self.cam.TriggerMode.SetValue("On")
        self.cam.TriggerSource.SetValue("Line1")
        self.cam.TriggerActivation.SetValue('RisingEdge')
        self.cam.ExposureMode.SetValue('TriggerWidth')    
        self.counts_ccd = grab_ccd_triggered2(self.cam, self.exposure, self.wait)[x_min_pixel:x_pixel,y_min_pixel:y_pixel]
        self.cam.Close()
        return

    # def _ccd_con_shot_fired(self):
        # '''not implemented yet'''
        # self.cam.Open()
        # self.cam.UserSetSelector = "Default"
        # self.cam.UserSetLoad.Execute()
        # self.cam.AcquisitionMode.SetValue('Continuous')
        # self.cam.ExposureAuto.SetValue('Off')
        # self.cam.TriggerSelector.SetValue('FrameStart')    
        # self.cam.TriggerMode.SetValue("On")
        # self.cam.TriggerSource.SetValue("Line1")
        # self.cam.TriggerActivation.SetValue('RisingEdge')
        # self.cam.ExposureMode.SetValue('TriggerWidth')    
        # self.cam.StartGrabbing(py.GrabStrategy_OneByOne)  
        # ha.PulseGenerator().Sequence([([], self.ccdwait*10**3),(['mw_2' , 'mw_x'],self.exposure*10**3),([],self.ccdwait*10**3)]) #we need longer initialization to attain enough Fluroscence counts        
        # while self.cam.IsGrabbing():
            # if self.stop:
                # break
            # try:
                # grabResult = self.cam.RetrieveResult(10000, py.TimeoutHandling_ThrowException)
                # if grabResult.GrabSucceeded():
                    # self.counts_ccd = grabResult.Array
            # except:
                # print('timeout error')
                # return
        # self.cam.StopGrabbing()
        # self.cam.Close()
        # grabResult.Release()
        # return
        
    traits_view = View(VSplit(HGroup(Item('submit_button',show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('ccd_single_shot', show_label=False),
                                     Item('ccd_con_shot', show_label=False),
                                     Item('ccdstop'),
                                     Item('priority', enabled_when='state != "run"'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('power', width= -40, enabled_when='state != "run"'),
                                            Item('frequency_begin', width= -80, enabled_when='state != "run"'),
                                            Item('frequency_end', width= -80, enabled_when='state != "run"'),
                                            Item('frequency_delta', width= -80, enabled_when='state != "run"'),
                                            Item('seconds_per_point', width= -80, enabled_when='state != "run"'),
                                            ),
                                     HGroup(Item('perform_fit'),
                                            Item('number_of_resonances', width= -60),
                                            Item('threshold', width= -60),
                                            ),
                                     # HGroup(Item('fit_contrast', style='readonly'),
                                            # Item('fit_line_width', style='readonly'),
                                            # Item('fit_frequencies', style='readonly'),
                                            # ),
                                     label='ODMR control'
                                     ),
                                      VGroup(HGroup(Item('thresh_low', width=-80),
                                             Item('thresh_high', width=-80),
                                             ),
                                             HGroup(Item('exposure', width=-80),
                                             Item('ccdwait', width=-80),
                                             ),
                                             label='CCD control'
                                             ),
                                     ),
                             Tabbed(Item('ccd_plot', show_label=False, resizable=True),
                                    Item('line_plot', show_label=False, resizable=True),
                                    ),
                              VGroup(Item('x', enabled_when='state != "run" or (state == "run" and constant_axis == "x")'),
                              Item('y', enabled_when='state != "run" or (state == "run" and constant_axis == "y")'),
                              ),
                              ),
                             menubar=MenuBar(Menu(Action(action='saveLinePlot', name='SaveLinePlot (.png)'),
                                              Action(action='saveCCDPlot', name='SaveCCDPlot (.png)'),
                                              Action(action='save', name='Save (.pyd or .pys)'),
                                              Action(action='saveAll', name='Save All (.png+.pys)'),
                                              Action(action='export', name='Export as Ascii (.asc)'),
                                              Action(action='load', name='Load'),
                                              Action(action='_on_close', name='Quit'),
                                              name='File')),
                       title='CCD ODMR test', width=900, height=500, buttons=[], resizable=True, handler=CCDODMRHandler
                       )

    get_set_items = ['frequency', 'counts_ccd', 'counts_ccd_data',
                     'run_time','perform_fit',
                     'fit_parameters', 'fit_contrast', 'fit_line_width', 'fit_frequencies',
                     'power', 'frequency_begin', 'frequency_end', 'frequency_delta',
                    'laser', 'wait', 'seconds_per_point',
                     'number_of_resonances', 'threshold',
                      'stop_time', 
                     '__doc__']


if __name__ == '__main__':

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().info('Starting logger.')

    from tools.emod import JobManager
    JobManager().start()

    o = CCDODMR()
    o.edit_traits()
    
    
