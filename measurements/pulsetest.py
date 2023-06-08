from traits.api import SingletonHasTraits, Trait, Instance, Property, String, Range, Float, Int, Bool, Array, Enum, Button, on_trait_change, cached_property, Code, List, NO_COMPARE
from traitsui.api import View, Item, HGroup, VGroup, VSplit, Tabbed, EnumEditor, TextEditor, Group
from enable.api import Component, ComponentEditor
from chaco.api import ArrayPlotData, Plot, Spectral, PlotLabel
from traitsui.file_dialog import save_file
from traitsui.menu import Action, Menu, MenuBar

import numpy as np
import time
import threading
import logging
import hardware.api as ha

from hardware.waveform import *
from tools.emod import ManagedJob
from measurements.auto_resonance import AutoResonance
from measurements.auto_focus import AutoFocus
from measurements.auto_offset import AutoOffset
from pulsed import sequence_length
from tools.utility import GetSetItemsHandler, GetSetItemsMixin
from analysis.fitting import find_edge

class RRHandler(GetSetItemsHandler):

    def saveLinePlot(self, info):
        filename = save_file(title='Save Line Plot')
        if filename is '':
            return
        else:
            if filename.find('.png') == -1:
                filename = filename + '.png'
            info.object.save_line_plot(filename)

    def saveAsText(self, info):
        filename = save_file(title='Save data as text file')
        if filename is '':
            return
        else:
            if filename.find('.txt') == -1:
                filename = filename + '.txt'
                info.object.save_as_text(filename)
                
    def saveAll(self, info):
        filename = save_file(title='Save All')
        if filename is '':
            return
        else:
            info.object.save_all(filename)


