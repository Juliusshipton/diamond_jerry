import numpy as np
import random
import cPickle

from traits.api import SingletonHasTraits, Trait, Instance, Property, String, Range, Float, Int, Bool, Array, Enum, Button, on_trait_change, cached_property, Code, List, NO_COMPARE, Str
from traitsui.api import View, Item, HGroup, VGroup, VSplit, Tabbed, EnumEditor, TextEditor, Group
from enable.api import Component, ComponentEditor
from chaco.api import ArrayPlotData, Plot, Spectral, PlotLabel

from traitsui.file_dialog import save_file, open_file
from traitsui.menu import Action, Menu, MenuBar

import time
import threading
import logging

from tools.emod import ManagedJob
from tools.cron import CronDaemon, CronEvent

import hardware.api as ha

from analysis import fitting
# import analysis.fitting as fitting
from tools.utility import GetSetItemsHandler, GetSetItemsMixin

class ODMRHandler(GetSetItemsHandler):

    def saveLinePlot(self, info):
        filename = save_file(title='Save Line Plot')
        if filename is '':
            return
        else:
            if filename.find('.png') == -1:
                filename = filename + '.png'
            info.object.save_line_plot(filename)

    def saveMatrixPlot(self, info):
        filename = save_file(title='Save Matrix Plot')
        if filename is '':
            return
        else:
            if filename.find('.png') == -1:
                filename = filename + '.png'
            info.object.save_matrix_plot(filename)
    
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