class QND_DDR1(ManagedJob, GetSetItemsMixin):
    """Provides single shot e spin measurements."""

    keep_data = Bool(False) # helper variable to decide whether to keep existing data

    resubmit_button = Button(label='resubmit', desc='Submits the measurement to the job manager. Tries to keep previously acquired data. Behaves like a normal submit if sequence or time bins have changed since previous run.')    
    
    time_focus = Range(low=1., high=10000., value=60, desc='refocusing interval[s]', label='focus interval [s]', mode='text', auto_set=False, enter_set=True)
    time_offset = Range(low=1., high=10000., value=60, desc='eomoffset interval[s]', label='eomoffset interval [s]', mode='text', auto_set=False, enter_set=True)
    
    mw_frequency = Range(low=1, high=20e9, value=2.877650e+09, desc='microwave frequency', label='MW freq [Hz]', mode='text', auto_set=False, enter_set=True)
    mw_power = Range(low= -100., high=25., value= -90, desc='microwave power', label='MW power [dBm]', mode='text', auto_set=False, enter_set=True)
    mw_t_pi = Range(low=1., high=100000., value=150., desc='length of pi pulse of MW[ns]', label='MW pi [ns]', mode='text', auto_set=False, enter_set=True)
    delay = Range(low=1., high=1.0e9, value=6., desc='length of delay before MW[ns]', label='delay [ns]', mode='text', auto_set=False, enter_set=True)
    
    spec_line = Enum('mw_r_e', 'mw_r_a', desc='NV spectrum line', label='spec_line')
    p_line = Enum('mw_r_e', 'mw_r_a','mw_r_a2', desc='P line', label='p_line')
    
    red_aom = Range(low= -10., high=-1., value=-7.7, desc='Red AOM', label='Red AOM [V]', mode='text', auto_set=False, enter_set=True)
    line1_seconds_per_point = Range(low=1e-5, high=10, value=0.00042, desc='Seconds per point for line 1', label='spp E', mode='text', auto_set=False, enter_set=True)
    line2_seconds_per_point = Range(low=1e-5, high=10, value=0.00057, desc='Seconds per point for line 2', label='spp A', mode='text', auto_set=False, enter_set=True)
    
    laser_read = Range(low=1., high=1.0e7, value=90, desc='laser read[ns]', label='laser read[ns]', mode='text', auto_set=False, enter_set=True)
    laser_init = Range(low=1., high=1.0e7, value=4000, desc='laser init[ns]', label='laser init[ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=1.0e7, value=100, desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    flank = Range(low=0.1, high=10000., value=1.0, desc='offset', label='offset (ns)', mode='text', auto_set=False, enter_set=True)
    charge_threshold = Range(low= -1.0, high=1.0e5, value=0.2, desc='charge threshold', label='charge threshold', mode='text', auto_set=False, enter_set=True)
    number_loop = Int(1, desc='number of loop', label='number of loop', mode='text', auto_set=False, enter_set=True)
    sweep_per_round = Int(500, desc='Sweep per round', label='Sweep per round', mode='text', auto_set=False, enter_set=True)
    
    record_length = Range(low=10, high=1.0e9, value=90, desc='length of acquisition record [ns]', label='record length [ns]', mode='text', auto_set=False, enter_set=True)
    bin_width = Range(low=0.1, high=1.0e9, value=1, desc='bin width [ns]', label='bin width [ns]', mode='text', auto_set=False, enter_set=True)
    
    ar = Instance(AutoResonance)
    auto_focus = Instance(AutoFocus)
    count_data0 = Array()
    count_data1 = Array()
    num_count = Int()
    decay_data0 = Array()
    decay_data1 = Array()
    
    run_time = Float(value=0.0)
    stop_time = Range(low=1., value=np.inf, desc='Time after which the experiment stops by itself [s]', label='Stop time [s]', mode='text', auto_set=False, enter_set=True)
        
    # plotting
    decay_plot_data0 = Instance(ArrayPlotData)
    decay_plot0 = Instance(Plot, editor=ComponentEditor())
    decay_plot_data1 = Instance(ArrayPlotData)
    decay_plot1 = Instance(Plot, editor=ComponentEditor())
    
    def __init__(self, ar, auto_focus,aos):
        super(QND_DDR1, self).__init__()
        self._create_decay_plot0()
        self._create_decay_plot1()
        self.ar = ar
        self.aos = aos
        self.auto_focus = auto_focus
        self.on_trait_change(self._update_decay_data_value0, 'decay_plot_data0', dispatch='ui')
        self.on_trait_change(self._update_decay_data_value1, 'decay_plot_data1', dispatch='ui')
        
    def submit(self):
        """Submit the job to the JobManager."""
        self.keep_data = False
        ManagedJob.submit(self)

    def resubmit(self):
        """Submit the job to the JobManager."""
        self.keep_data = True
        ManagedJob.submit(self)

    def _resubmit_button_fired(self):
         self.resubmit() 
    
    def apply_parameters(self):
        
        #if (self.record_length > (self.laser_read + self.wait)) or (self.record_length < self.laser_read):
        #    self.record_length = self.laser_read + self.wait * 0.5
        n_bins = int(self.record_length / self.bin_width)
        time_bins = self.bin_width * np.arange(n_bins)
        sequence = self.generate_sequence()
        self.sequence = sequence
        self.sequence_length = sequence_length(sequence) * 1e-9
        self.time_bins = time_bins
        self.n_bins = n_bins
        if self.keep_data and sequence == self.sequence and np.all(time_bins == self.time_bins): # if the sequence and time_bins are the same as previous, keep existing data
#             self.statistics = self.statistics.copy()
#             self.count_data = self.count_data.copy()
#             self.num_count = self.num_count.copy()
#             self.decay_data = self.decay_data.copy()
            pass
        else:
            self.count_data0 = np.zeros((1, n_bins))
            self.decay_data0 = np.zeros(n_bins)
            self.count_data1 = np.zeros((1, n_bins))
            self.decay_data1 = np.zeros(n_bins)
            self.num_count = 0
            self.run_time = 0.0
                
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.
    
    def generate_sequence(self):
#         spec_i = self.p_line
#         if self.spec_line == 'mw_r_e':
#             spec_i = 'mw_r_a'
#         if self.spec_line == 'mw_r_a':
#             spec_i = 'mw_r_e'    
        sequence = [(['dtg'], 60),([], 60),(['red'], 180),([], 54) ,(['laser'], self.laser_read) , ([], 6000)]
        #sequence = [(['dtg'], 60),([], 81),(['red'], 61),([], 201) ,(['laser'], self.laser_read) , ([], 6000)]
        #sequence = [(['mw_r_a', 'red'], self.laser_init), (['mw_r_a'], 500),([],self.delay), (['mw','mw_x'], self.mw_t_pi), ([], 200),(['red'],320),  (['red', 'laser', self.spec_line], 100), (['red', 'laser'], self.laser_read-100) , ([], self.wait), (['mw_r_e', 'mw_r_a', 'red', 'laser'], self.laser_check), ([], self.wait)]
        #sequence = [(['mw_r_a', 'red'], self.laser_init), (['mw_r_a'], 500),([],self.delay),  (['mw','mw_x'], self.mw_t_pi), ([], 200), (['dtg',self.spec_line], 60),([self.spec_line], 60),(['red',self.spec_line], 180),([self.spec_line], 54) ,(['laser'], self.laser_read) , ([], 6000)]
        #sequence = [([spec_i, 'red'], self.laser_init), ([spec_i], 500),([],self.delay), (['mw','mw_x'], self.mw_t_pi), ([], 200), (['red'],300),(['red', 'laser', self.spec_line], self.laser_read) , ([], self.wait), (['mw_r_e', 'mw_r_a', 'red', 'laser'], self.laser_check), ([], self.wait)]
        #sequence = [([], 200),([], 200),(['red', 'laser', self.spec_line], self.laser_read) , ([], self.wait), (['mw_r_e', 'mw_r_a', 'red', 'laser'], self.laser_check), ([], self.wait)]
        sequence = self.sweep_per_round * sequence
        sequence += [(['sequence'], 120)]
        return sequence

    def _run(self):
                
        try: # try to run the acquisition from start_up to shut_down
            self.state = 'run'
            self.apply_parameters()
            ha.RedAOM().voltage=self.red_aom
            """
            if self.line1_seconds_per_point != 0: 
                self.ar.line1_seconds_per_point=self.line1_seconds_per_point 
            if self.line2_seconds_per_point != 0: 
                self.ar.line2_seconds_per_point=self.line2_seconds_per_point
            """
            ha.DtgOptical()._write('PGENB:CH1:OUTP ON')
            ha.DtgOptical()._write('PGENA:CH1:OUTP ON')
            ha.DtgOptical()._write('PGENA:CH2:OUTP ON')
            ha.DtgOptical()._write('TBAS:RUN ON')
            
            ha.PulseGenerator().Night()
            ha.Microwave().setOutput(self.mw_power, self.mw_frequency)
            tagger0 = ha.TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), self.sweep_per_round, 0, 2, 3)
            tagger1 = ha.TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), self.sweep_per_round, 4, 2, 3)
            tagger1.setMaxCounts(self.number_loop +1)
            tagger0.setMaxCounts(self.number_loop +1)
            #ha.PulseGenerator().Sequence(self.sequence)
            time.sleep(0.5)
            
            time_focus = 0.0
            time_offset=0.
            count_data0 = ()
            count_data1 = ()
            check_counts = np.zeros(self.sweep_per_round)
            I = int(round((self.laser_read) / float(self.bin_width)))
            flank = 0 #flank = int(round((self.flank) / float(self.bin_width)))
            
            #ha.PulseGenerator().Continuous([])
            #ha.PulseGenerator().checkUnderflow()
            
            while self.run_time < self.stop_time:
                
                start_time = time.time()
                if threading.currentThread().stop_request.isSet():
                    break
                
                ha.PulseGenerator().Sequence(self.sequence)
                tagger0.clear()
                tagger1.clear()
                
                while not tagger0.ready():
                    time.sleep(1.1 * self.sequence_length)
                
                count_data0 = tagger0.getData()
                count_data1 = tagger1.getData()
                self.count_data=count_data0+count_data1
                
                for n in range(self.sweep_per_round):
                    #self.count_data0 = np.vstack((self.count_data0, count_data0[n][:]))
                    #self.count_data1 = np.vstack((self.count_data1, count_data1[n][:]))
                    self.decay_data0 += count_data0[n][:]
                    self.decay_data1 += count_data1[n][:]
            
                    
                time_focus += time.time() - start_time
                time_offset += time.time() - start_time
                self.run_time += time.time() - start_time