class ODMRR(ManagedJob, GetSetItemsMixin):
    """Provides ODMR measurements."""

    # starting and stopping
    keep_data = Bool(False) # helper variable to decide whether to keep existing data
    resubmit_button = Button(label='resubmit', desc='Submits the measurement to the job manager. Tries to keep previously acquired data. Behaves like a normal submit if sequence or time bins have changed since previous run.')    
    
    # measurement parameters
    power = Range(low= -100., high=25., value= -38, desc='Power [dBm]', label='Power [dBm]', mode='text', auto_set=False, enter_set=True)
    frequency_begin = Range(low=1, high=20e9, value=2.85e9, desc='Start Frequency [Hz]', label='Begin [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    frequency_end = Range(low=1, high=20e9, value=2.90e9, desc='Stop Frequency [Hz]', label='End [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    frequency_delta = Range(low=1e-3, high=20e9, value=1e6, desc='frequency step [Hz]', label='Delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    t_pi = Range(low=1., high=100000., value=800., desc='length of pi pulse [ns]', label='pi [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=10000., value=300., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    pulsed = Bool(False, label='pulsed')
    power_p = Range(low= -100., high=25., value= -26, desc='Power Pmode [dBm]', label='Power Pmode[dBm]', mode='text', auto_set=False, enter_set=True)
    frequency_begin_p = Range(low=1, high=20e9, value=2.865e9, desc='Start Frequency Pmode[Hz]', label='Begin Pmode[Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    frequency_end_p = Range(low=1, high=20e9, value=2.876e9, desc='Stop Frequency Pmode[Hz]', label='End Pmode[Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    frequency_delta_p = Range(low=1e-3, high=20e9, value=0.6e5, desc='frequency step Pmode[Hz]', label='Delta Pmode[Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    seconds_per_point = Range(low=1e-6, high=1, value=10e-3, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
    stop_time = Range(low=1., value=np.inf, desc='Time after which the experiment stops by itself [s]', label='Stop time [s]', mode='text', auto_set=False, enter_set=True)
    n_lines = Range (low=1, high=10000, value=50, desc='Number of lines in Matrix', label='Matrix lines', mode='text', auto_set=False, enter_set=True)
       
    # control data fitting
    perform_fit = Bool(False, label='perform fit')
    number_of_resonances = Trait('auto', String('auto', auto_set=False, enter_set=True), Int(10000., desc='Number of Lorentzians used in fit', label='N', auto_set=False, enter_set=True))
    threshold = Range(low= -99, high=99., value= -50., desc='Threshold for detection of resonances [%]. The sign of the threshold specifies whether the resonances are negative or positive.', label='threshold [%]', mode='text', auto_set=False, enter_set=True)
    #'''new starts'''
    # control comparison
    perform_compare = Bool(False, label='perform comp')
    frequency_comp = Array()
    counts_comp = Array()
    comp_offset = Range(low= 0.0, value= 0.0, desc='compare offset', label='comp_offset', mode='text', auto_set=False, enter_set=True)
    #'''ends here'''
    # fit result
    fit_parameters = Array(value=np.array((np.nan, np.nan, np.nan, np.nan)))
    fit_frequencies = Array(value=np.array((np.nan,)), label='frequency [Hz]') 
    fit_line_width = Array(value=np.array((np.nan,)), label='line_width [Hz]') 
    fit_contrast = Array(value=np.array((np.nan,)), label='contrast [%]')
    splitting = Float(value=np.nan, label='spltting [MHz]')
    bfield = Float(value=np.nan, label='bfield [G]')
    angle = Float(value=np.nan, label='angle [Degree]')
    new_center = Float(value=np.nan, label='new_center [GHz]')
    dvalue = Range(low=0.0, value=2.87765, desc='D value for bfield data', label='D value [GHz]', mode='text', auto_set=False, enter_set=True)

    # measurement data    
    frequency = Array()
    counts = Array()
    counts_matrix = Array()
    run_time = Float(value=0.0, desc='Run time [s]', label='Run time [s]')
    mix = Int(value=0, label='mix')

    #odmr non-uniform
    custom_nonuniform = Bool(False, label='Custom Non-uniform')
    #centerlist = List(Float)
    centerlist = []
    check_centerlist = Button(label='check center')
    del_center = Button(label='del center')
    add_center = Button(label='add center')
    center = Range(low=1e-3, high=20e9, value=2.87e9, desc='center [Hz]', label='center [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    centerspan = Range(low=1e-3, high=20e9, value=1e6, desc='center span [Hz]', label='center span [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    centerdelta = Range(low=1e-3, high=20e9, value=1e6, desc='center delta [Hz]', label='center delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    
    #Cronevent GUI
    cron_event = {}
    cronname = Str(label='cronname', desc='name to use when adding or removing cron events')
    cronmin = Int(value = 0, label='cron minute')
    cronhr = Int(value = 0, label='cron hour')
    crond = Int(value = 0, label='cron day')
    cronm = Int(value = 0, label='cron month')
    cronsub = Button(label='submit a cronevent')
    
    #Hahn ODMR
    hahn = Bool(False, label='hahn')
    hahn_t_pi2 = Range(low=1., high=100000., value=800., desc='length of pi/2 pulse [ns]', label='hahn_pi2 [ns]', mode='text', auto_set=False, enter_set=True)
    hahn_wait = Range(low=1., high=100000., value=800., desc='wait time [ns]', label='hahn_wait [ns]', mode='text', auto_set=False, enter_set=True)
    hahn_T2 = Range(low=1., high=100000., value=800., desc='T2 [ns]', label='hahn_T2 [ns]', mode='text', auto_set=False, enter_set=True)
    hahn_laser = Range(low=1., high=100000., value=800., desc='length of laser [ns]', label='hahn_laser [ns]', mode='text', auto_set=False, enter_set=True)
    
    # plotting
    line_label = Instance(PlotLabel)
    line_data = Instance(ArrayPlotData)
    matrix_data = Instance(ArrayPlotData)
    line_plot = Instance(Plot, editor=ComponentEditor())
    matrix_plot = Instance(Plot, editor=ComponentEditor())

    def __init__(self):
        super(ODMRR, self).__init__()
        self._create_line_plot()
        self._create_matrix_plot()
        self.on_trait_change(self._update_line_data_index, 'frequency', dispatch='ui')
        self.on_trait_change(self._update_line_data_value, 'counts', dispatch='ui')
        self.on_trait_change(self._update_line_data_fit, 'fit_parameters', dispatch='ui')
        self.on_trait_change(self._update_matrix_data_value, 'counts_matrix', dispatch='ui')
        self.on_trait_change(self._update_matrix_data_index, 'n_lines,frequency', dispatch='ui')
        self.on_trait_change(self._update_fit, 'counts,perform_fit,number_of_resonances,threshold', dispatch='ui')
        # '''new starts'''
        self.on_trait_change(self._update_line_data_comp, 'counts_comp,frequency_comp,offset_comp', dispatch='ui')        
        # '''ends here'''
        
    def _cronsub_fired(self):
        if not self.cronname in self.cron_event.keys():
            self.cron_event[self.cronname] = CronEvent(self.submit, destruction=True, min=self.cronmin, hour=self.cronhr, day=self.crond, month=self.cronm)
            CronDaemon().register(self.cron_event[self.cronname])
        else:
            pass

    def _counts_matrix_default(self):
        return np.zeros((self.n_lines, len(self.frequency)))

    def _frequency_default(self):
        if self.pulsed:
            return np.arange(self.frequency_begin_p, self.frequency_end_p + self.frequency_delta_p, self.frequency_delta_p)
        elif self.custom_nonuniform:
            dummy = np.sort(np.array((self.centerlist)))
            freq_mid = np.array(())
            center_diff = np.diff(dummy) > 2*self.centerspan
            freq_end = np.arange(dummy[-1]+self.centerspan,self.frequency_end+self.frequency_delta, self.frequency_delta)
            freq_begin = np.arange(self.frequency_begin,dummy[0]-self.centerspan, self.frequency_delta)
            first_center = np.arange(dummy[0]-self.centerspan,dummy[0]+self.centerspan, self.centerdelta)
            if len(dummy)>1:
                for i in range(len(center_diff)):
                    if center_diff[i]:
                        print(dummy)
                        freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]-self.centerspan, self.frequency_delta))
                        freq_mid = np.append(freq_mid,np.arange(dummy[i+1]-self.centerspan, dummy[i+1]+self.centerspan, self.centerdelta))
                    else:
                        freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]+self.centerspan, self.centerdelta))
                frequency = np.append(freq_begin, first_center)
                frequency = np.append(frequency, freq_mid)
                frequency = np.append(frequency, freq_end)
            else:
                frequency = np.append(freq_begin, first_center)
                frequency = np.append(frequency, freq_end)
            return frequency
        else:
            freq = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)
            return freq
            
    def _counts_default(self):
        return np.zeros(self.frequency.shape)

    # data acquisition
    def _add_center_fired(self):
        self.centerlist.append(self.center)
        print(self.centerlist)
        
    def _del_center_fired(self):
        if len(self.centerlist)!=1:
            self.centerlist = self.centerlist[:-1]
        else:
            self.centerlist = []
        print(self.centerlist)
        
    def _check_centerlist_fired(self):
        print(self.centerlist)
        
        
    def freq_mixer(self, freq):
        a = np.copy(freq)
        random.seed(self.mix)
        b = random.choice(range(0,len(a)))
        a = np.append(a[b:],a[0:b])
        #np.random.shuffle(a)
        if self.mix%2 == 0:
            return a
        else:
            return a[::-1]

    def counts_resolve(self, counts):
        a = np.copy(counts)
        random.seed(self.mix)
        b = random.choice(range(0,len(a)))
        if self.mix%2 == 0:
            pass
        else:
            a = a[::-1]
        a = np.append(a[len(a)-b:],a[0:len(a)-b])
        return a
        
    def freq_mixer2(self, freq, mix):
        a = np.copy(freq)
        random.seed(mix)
        b = random.choice(range(0,len(a)))
        c = np.array(())
        if len(a[:b])>len(a[b:]):
            for i in range(len(a[b:])):
                c = np.append(c,a[:b][i])
                c = np.append(c,a[b:][i])
            c = np.append(c,a[:b][len(a[b:]):])
        elif len(a[:b]) == len(a[b:]):
            for i in range(len(a[b:])):
                c = np.append(c,a[:b][i])
                c = np.append(c,a[b:][i])
        else:
            for i in range(len(a[:b])):
                c = np.append(c,a[b:][i])
                c = np.append(c,a[:b][i])
            c = np.append(c,a[b:][len(a[:b]):])
        return c
    
    def counts_resolve2(self, counts, mix):
        a = np.copy(counts)
        random.seed(mix)
        b = random.choice(range(0,len(a)))
        c = np.array(())
        d = np.array(())
        if b < len(a[b:]) and b != 0:
            for i in range(0,2*b,2):
                c = np.append(c,a[i+1])
                d = np.append(d,a[i])
            d = np.append(d,a[2*b:])
            c = np.append(c,d)
            return c
        elif b == 0:
            return a
        elif len(a[b:]) == len(a[:b]):
            for i in range(0,2*b,2):
                c = np.append(c,a[i+1])
                d = np.append(d,a[i])
            c = np.append(d,c)
            return c
        else:
            for i in range(0,2*len(a[b:]),2):
                c = np.append(c,a[i+1])
                d = np.append(d,a[i])
            d = np.append(d,a[len(a[b:])*2:])
            d = np.append(d,c)
            c = d
            return c
        
    def apply_parameters(self):
        """Apply the current parameters and decide whether to keep previous data."""
        if self.pulsed:
            frequency = np.arange(self.frequency_begin_p, self.frequency_end_p + self.frequency_delta_p, self.frequency_delta_p)
        elif self.custom_nonuniform:
            dummy = np.sort(np.array((self.centerlist)))
            freq_mid = np.array(())
            center_diff = np.diff(dummy) > 2*self.centerspan
            if dummy[-1]+self.centerspan<self.frequency_end:
                freq_end = np.arange(dummy[-1]+self.centerspan,self.frequency_end+self.frequency_delta, self.frequency_delta)
            else:
                pass
            
            if dummy[0]-self.centerspan>self.frequency_begin:
                freq_begin = np.arange(self.frequency_begin,dummy[0]-self.centerspan, self.frequency_delta)
                first_center = np.arange(dummy[0]-self.centerspan,dummy[0]+self.centerspan, self.centerdelta)
            else:
                freq_begin = np.arange(self.frequency_begin,dummy[0], self.centerdelta)
                first_center = np.arange(dummy[0], dummy[0]+self.centerspan, self.centerdelta)
                
            if len(dummy)>1 and dummy[-1]+self.centerspan<self.frequency_end:
                for i in range(len(center_diff)):
                    if center_diff[i]:
                        freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]-self.centerspan, self.frequency_delta))
                        freq_mid = np.append(freq_mid,np.arange(dummy[i+1]-self.centerspan, dummy[i+1]+self.centerspan, self.centerdelta))
                    else:
                        freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]+self.centerspan, self.centerdelta))
                frequency = np.append(freq_begin, first_center)
                frequency = np.append(frequency, freq_mid)
                frequency = np.append(frequency, freq_end)
            elif len(dummy)>1 and dummy[-1]+self.centerspan>self.frequency_end:
                for i in range(len(center_diff)):
                    if i != len(center_diff)-1:
                        if center_diff[i]:
                            freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]-self.centerspan, self.frequency_delta))
                            freq_mid = np.append(freq_mid,np.arange(dummy[i+1]-self.centerspan, dummy[i+1]+self.centerspan, self.centerdelta))
                        else:
                            freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]+self.centerspan, self.centerdelta))
                    else:
                        if center_diff[i]:
                            freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, dummy[i+1]-self.centerspan, self.frequency_delta))
                            freq_mid = np.append(freq_mid,np.arange(dummy[i+1]-self.centerspan, self.frequency_end, self.centerdelta))
                        else:
                            freq_mid = np.append(freq_mid,np.arange(dummy[i]+self.centerspan, self.frequency_end, self.centerdelta))

                    frequency = np.append(freq_begin, first_center)
                    frequency = np.append(frequency, freq_mid)
            else:
                frequency = np.append(freq_begin, first_center)
                frequency = np.append(frequency, freq_end)
        else:
            frequency = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)
        if not self.keep_data or np.any(frequency != self.frequency):
            self.frequency = frequency
            self.counts = np.zeros(frequency.shape)
            self.run_time = 0.0
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.

    def _run(self):
                
        try:

            self.state = 'run'
            self.apply_parameters()

            if self.run_time >= self.stop_time:
                self.state = 'done'
                return

            # if pulsed, turn on sequence
            if self.pulsed:
                #ha.PulseGenerator().Sequence(100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw','mw_x'], self.t_pi) ])
                ha.PulseGenerator().Sequence(100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_x'], self.t_pi) ])
                #ha.PulseGenerator().Sequence(100 * [ (['aom'], self.t_pi),  (['mw_x','aom','laser'], self.laser), (['aom'], 6.0)])
            if self.hahn:
                t_pi2 = self.hahn_t_pi2
                t_pi = self.hahn_t_pi2*2
                laser = self.hahn_laser
                wait = self.hahn_wait
                t = self.hahn_T2
                ha.PulseGenerator().Sequence(100*[  (['mw_x'], t_pi2), ([], 0.5 * t), (['mw_x'], t_pi), ([], 0.5 * t), (['mw_x'], t_pi2), (['laser', 'aom'], laser), ([], wait)  ])
            else:
                #ha.PulseGenerator().Continuous(['green','mw','mw_x'])
                ha.PulseGenerator().Continuous(['green','mw_x'])

            n = len(self.frequency)
            """
            ha.Microwave().setOutput( self.power, np.append(self.frequency,self.frequency[0]), self.seconds_per_point)
            self._prepareCounter(n)
            """
            if self.pulsed:
                ha.Microwave().setPower(self.power_p)
                # ha.Microwave().initSweep(self.frequency, self.power_p * np.ones(self.frequency.shape))
            else:
                ha.Microwave().setPower(self.power)

            ha.Counter().configure(n, self.seconds_per_point, DutyCycle=0.8)
            time.sleep(0.5)

            while self.run_time < self.stop_time:
                random.seed(int(time.time()))
                self.mix = random.choice(range(0,1000))
                if self.pulsed:
                    ha.Microwave().initSweep(self.freq_mixer2(self.freq_mixer2(self.freq_mixer2(self.frequency, self.mix), int(self.mix/2)), int(self.mix/3)), self.power_p * np.ones(self.frequency.shape))
                else:
                    ha.Microwave().initSweep(self.freq_mixer2(self.freq_mixer2(self.freq_mixer2(self.frequency, self.mix), int(self.mix/2)), int(self.mix/3)), self.power * np.ones(self.frequency.shape))
                start_time = time.time()
                if threading.currentThread().stop_request.isSet():
                    break
                ha.Microwave().resetListPos()
                counts = ha.Counter().run()
                self.run_time += time.time() - start_time
                self.counts += self.counts_resolve2(self.counts_resolve2(self.counts_resolve2(counts, int(self.mix/3)),int(self.mix/2)),self.mix)
                self.counts_matrix = np.vstack((self.counts_resolve2(self.counts_resolve2(self.counts_resolve2(counts, int(self.mix/3)), int(self.mix/2)),self.mix), self.counts_matrix[:-1, :]))
                self.trait_property_changed('counts', self.counts)
                """
                ha.Microwave().doSweep()
                
                timeout = 3.
                start_time = time.time()
                while not self._count_between_markers.ready():
                    time.sleep(0.1)
                    if time.time() - start_time > timeout:
                        print "count between markers timeout in ODMR"
                        break
                        
                counts = self._count_between_markers.getData(0)
                self._count_between_markers.clean()
                """
            if self.run_time < self.stop_time:
                self.state = 'idle'
            else:
                self.state = 'done'
            if self.pulsed:
                ha.Microwave().setOutput(None, self.frequency_begin_p)
            else:
                ha.Microwave().setOutput(None, self.frequency_begin)
            ha.PulseGenerator().Light()
            ha.Counter().clear()
        except:
            logging.getLogger().exception('Error in odmr.')
            self.state = 'error'
        finally:
            if self.pulsed:
                ha.Microwave().setOutput(None, self.frequency_begin_p)
            else:
                ha.Microwave().setOutput(None, self.frequency_begin)

    # fitting
    def BFieldData(self, upper, lower, D, strain, gyro): #edited
        a = (upper + lower)*1e-9
        b = (upper - lower)*1e-9
        c = (-2*D**2+D*a)**0.5/(gyro*3**0.5)
        d = (D**2*b**2-4*D**2*strain**2-4*D*gyro**2*strain*c**2-gyro**4*c**4)**0.5/(2*D*gyro)
        e = (c**2+d**2)**0.5
        f = np.arctan(c/d)*180/np.pi
        g = (upper+lower)*1e-9/2
        data = np.array([a, b*1e3, c, d, e, f, g])
        return data

    def _update_fit(self):
        if self.perform_fit:
            N = self.number_of_resonances 
            if N != 'auto':
                N = int(N)
            try:
                p = fitting.fit_multiple_lorentzians(self.frequency, self.counts, N, threshold=self.threshold * 0.01)
            except Exception:
                logging.getLogger().debug('ODMR fit failed.', exc_info=True)
                p = np.nan * np.empty(4)
        else:
            p = np.nan * np.empty(4)
        D = self.BFieldData(p[1::3][-1],p[1::3][0],self.dvalue,0.003,0.0028)
        self.splitting = np.around(D[1],decimals=5)
        self.bfield = np.around(D[4],decimals=5)
        self.angle = np.around(D[5],decimals=5)
        self.new_center = np.around(D[-1],decimals=5)
        
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
    
    
    # plotting
        
    def _create_line_plot(self):
        line_data = ArrayPlotData(frequency=np.array((0., 1.)), counts=np.array((0., 0.)), fit=np.array((0., 0.))) 
        line_plot = Plot(line_data, padding=8, padding_left=64, padding_bottom=32)
        line_plot.plot(('frequency', 'counts'), style='line', color='blue')
        line_plot.index_axis.title = 'Frequency [MHz]'
        line_plot.value_axis.title = 'Fluorescence counts'
        line_label = PlotLabel(text='', hjustify='left', vjustify='bottom', position=[64, 128])
        line_plot.overlays.append(line_label)
        self.line_label = line_label
        self.line_data = line_data
        self.line_plot = line_plot
        
    def _create_matrix_plot(self):
        matrix_data = ArrayPlotData(image=np.zeros((2, 2)))
        matrix_plot = Plot(matrix_data, padding=8, padding_left=64, padding_bottom=32)
        matrix_plot.index_axis.title = 'Frequency [MHz]'
        matrix_plot.value_axis.title = 'line #'
        matrix_plot.img_plot('image',
                             xbounds=(self.frequency[0], self.frequency[-1]),
                             ybounds=(0, self.n_lines),
                             colormap=Spectral)
        self.matrix_data = matrix_data
        self.matrix_plot = matrix_plot
#'''new function starts'''      
    def _perform_compare_changed(self, new):       
        plot = self.line_plot
        if new:
            plot.plot(('frequency_comp', 'counts_comp'), style='line', color='green', name='comp')
            # self.line_label.visible = True
            # print(len(self.frequency_comp),len(self.counts_comp))
        else:
            plot.delplot('comp')
            # self.line_label.visible = False
            # print('Close it damn')
        plot.request_redraw()
#'''ends here'''
    def _perform_fit_changed(self, new):
        plot = self.line_plot
        if new:
            plot.plot(('frequency', 'fit'), style='line', color='red', name='fit')
            self.line_label.visible = True
        else:
            plot.delplot('fit')
            self.line_label.visible = False
        plot.request_redraw()
    
    # new starts
    def _update_line_data_comp(self):
        self.line_data.set_data('frequency_comp', self.frequency_comp * 1e-6)
        self.line_data.set_data('counts_comp', self.counts_comp)
    # ends here
    def _update_line_data_index(self):
        self.line_data.set_data('frequency', self.frequency * 1e-6)
        self.counts_matrix = self._counts_matrix_default()

    def _update_line_data_value(self):
        self.line_data.set_data('counts', self.counts)
    
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

    def _update_matrix_data_value(self):
        self.matrix_data.set_data('image', self.counts_matrix)

    def _update_matrix_data_index(self):
        if self.n_lines > self.counts_matrix.shape[0]:
            self.counts_matrix = np.vstack((self.counts_matrix, np.zeros((self.n_lines - self.counts_matrix.shape[0], self.counts_matrix.shape[1]))))
        else:
            self.counts_matrix = self.counts_matrix[:self.n_lines]
        self.matrix_plot.components[0].index.set_data((self.frequency[0] * 1e-6, self.frequency[-1] * 1e-6), (0.0, float(self.n_lines)))

    # saving data
    
    def save_line_plot(self, filename):
        self.save_figure(self.line_plot, filename)

    def save_matrix_plot(self, filename):
        self.save_figure(self.matrix_plot, filename)
    
    def save_all(self, filename):
        self.save_line_plot(filename + '_ODMR_Line_Plot.png')
        self.save_matrix_plot(filename + '_ODMR_Matrix_Plot.png')
        self.save(filename + '_ODMR.pys')
        data = cPickle.load(open(filename + '_ODMR.pys','rb'))
        counts = data[b'counts']
        frequency = data[b'frequency']
        output = np.column_stack((frequency,counts))
        np.savetxt(filename + '.txt', output)
    #'''new starts'''
    def load_comp(self, filename):
        data = cPickle.load(open(filename,'rb'))
        self.counts_comp = 1-(np.max(data[b'counts'])-data[b'counts'])/(np.max(data[b'counts']))
        self.counts_comp = self.comp_offset*self.counts_comp
        self.frequency_comp = data[b'frequency']        
    #'''ends here'''
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

    traits_view = View(VSplit(HGroup(Item('submit_button',show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority', enabled_when='state != "run"'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              VGroup(HGroup(Item('power', width= -40, enabled_when='state != "run"'),
                                            Item('frequency_begin', width= -80, enabled_when='state != "run"'),
                                            Item('frequency_end', width= -80, enabled_when='state != "run"'),
                                            Item('frequency_delta', width= -80, enabled_when='state != "run"'),
                                            Item('seconds_per_point', width= -80, enabled_when='state != "run"'),
                                            ),
                                     HGroup(Item('perform_fit'),
                                            Item('number_of_resonances', width= -60),
                                            Item('threshold', width= -60),
                                            Item('n_lines', width= -60),
                                            Item('perform_compare'),
                                            Item('comp_offset', width=-60),
                                            ),
                                     HGroup(Item('splitting', style='readonly'),
                                            Item('bfield', style='readonly'),
                                            Item('angle', style='readonly'),
                                            Item('new_center', style='readonly'),
                                            Item('dvalue'),
                                            Item('mix', style='readonly'),
                                            ),
                              Tabbed(VGroup(HGroup(Item('custom_nonuniform', enabled_when = 'state != "run"'),
                                            Item('check_centerlist'),
                                            Item('add_center'),
                                            Item('del_center'),
                                            ),
                                            HGroup(Item('center', width = -40, enabled_when = 'state != "run"'),
                                            Item('centerspan', width = -40, enabled_when = 'state != "run"'),
                                            Item('centerdelta', width = -40, enabled_when = 'state != "run"'),
                                            ),
                                            label='non-uniform'),
                                    VGroup(HGroup(Item('pulsed', enabled_when='state != "run"'),
                                            Item('power_p', width= -40, enabled_when='state != "run"'),
                                            Item('frequency_begin_p', width= -80, enabled_when='state != "run"'),
                                            ),
                                     HGroup(Item('frequency_end_p', width= -80, enabled_when='state != "run"'),
                                            Item('frequency_delta_p', width= -80, enabled_when='state != "run"'),
                                            Item('t_pi', width= -50, enabled_when='state != "run"'),
                                            ),
                                            label='pulsed',
                                            ),
                                     VGroup(HGroup(Item('hahn', enabled_when='state != "run"'),
                                            Item('hahn_laser', width= -80, enabled_when='state != "run"'),
                                            Item('hahn_wait', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('hahn_t_pi2', width= -80, enabled_when='state != "run"'),
                                            Item('hahn_T2', width= -80, enabled_when='state != "run"'),
                                            ),
                                            label='hahn',
                                            ),
                                     VGroup(HGroup(Item('cronsub'),
                                            Item('cronname', width=-50),
                                            ),
                                            HGroup(Item('cronm', width= -50),
                                            Item('crond', width= -50),
                                            Item('cronhr',width=-50),
                                            Item('cronmin', width=-50),
                                            ),
                                            label='cronevent',
                                            ),
                                            ),
                                     ),
                            Tabbed(Item('matrix_plot', show_label=False, resizable=True),
                                     Item('line_plot', show_label=False, resizable=True),
                                     ),
                              ),
                             menubar=MenuBar(Menu(Action(action='saveLinePlot', name='SaveLinePlot (.png)'),
                                              Action(action='saveMatrixPlot', name='SaveMatrixPlot (.png)'),
                                              Action(action='save', name='Save (.pyd or .pys)'),
                                              Action(action='saveAll', name='Save All (.png+.pys)'),
                                              Action(action='export', name='Export as Ascii (.asc)'),
                                              #'''new starts'''
                                              Action(action='loadcomp', name='LoadComparison'),
                                              #'''ends here'''
                                              Action(action='load', name='Load'),
                                              Action(action='_on_close', name='Quit'),
                                              name='File')),
                       title='ODMRR', width=900, height=500, buttons=[], resizable=True, handler=ODMRHandler
                       )

    get_set_items = ['frequency', 'counts', 'counts_matrix',
                     'fit_parameters', 'fit_contrast', 'fit_line_width', 'fit_frequencies',
                     'splitting', 'bfield', 'angle', 'new_center', 'dvalue', 'mix',#edited
                     'perform_fit', 'run_time',
                     'hahn', 'hahn_laser', 'hahn_wait', 'hahn_T2', 'hahn_t_pi2',
                     'power', 'frequency_begin', 'frequency_end', 'frequency_delta',
                     'custom_nonuniform',  'center', 'centerspan', 'centerdelta', 'centerlist',#'check_centerlist', 'centerlist','add_center',
                    'power_p', 'frequency_begin_p', 'frequency_end_p', 'frequency_delta_p',
                    'laser', 'wait', 'pulsed', 't_pi', 'seconds_per_point',
                      'stop_time', 'n_lines',
                     'number_of_resonances', 'threshold',
                     '__doc__']


if __name__ == '__main__':

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().info('Starting logger.')

    from tools.emod import JobManager
    JobManager().start()

    o = ODMRR()
    o.edit_traits()
    
    