#                 if time_focus > self.time_focus:
#                     time_focus=0
#                     self.auto_focus._run()
                if time_offset > self.time_offset:
                    time_offset=0
                    self.aos._run()
                
                ha.PulseGenerator().Continuous(['green'])
                time.sleep(0.5) 
                
#                 self.ar._run()
#                 ar_run=0.
#                 while (self.ar.drift1[-1] == 0 or self.ar.drift2[-1] == 0):
#                     if ar_run < 20.:
#                         if threading.currentThread().stop_request.isSet():
#                             break
#                         ha.PulseGenerator().Continuous(['green'])
#                         time.sleep(0.5) 
#                         self.ar._run()
#                         ar_run +=1.
#                     else:
#                         ar_run=0
#                         time_focus=0
#                         self.auto_focus._run()
#                         break
#                 
                
            del tagger0
            del tagger1
            ha.PulseGenerator().Night()
            ha.Microwave().setOutput(None, self.mw_frequency)

        finally: # if anything fails, recover
            self.state = 'idle'        
            ha.PulseGenerator().Night()
                
   
    # plotting    
    
    def _create_decay_plot0(self):
        decay_plot_data = ArrayPlotData(time=np.array((0., 1.)), counts=np.array((0., 0.))) 
        decay_plot = Plot(decay_plot_data, padding=8, padding_left=64, padding_bottom=32)
        decay_plot.plot(('time', 'counts'), style='line', color='blue')
        decay_plot.index_axis.title = 'time(ns)'
        decay_plot.value_axis.title = 'PSB count'
        self.decay_plot_data0 = decay_plot_data
        self.decay_plot0 = decay_plot
        
    def _create_decay_plot1(self):
        decay_plot_data = ArrayPlotData(time=np.array((0., 1.)), counts=np.array((0., 0.))) 
        decay_plot = Plot(decay_plot_data, padding=8, padding_left=64, padding_bottom=32)
        decay_plot.plot(('time', 'counts'), style='line', color='blue')
        decay_plot.index_axis.title = 'time(ns)'
        decay_plot.value_axis.title = 'ZPL count'
        self.decay_plot_data1 = decay_plot_data
        self.decay_plot1 = decay_plot
    
    def _update_decay_data_value0(self):
        s = self.decay_data0
        tbin = self.bin_width# / 1000.0
        index = np.arange(0, tbin * (len(s)), tbin)
        self.decay_plot_data0.set_data('counts', s)
        self.decay_plot_data0.set_data('time', index)
        
    def _update_decay_data_value1(self):
        s = self.decay_data1
        tbin = self.bin_width# / 1000.0
        index = np.arange(0, tbin * (len(s)), tbin)
        self.decay_plot_data1.set_data('counts', s)
        self.decay_plot_data1.set_data('time', index)
        
    
    def save_line_plot(self, filename):
        self.save_figure(self.line_plot, filename + 'stat.png')
        self.save_figure(self.decay_plot, filename + 'decay.png')
        
    def save_as_text(self, filename):
        np.savetxt(filename, self.statistics)
        
    def save_all(self, filename):
        self.save_line_plot(filename + '_QND_')
        self.save_as_text(filename + '_QND_.txt')
        self.save(filename + '_QND.pys')

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', width= -40, format_str='%6.0f'),
                                     Item('time_focus', width= -40, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float)),
                                     Item('time_offset', width= -40, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float)),
                                     ),
                              Group(HGroup(Item('mw_frequency', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%3.1e' % x)),
                                           Item('mw_power', width= -40, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float)),
                                           Item('mw_t_pi', width= -40, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%5.0f' % x)),
                                           Item('delay', width= -40, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%2.0f' % x)),
                                           #Item('spec_line', style='custom'),
                                           #Item('p_line', style='custom'),
                                           ),
                                    HGroup(Item('red_aom', width= -40),
                                           Item('laser_read', width= -60, enabled_when='state == "idle"'),
                                           Item('laser_init', width= -60, enabled_when='state == "idle"'),
                                           Item('wait', width= -60, enabled_when='state == "idle"'),
                                           ),
                                    HGroup(Item('sweep_per_round', width= -40, enabled_when='state == "idle"'),
                                           Item('flank', width= -40, enabled_when='state == "idle"'),
                                           Item('charge_threshold', width= -40, enabled_when='state == "idle"'),
                                           Item('record_length', width= -40, enabled_when='state == "idle"'),
                                           Item('bin_width', width= -40, enabled_when='state == "idle"'),
                                           Item('stop_time', width= -80),
                                           ),
                                    ),
                              VSplit(
                                     Item('decay_plot0', show_label=False, resizable=True),
                                     Item('decay_plot1', show_label=False, resizable=True),
                                     ),
                              ),
                       menubar=MenuBar(Menu(Action(action='saveLinePlot', name='SaveLinePlot (.png)'),
                                              Action(action='save', name='Save (.pyd or .pys)'),
                                              Action(action='saveAsText', name='SaveAsText (.txt)'),
                                              Action(action='saveAll', name='Save All (.png+.pys)'),
                                              Action(action='export', name='Export as Ascii (.asc)'),
                                              Action(action='load', name='Load'),
                                              Action(action='_on_close', name='Quit'),
                                              name='File')),
                       title='Pulse shape', width=1200, height=1000, buttons=[], resizable=True, handler=RRHandler
                       )

    get_set_items = ['mw_frequency', 'mw_power', 'red_aom','mw_t_pi', 'laser_read', 'laser_check', 'laser_init', 'laser_green', 'wait', 'sweep_per_round', 'delay',
                   'statistics', 'flank', 'count_data', 'bin_width', 'run_time', 'p_line', 'charge_threshold', 'num_count', 'decay_data', 'spec_line', '__doc__' ]

 
if __name__ == '__main__':

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().info('Starting logger.')

    from tools.emod import JobManager
    JobManager().start()