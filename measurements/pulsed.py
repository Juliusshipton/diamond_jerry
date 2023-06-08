import numpy as np

from traits.api import Range, Int, Float, Bool, Array, Instance, Enum, on_trait_change, Button
from traitsui.api import View, Item, Tabbed, HGroup, VGroup, VSplit, EnumEditor, TextEditor

import logging
import time

from hardware.api import PulseGenerator, TimeTagger, Microwave, MicrowaveD, MicrowaveE, RFSource

from tools.emod import ManagedJob

from tools.utility import GetSetItemsMixin

"""
Several options to decide when to start  and when to restart a job, i.e. when to clear data, etc.

1. set a 'new' flag on every submit button

pro: simple, need not to think about anything in subclass

con: continue of measurement only possible by hack (manual submit to JobManager without submit button)
     submit button does not do what it says
     
2. check at start time whether this is a new measurement.

pro: 

con: complicated checking needed
     checking has to be reimplemented on sub classes
     no explicit way to restart the same measurement

3. provide user settable clear / keep flag

pro: explicit

con: user can forget

4. provide two different submit buttons: submit, resubmit

pro: explicit

con: two buttons that user may not understand
     user may use wrong button
     wrong button can result in errors

"""

# utility functions
def find_laser_pulses(sequence):
    n = 0
    prev = []
    for channels, t in sequence:
        if 'laser' in channels and not 'laser' in prev:
            n += 1
        prev = channels
        if ('sequence' in channels) and (n>0):
            break
    return n

def sequence_length(sequence):
    t = 0
    for c, ti in sequence:
        t += ti
    return t

def sequence_union(s1, s2):
    """
    Return the union of two pulse sequences s1 and s2.
    """
    # make sure that s1 is the longer sequence and s2 is merged into it
    if sequence_length(s1) < sequence_length(s2):
        sp = s2
        s2 = s1
        s1 = sp
    s = []
    c1, dt1 = s1.pop(0)
    c2, dt2 = s2.pop(0)
    while True:
        if dt1 < dt2:
            s.append((set(c1) | set(c2), dt1))
            dt2 -= dt1
            try:
                c1, dt1 = s1.pop(0)
            except:
                break
        elif dt2 < dt1:
            s.append((set(c1) | set(c2), dt2))
            dt1 -= dt2
            try:
                c2, dt2 = s2.pop(0)
            except:
                c2 = []
                dt2 = np.inf
        else:
            s.append((set(c1) | set(c2), dt1))
            try:
                c1, dt1 = s1.pop(0)
            except:
                break
            try:
                c2, dt2 = s2.pop(0)
            except:
                c2 = []
                dt2 = np.inf            
    return s

def sequence_remove_zeros(sequence):
    return filter(lambda x: x[1] != 0.0, sequence)

class Pulsed(ManagedJob, GetSetItemsMixin):
    
    """Defines a pulsed measurement."""
    
    keep_data = Bool(False) # helper variable to decide whether to keep existing data

    resubmit_button = Button(label='resubmit', desc='Submits the measurement to the job manager. Tries to keep previously acquired data. Behaves like a normal submit if sequence or time bins have changed since previous run.')

    sequence = Instance(list, factory=list)
    
    record_length = Range(low=100, high=100000., value=3000, desc='length of acquisition record [ns]', label='record length [ns]', mode='text', auto_set=False, enter_set=True)
    bin_width = Range(low=0.1, high=1000., value=1.0, desc='bin width [ns]', label='bin width [ns]', mode='text', auto_set=False, enter_set=True)
    
    n_laser = Int(2)
    n_bins = Int(2)
    time_bins = Array(value=np.array((0, 1)))
    
    count_data = Array(value=np.zeros((2, 2)))
    
    run_time = Float(value=0.0, label='run time [s]', format_str='%.f')
    stop_time = Range(low=1., value=np.inf, desc='Time after which the experiment stops by itself [s]', label='Stop time [s]', mode='text', auto_set=False, enter_set=True)
    
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

    def generate_sequence(self):
        return []

    def apply_parameters(self):
        """Apply the current parameters and decide whether to keep previous data."""
        n_bins = int(self.record_length / self.bin_width)
        time_bins = self.bin_width * np.arange(n_bins)
        sequence = self.generate_sequence()
        n_laser = find_laser_pulses(sequence)

        if self.keep_data and sequence == self.sequence and np.all(time_bins == self.time_bins): # if the sequence and time_bins are the same as previous, keep existing data
            self.old_count_data = self.count_data.copy()
        else:
            self.old_count_data = np.zeros((n_laser, n_bins))
            self.run_time = 0.0
        
        self.sequence = sequence 
        self.time_bins = time_bins
        self.n_bins = n_bins
        self.n_laser = n_laser
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.

    def start_up(self):
        """Put here additional stuff to be executed at startup."""
        pass

    def shut_down(self):
        """Put here additional stuff to be executed at shut_down."""
        pass

    def _run(self):
        """Acquire data."""

        try: # try to run the acquisition from start_up to shut_down
            self.state = 'run'
            self.apply_parameters()

            if self.run_time >= self.stop_time:
                logging.getLogger().debug('Runtime larger than stop_time. Returning')
                self.state = 'done'
                return

            self.start_up()
            PulseGenerator().Night()
            tagger_0 = TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), self.n_laser, 0, 2, 3)
            tagger_1 = TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), self.n_laser, 1, 2, 3)

            #tagger_0 = TimeTagger.Pulsed(int(self.n_bins), int(np.round(self.bin_width * 1000)), int(self.n_laser), Int(0), Int(2), Int(3))
            #tagger_1 = TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), self.n_laser, Int(1), Int(2), Int(3))
            PulseGenerator().Sequence(self.sequence)
            if PulseGenerator().checkUnderflow():
                logging.getLogger().info('Underflow in pulse generator.')
                PulseGenerator().Night()
                PulseGenerator().Sequence(self.sequence)
                
            
            while self.run_time < self.stop_time:
                start_time = time.time()
                self.thread.stop_request.wait(1.0)
                if self.thread.stop_request.isSet():
                    logging.getLogger().debug('Caught stop signal. Exiting.')
                    break
                if PulseGenerator().checkUnderflow():
                    logging.getLogger().info('Underflow in pulse generator.')
                    PulseGenerator().Night()
                    PulseGenerator().Sequence(self.sequence)
                self.count_data = self.old_count_data + tagger_0.getData()  + tagger_1.getData()
                self.run_time += time.time() - start_time

            if self.run_time < self.stop_time:
                self.state = 'idle'
            else:
                self.state = 'done'
            del tagger_0
            del tagger_1
            self.shut_down()
            PulseGenerator().Light()

        except: # if anything fails, log the exception and set the state
            logging.getLogger().exception('Something went wrong in pulsed loop.')
            self.state = 'error'

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     #Item('run_time', style='readonly', format_str='%.f'),
                                     #Item('stop_time'),
                                     ),
                             HGroup(Item('run_time', style='readonly', format_str='%.f'),
                                    Item('stop_time'),
                                    ),
                              HGroup(Item('bin_width', width= -80, enabled_when='state != "run"'),
                                     Item('record_length', width= -80, enabled_when='state != "run"'),
                                     ),
                              ),
                       title='Pulsed Measurement',
                       )

    get_set_items = ['__doc__', 'record_length', 'bin_width', 'n_bins', 'time_bins', 'n_laser', 'sequence', 'count_data', 'run_time']


class PulsedTau(Pulsed):

    """Defines a Pulsed measurement with tau mesh."""

    tau_begin = Range(low=0., high=1e8, value=0., desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=300., desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e8, value=3., desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)

    tau = Array(value=np.array((0., 1.)))

    def apply_parameters(self):
        """Overwrites apply_parameters() from pulsed. Prior to generating sequence, etc., generate the tau mesh."""
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        Pulsed.apply_parameters(self)

    get_set_items = Pulsed.get_set_items + ['tau_begin', 'tau_end', 'tau_delta', 'tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     #Item('run_time', style='readonly', format_str='%.f'),
                                     #Item('stop_time'),
                                     ),
                             HGroup(Item('run_time', style='readonly', format_str='%.f'),
                                    Item('stop_time'),
                                    ),
                              HGroup(Item('bin_width', width= -80, enabled_when='state != "run"'),
                                     Item('record_length', width= -80, enabled_when='state != "run"'),
                                     ),
                              ),
                       title='PulsedTau Measurement',
                       )

class Rabi(PulsedTau):
    
    """Defines a Rabi measurement."""

    frequency = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency', label='frequency [Hz]', mode='text', auto_set=False, enter_set=True, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    power = Range(low= -100., high=25., value= -20, desc='microwave power', label='power [dBm]', mode='text', auto_set=False, enter_set=True)
    switch = Enum('mw', 'mw_y', desc='switch to use for microwave pulses', label='switch', editor=EnumEditor(cols=3, values={'mw':'1:X', 'mw_y':'2:Y'}))

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=0., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
        
    def start_up(self):
        PulseGenerator().Night()
        Microwave().setOutput(self.power, self.frequency)

    def shut_down(self):
        PulseGenerator().Light()
        #Microwave().setOutput(None, self.frequency)

    def generate_sequence(self):
        MW = self.switch
        tau = self.tau
        laser = self.laser
        wait = self.wait
        sequence = [ (['aom'], laser), ([], wait) ]
        for t in tau:
            #sequence += [  ([MW], t), ([], wait), (['laser', 'aom'], laser)  ]
            sequence += [  ([MW, 'mw_x'],t),  (['laser','aom'],laser),  ([],wait)  ]
        sequence += [ (['sequence'], 100)  ]
        return sequence

    get_set_items = PulsedTau.get_set_items + ['frequency', 'power', 'switch', 'laser', 'wait']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('stop_time'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('state', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('switch', style='custom', enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),
                                                   ),
                                     label='settings'),
                              ),
                              
                        ),
                       title='Rabi Measurement',
                  )

class T1(PulsedTau):
    
    """Defines a T1 measurement."""

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
        
    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        sequence = [ (['aom'], laser) ]
        for t in tau:
            sequence += [  ([], t), (['laser', 'aom'], laser)  ]
        sequence += [  ([], 1000)  ]
        sequence += [  (['sequence'], 100)  ]
        return sequence

    get_set_items = PulsedTau.get_set_items + ['laser']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     #Item('run_time', style='readonly', format_str='%.f'),
                                     #Item('stop_time'),
                                     ),
                              HGroup(Item('run_time', style='readonly', format_str='%.f'),
                                    Item('stop_time'),
                                    ),
                              Tabbed(VGroup(HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                              ),
                       ),
                       title='T1 Measurement',
                       )

class PulseCal(Pulsed):
    
    """Pulse Calibration."""

    frequency = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency', label='frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    power = Range(low= -100., high=25., value= -20, desc='microwave power', label='power [dBm]', mode='text', auto_set=False, enter_set=True)
    switch = Enum('mw_x', 'mw_y', desc='switch to use for microwave pulses', label='switch', editor=EnumEditor(cols=3, values={'mw_x':'1:X', 'mw_y':'2:Y'}))

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    pulse = Range(low=1., high=100000., value=1000., desc='Length of the Pulse that is Calibrated', label='pulse [ns]', mode='text', auto_set=False, enter_set=True)
    delay = Range(low=1., high=100000., value=100., desc='Delay between two pulses', label='delay [ns]', mode='text', auto_set=False, enter_set=True)

    N = Range(low=0, high=100, value=6, desc='Maximum Number of pulses', label='N', mode='text', auto_set=False, enter_set=True)

    def start_up(self):
        PulseGenerator().Night()
        Microwave().setOutput(self.power, self.frequency)

    def shut_down(self):
        PulseGenerator().Light()
        Microwave().setOutput(None, self.frequency)

    def generate_sequence(self):
        mw = self.switch
        laser = self.laser
        wait = self.wait
        delay = self.delay
        pulse = self.pulse
        N = self.N
        sequence = []
        for i in range(N):
            sequence += i * [  ([mw], pulse), ([], delay)  ] + [  (['laser', 'aom'], laser), ([], wait)  ]
        sequence += [  (['sequence'], 100)  ]
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency', 'power', 'laser', 'wait', 'pulse', 'delay', 'N', 'switch']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('switch', style='custom',)
                                                   ),
                                            HGroup(Item('pulse', width= -80, enabled_when='state != "run"'),
                                                   Item('delay', width= -80, enabled_when='state != "run"'),
                                                   Item('N', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'
                                            ),
                                     ),
                              ),
                              title='Pulse Calibration',
                              )

class Pi2PiCal(Pulsed):
    
    """Pulse Calibration with initial and final pi/2_x pulses, pi_x and pi_y pulse sequences and bright / dark reference."""

    frequency = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency', label='frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    power = Range(low= -100., high=25., value= -20, desc='microwave power', label='power [dBm]', mode='text', auto_set=False, enter_set=True)

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    t_pi2_x = Range(low=0., high=100000., value=1000., desc='pi/2 pulse length (x)', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_y = Range(low=1., high=100000., value=1000., desc='pi pulse length (y)', label='pi y [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_x = Range(low=1., high=100000., value=1000., desc='pi pulse length (x)', label='pi x [ns]', mode='text', auto_set=False, enter_set=True)
    delay = Range(low=1., high=100000., value=100., desc='Delay between two pulses', label='delay [ns]', mode='text', auto_set=False, enter_set=True)

    n_pi = Range(low=0, high=100, value=10, desc='number of pi pulses', label='n pi', mode='text', auto_set=False, enter_set=True)
    n_ref = Range(low=1, high=100, value=10, desc='number of reference pulses', label='n ref', mode='text', auto_set=False, enter_set=True)

    def start_up(self):
        PulseGenerator().Night()
        Microwave().setOutput(self.power, self.frequency)

    def shut_down(self):
        PulseGenerator().Light()
        Microwave().setOutput(None, self.frequency)

    def generate_sequence(self):

        # parameters        
        laser = self.laser
        wait = self.wait
        t_pi2_x = self.t_pi2_x
        t_pi_y = self.t_pi_y
        t_pi_x = self.t_pi_x
        n_pi = self.n_pi
        n_ref = self.n_ref
        t = self.delay
        sequence = []
        
        # first sequence
        sequence += [ (['laser', 'aom'], laser), ([], wait) ]
        for n in range(n_pi + 1):
            sequence += [ (['mw_x'], t_pi2_x), ([], t)    ]
            sequence += n * [ (['mw_x'], t_pi_x), ([], 2 * t)  ] 
            sequence += [ (['laser', 'aom'], laser), ([], wait) ]
        sequence += [ (['mw_x'], t_pi2_x), ([], t)    ]
        sequence += n * [ (['mw_x'], t_pi_x), ([], 2 * t)  ] 
        sequence += [ (['mw_x'], t_pi2_x), ([], t)    ]
        sequence += [ (['laser', 'aom'], laser), ([], wait) ]
        
        # second sequence
        sequence += [ (['laser', 'aom'], laser), ([], wait) ]
        for n in range(n_pi + 1):
            sequence += [ (['mw_x'], t_pi2_x), ([], t)    ]
            sequence += n * [ (['mw_y'], t_pi_y), ([], 2 * t)  ] 
            sequence += [ (['laser', 'aom'], laser), ([], wait) ]
        sequence += [ (['mw_x'], t_pi2_x), ([], t)    ]
        sequence += n * [ (['mw_y'], t_pi_y), ([], 2 * t)  ]
        sequence += [ (['mw_x'], t_pi2_x), ([], t)    ]
        sequence += [ (['laser', 'aom'], laser), ([], wait) ]
        
        # bright state reference
        sequence += n_ref * [ (['laser', 'aom'], laser), ([], wait) ]
        
        # dark state reference
        sequence += n_ref * [ (['mw_y'], t_pi_y), (['laser', 'aom'], laser), ([], wait)  ]

        # start trigger
        sequence += [ (['sequence'], 100)  ]

        
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency', 'power', 'laser', 'wait', 't_pi2_x', 't_pi_x', 't_pi_y', 'delay', 'n_pi', 'n_ref']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_y', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_x', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('delay', width= -80, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('n_ref', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='manipulation'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='detection'
                                            ),
                                     ),
                              ),
                              title='Pi/2 Pi Calibration',
                              )

class Test(Pulsed):
    
    """Test sequence."""

    frequency = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency', label='frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    power = Range(low= -100., high=25., value= -20, desc='microwave power', label='power [dBm]', mode='text', auto_set=False, enter_set=True)

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    t_pi2_x = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length (x)', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_x = Range(low=1., high=100000., value=1000., desc='pi pulse length (x)', label='pi x [ns]', mode='text', auto_set=False, enter_set=True)

    n = Range(low=0, high=100, value=10, desc='number of pulses', label='n', mode='text', auto_set=False, enter_set=True)

    def start_up(self):
        PulseGenerator().Night()
        Microwave().setOutput(self.power, self.frequency)

    def shut_down(self):
        PulseGenerator().Light()
        Microwave().setOutput(None, self.frequency)

    def generate_sequence(self):

        # parameters        
        laser = self.laser
        wait = self.wait
        t_pi2_x = self.t_pi2_x
        t_pi_x = self.t_pi_x
        n = self.n
        
        # start trigger
        sequence = [ (['sequence'], 100)  ]

        # three sequence
        sequence += n * [ (['laser', 'aom'], laser), ([], wait) ]
        sequence += n * [ (['mw'], t_pi_x), (['laser', 'aom'], laser), ([], wait)  ]
        sequence += n * [ (['mw'], t_pi2_x), (['laser', 'aom'], laser), ([], wait)  ]
        
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency', 'power', 'laser', 'wait', 't_pi2_x', 't_pi_x', 'n']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_x', width= -80, enabled_when='state != "run"'),
                                                   Item('n', width= -80, enabled_when='state != "run"'),),
                                            label='manipulation'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='detection'
                                            ),
                                     ),
                              ),
                              title='Test bright, dark and pi/2 reproducability',
                              )

class TestBright(Pulsed):
    
    """Test sequence."""

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    n = Range(low=0, high=100, value=10, desc='number of pulses', label='n', mode='text', auto_set=False, enter_set=True)

    def start_up(self):
        PulseGenerator().Night()

    def shut_down(self):
        PulseGenerator().Light()

    def generate_sequence(self):

        # parameters        
        laser = self.laser
        wait = self.wait
        n = self.n
        
        sequence = [ (['sequence'], 100)  ] + n * [ (['laser', 'aom'], laser), ([], wait) ]

        return sequence

    get_set_items = Pulsed.get_set_items + ['laser', 'wait', 'n']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('n', width= -80, enabled_when='state != "run"'),),
                                            label='manipulation'),
                                     VGroup(HGroup(Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='detection'
                                            ),
                                     ),
                              ),
                              title='Bright state detection',
                              )

class SingletDecay(Pulsed):
    
    """Singlet Decay."""

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=0., high=1e8, value=0., desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e9, value=300., desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=3., desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)

    tau = Array(value=np.array((0., 1.)))

    def apply_parameters(self):
        """Overwrites apply_parameters() from pulsed. Prior to generating sequence, etc., generate the tau mesh."""
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        Pulsed.apply_parameters(self)

    def start_up(self):
        PulseGenerator().Night()

    def shut_down(self):
        PulseGenerator().Light()

    def generate_sequence(self):

        tau = self.tau
        laser = self.laser

        sequence = [ (['sequence'], 100) ]
        for t in tau:
            sequence += [  ([], t), (['laser', 'aom'], laser)  ]
        return sequence

    get_set_items = Pulsed.get_set_items + ['tau_begin', 'tau_end', 'tau_delta', 'laser', 'tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='manipulation'),
                                     VGroup(HGroup(Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='detection'
                                            ),
                                     ),
                              ),
                              title='Singlet decay',
                              )
    
class SingletDecayDouble(PulsedTau):
    
    """Singlet Decay."""

    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)

    def start_up(self):
        PulseGenerator().Night()

    def shut_down(self):
        PulseGenerator().Light()

    def generate_sequence(self):

        tau = self.tau
        laser = self.laser

        sequence = [ (['sequence'], 100) ]
        for t in tau:
            sequence += [  ([], t), (['laser', 'aom'], laser)  ]
        for t in tau[::-1]:
            sequence += [  ([], t), (['laser', 'aom'], laser)  ]
        return sequence

    get_set_items = Pulsed.get_set_items + ['tau_begin', 'tau_end', 'tau_delta', 'laser', 'tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='manipulation'),
                                     VGroup(HGroup(Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='detection'
                                            ),
                                     ),
                              ),
                              title='Singlet decay double',
                              )
    
class Hahn(Rabi):
    
    """Defines a Hahn-Echo measurement."""

    t_pi2 = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length', label='pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi = Range(low=1., high=100000., value=1000., desc='pi pulse length', label='pi [ns]', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2 = self.t_pi2
        t_pi = self.t_pi
        sequence = []
        for t in tau:
            sequence += [  (['mw','mw_x'], t_pi2), ([], 0.5 * t), (['mw','mw_x'], t_pi), ([], 0.5 * t), (['mw','mw_x'], t_pi2), (['laser', 'aom'], laser), ([], wait)  ]
        sequence += [  (['sequence'], 100)  ]
        return sequence

    get_set_items = Rabi.get_set_items + ['t_pi2', 't_pi']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'
                                            ),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'
                                            ),
                                     ),
                              ),
                       title='Hahn-Echo Measurement',
                       )
    
class Hahn3pi2(Rabi):
    
    """Defines a Hahn-Echo measurement with both pi/2 and 3pi/2 readout pulse."""

    t_pi2 = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length', label='pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi = Range(low=1., high=100000., value=1000., desc='pi pulse length', label='pi [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2 = Range(low=1., high=100000., value=1000., desc='3pi/2 pulse length', label='3pi/2 [ns]', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2 = self.t_pi2
        t_pi = self.t_pi
        t_3pi2 = self.t_3pi2
        sequence = []
        for t in tau:
            sequence += [  (['mw','mw_x'], t_pi2), ([], 0.5 * t), (['mw','mw_x'], t_pi), ([], 0.5 * t), (['mw','mw_x'], t_pi2), (['laser', 'aom'], laser), ([], wait)  ]
        for t in tau:
            sequence += [  (['mw','mw_x'], t_pi2), ([], 0.5 * t), (['mw','mw_x'], t_pi), ([], 0.5 * t), (['mw','mw_x'], t_3pi2), (['laser', 'aom'], laser), ([], wait)  ]
        sequence += [  (['sequence'], 100)  ]
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'
                                            ),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'
                                            ),
                                     ),
                              ),
                       title='Hahn-Echo Measurement with both pi/2 and 3pi/2 readout pulse',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi2', 't_pi', 't_3pi2']

class CPMG3pi2(Rabi):
    
    """
    Defines a CPMG measurement with both pi/2 and 3pi/2 readout pulse,
    using a second microwave switch for 90 degree phase shifted pi pulses.
    
    Includes also bright (no pulse) and dark (pi_y pulse) reference points.
    """

    t_pi2_x = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length (x)', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_y = Range(low=1., high=100000., value=1000., desc='pi pulse length (y)', label='pi y [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2_x = Range(low=1., high=100000., value=1000., desc='3pi/2 pulse length (x)', label='3pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    n_pi = Range(low=1, high=100, value=5, desc='number of pi pulses', label='n pi', mode='text', auto_set=False, enter_set=True)
    n_ref = Range(low=0, high=100, value=0, desc='number of reference pulses', label='n ref', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_x = self.t_pi2_x
        t_pi_y = self.t_pi_y
        t_3pi2_x = self.t_3pi2_x
        n_pi = self.n_pi
        n_ref = self.n_ref
        sequence = []
        for t in tau:
            sequence += [ (['mw_x'], t_pi2_x), ([], t / float(2 * n_pi))  ]
            sequence += (n_pi - 1) * [ (['mw_y'], t_pi_y), ([], t / float(n_pi))    ] 
            sequence += [ (['mw_y'], t_pi_y), ([], t / float(2 * n_pi))  ]
            sequence += [ (['mw_x'], t_pi2_x)                              ]
            sequence += [ (['laser', 'aom'], laser), ([], wait)             ]
        for t in tau:
            sequence += [ (['mw_x'], t_pi2_x), ([], t / float(2 * n_pi))  ]
            sequence += (n_pi - 1) * [ (['mw_y'], t_pi_y), ([], t / float(n_pi))    ] 
            sequence += [ (['mw_y'], t_pi_y), ([], t / float(2 * n_pi))  ]
            sequence += [ (['mw_x'], t_3pi2_x)                             ]
            sequence += [ (['laser', 'aom'], laser), ([], wait)             ]            
        sequence += n_ref * [ (['laser', 'aom'], laser), ([], wait)       ]
        sequence += n_ref * [ (['mw_y'], t_pi_y), (['laser', 'aom'], laser), ([], wait)      ]
        sequence += [ (['sequence'], 100)                        ]
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_y', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('n_ref', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'
                                            ),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'
                                            ),
                                     ),
                              ),
                       title='CPMG Measurement with both pi/2 and 3pi/2 readout pulse',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi2_x', 't_pi_y', 't_3pi2_x', 'n_pi', 'n_ref']


class XY83pi2(Rabi):
    
    """
    Defines a XY8 measurement with both pi/2 and 3pi/2 readout pulse,
    using a second microwave switch for 90 degree phase shifted pi pulses.
    
    Includes also bright (no pulse) and dark (pi_y pulse) reference points.
    """

    t_pi2_x = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length (x)', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_x = Range(low=1., high=100000., value=1000., desc='pi pulse length (x)', label='pi x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_y = Range(low=1., high=100000., value=1000., desc='pi pulse length (y)', label='pi y [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2_x = Range(low=1., high=100000., value=1000., desc='3pi/2 pulse length (x)', label='3pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    n_pi = Range(low=1, high=100, value=4, desc='number of pi pulses', label='n pi', mode='text', auto_set=False, enter_set=True)
    n_ref = Range(low=0, high=100, value=0, desc='number of reference pulses', label='n ref', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_x = self.t_pi2_x
        t_pi_x = self.t_pi_x
        t_pi_y = self.t_pi_y
        t_3pi2_x = self.t_3pi2_x
        n_pi = self.n_pi
        n_ref = self.n_ref
        sequence = []
        for t in tau:
            sequence += [ (['mw_x'], t_pi2_x), ([], t / float(2 * n_pi))  ]
            sequence += int(n_pi / 4) * [ (['mw_x'], t_pi_x), ([], t / float(n_pi)), (['mw_y'], t_pi_y), ([], t / float(n_pi))] 
            sequence += int(n_pi / 4 - 1) * [ (['mw_y'], t_pi_y), ([], t / float(n_pi)), (['mw_x'], t_pi_x), ([], t / float(n_pi))] 
            sequence += [ (['mw_y'], t_pi_y), ([], t / float(n_pi)), (['mw_x'], t_pi_x), ([], t / float(2 * n_pi)), (['mw_x'], t_pi2_x)]
            sequence += [ (['laser', 'aom'], laser), ([], wait)             ]
        for t in tau:
            sequence += [ (['mw_x'], t_pi2_x), ([], t / float(2 * n_pi))  ]
            sequence += int(n_pi / 4) * [ (['mw_x'], t_pi_x), ([], t / float(n_pi)), (['mw_y'], t_pi_y), ([], t / float(n_pi))] 
            sequence += int(n_pi / 4 - 1) * [ (['mw_y'], t_pi_y), ([], t / float(n_pi)), (['mw_x'], t_pi_x), ([], t / float(n_pi))] 
            sequence += [ (['mw_y'], t_pi_y), ([], t / float(n_pi)), (['mw_x'], t_pi_x), ([], t / float(2 * n_pi)), (['mw_x'], t_3pi2_x)]
            sequence += [ (['laser', 'aom'], laser), ([], wait)             ]            
        #sequence += n_ref * [ (['laser', 'aom'], laser), ([], wait)       ]
        #sequence += n_ref * [ (['mw_y'], t_pi_y), (['laser', 'aom'], laser), ([], wait)      ]
        sequence += [ (['sequence'], 100)                        ]
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_y', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('n_ref', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'
                                            ),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'
                                            ),
                                     ),
                              ),
                       title='XY8 Measurement with both pi/2 and 3pi/2 readout pulse',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi2_x', 't_pi_x','t_pi_y', 't_3pi2_x', 'n_pi', 'n_ref']


class CP(Rabi):
    
    """Defines a CP measurement."""

    t_pi2 = Range(low=1., high=100000., value=1000., desc='pi/2 x pulse length', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi = Range(low=1., high=100000., value=1000., desc='pi y pulse length', label='pi y [ns]', mode='text', auto_set=False, enter_set=True)
    n_pi = Range(low=1, high=100, value=5, desc='number of pi pulses', label='n pi', mode='text', auto_set=False, enter_set=True)
    
    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2 = self.t_pi2
        t_pi = self.t_pi
        n_pi = self.n_pi
        
        sequence = []
        for t in tau:
            sequence += [ (['mw_x','mw'], t_pi2), ([], t / float(2 * n_pi)) ]
            sequence += (n_pi - 1) * [ (['mw_x','mw'], t_pi), ([], t / float(n_pi))   ] 
            sequence += [ (['mw_x','mw'], t_pi), ([], t / float(2 * n_pi)) ]
            sequence += [ (['mw_x','mw'], t_pi2)                             ]
            sequence += [ (['laser', 'aom'], laser), ([], wait)            ]
        sequence += [ (['sequence'], 100)                        ]
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='CP Measurement',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi2', 't_pi', 'n_pi']



class CPMG(Rabi):
    
    """Defines a basic CPMG measurement with a single sequence and bright / dark reference points."""

    t_pi2_x = Range(low=1., high=100000., value=1000., desc='pi/2 x pulse length', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_y = Range(low=1., high=100000., value=1000., desc='pi y pulse length', label='pi y [ns]', mode='text', auto_set=False, enter_set=True)
    n_pi = Range(low=1, high=100, value=5, desc='number of pi pulses', label='n pi', mode='text', auto_set=False, enter_set=True)
    n_ref = Range(low=1, high=100, value=10, desc='number of reference pulses', label='n ref', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_x = self.t_pi2_x
        t_pi_y = self.t_pi_y
        n_pi = self.n_pi
        n_ref = self.n_ref
        sequence = []
        for t in tau:
            sequence += [ (['mw_x','mw'], t_pi2_x), ([], t / float(2 * n_pi)) ]
            sequence += (n_pi - 1) * [ (['mw_y','mw'], t_pi_y), ([], t / float(n_pi))   ] 
            sequence += [ (['mw_y','mw'], t_pi_y), ([], t / float(2 * n_pi)) ]
            sequence += [ (['mw_x','mw'], t_pi2_x)                             ]
            sequence += [ (['laser', 'aom'], laser), ([], wait)            ]
        sequence += n_ref * [ (['laser', 'aom'], laser), ([], wait)       ]
        sequence += n_ref * [ (['mw_y'], t_pi_y), (['laser', 'aom'], laser), ([], wait)      ]
        sequence += [ (['sequence'], 100)                        ]
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_y', width= -80, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('n_ref', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='Basic CPMG Measurement with pi/2 pulse on B and pi pulses on A',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi2_x', 't_pi_y', 'n_pi', 'n_ref']

class CPMGxy(Rabi):
    
    """
    Defines a CPMG measurement with both pi_x and pi_y pulses.

    Includes also bright (no pulse) and dark (pi_y pulse) reference points.
    """

    t_pi2_x = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length (x)', label='pi/2 x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_x = Range(low=1., high=100000., value=1000., desc='pi pulse length (x)', label='pi x [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_y = Range(low=1., high=100000., value=1000., desc='pi pulse length (y, 90 degree)', label='pi y [ns]', mode='text', auto_set=False, enter_set=True)
    n_pi = Range(low=1, high=100, value=5, desc='number of pi pulses', label='n pi', mode='text', auto_set=False, enter_set=True)
    n_ref = Range(low=1, high=100, value=10, desc='number of reference pulses', label='n ref', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_x = self.t_pi2_x
        t_pi_x = self.t_pi_x
        t_pi_y = self.t_pi_y
        n_pi = self.n_pi
        n_ref = self.n_ref
        sequence = []
        for t in tau:
            sequence += [ (['mw_x'], t_pi2_x), ([], t / float(2 * n_pi))  ]
            sequence += (n_pi - 1) * [ (['mw_x'], t_pi_x), ([], t / float(n_pi))    ] 
            sequence += [ (['mw_x'], t_pi_x), ([], t / float(2 * n_pi))  ]
            sequence += [ (['mw_x'], t_pi2_x)                              ]
            sequence += [ (['laser', 'aom'], laser), ([], wait)             ]
        for t in tau:
            sequence += [ (['mw_x'], t_pi2_x), ([], t / float(2 * n_pi))  ]
            sequence += (n_pi - 1) * [ (['mw_y'], t_pi_y), ([], t / float(n_pi))    ] 
            sequence += [ (['mw_y'], t_pi_y), ([], t / float(2 * n_pi))  ]
            sequence += [ (['mw_x'], t_pi2_x)                              ]
            sequence += [ (['laser', 'aom'], laser), ([], wait)             ]            
        sequence += n_ref * [ (['laser', 'aom'], laser), ([], wait)        ]
        sequence += n_ref * [ (['mw_y'], t_pi_y), (['laser', 'aom'], laser), ([], wait)      ]
        sequence += [ (['sequence'], 100)                         ]
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('t_pi2_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_x', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_y', width= -80, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -80, enabled_when='state != "run"'),
                                                   Item('n_ref', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='CPMG Measurement with both pix and piys pulses',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi2_x', 't_pi_x', 't_pi_y', 'n_pi', 'n_ref']

class T1pi(Rabi):
    
    """Defines a T1 measurement with pi pulse."""

    t_pi = Range(low=1., high=100000., value=1000., desc='pi pulse length', label='pi [ns]', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi = self.t_pi
        sequence = []
        for t in tau:
            sequence.append(([       ], t))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([       ], wait))
        for t in tau:
            sequence.append((['mw' ,'mw_x'  ], t_pi))
            sequence.append(([       ], t))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([       ], wait))
        sequence.append((['sequence'], 100))
        return sequence

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='T1pi',
                       )
    
    get_set_items = Rabi.get_set_items + ['t_pi']

class T1Meta(Rabi):
    
    """T1 measurement of metastable state."""

    t_pi = Range(low=0., high=100000., value=1000., desc='pi pulse length', label='pi [ns]', mode='text', auto_set=False, enter_set=True)
    delay = Range(low=0., high=1000., value=450., desc='delay of AOM relative to trigger', label='AOM delay [ns]', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi = self.t_pi
        delay = self.delay
        s1 = []
        s2 = []
        s2.append(([], delay + wait))
        for t in tau:
            s1.append(([       ], wait + t_pi + t))
            s1.append((['laser', 'aom'], laser))
            s2.append((['mw'   ], t_pi))
            s2.append(([       ], t + laser + wait))
        s1.append(([          ], 1000))
        s1.append((['sequence'], 100))
        s2.pop()
        """
        s1.append( (['aom'],  laser   ) )
        s2.append( ([],  delay+laser+wait  ) )
        for t in tau:
            s1.append(  ([       ],  wait + t_pi + t  )  )
            s1.append(  (['laser','aom'],  laser      )  )
            s2.append(  (['mw'   ],  t_pi             )  )
            s2.append(  ([       ],  t+laser+wait     )  )
        s1.append(  ([          ], 1000  )  )
        s1.append(  (['sequence'], 100   )  )
        s2.pop()
        """
        return sequence_union(s1, s2)

    get_set_items = Rabi.get_set_items + ['t_pi', 'delay']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('delay', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='T1Meta',
                       )
    
class FID3pi2(Rabi):
    
    """Defines a FID measurement with both pi/2 and 3pi/2 readout pulse."""

    t_pi2 = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length', label='pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2 = Range(low=1., high=100000., value=1000., desc='3pi/2 pulse length', label='3pi/2 [ns]', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2 = self.t_pi2
        t_3pi2 = self.t_3pi2
        sequence = []
        for t in tau:
            sequence.append((['mw','mw_x'], t_pi2))
            sequence.append(([       ], t))
            sequence.append((['mw','mw_x'   ], t_pi2))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([       ], wait))
        for t in tau:
            sequence.append((['mw','mw_x'   ], t_pi2))
            sequence.append(([       ], t))
            sequence.append((['mw','mw_x'   ], t_3pi2))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([       ], wait))
        sequence.append((['sequence'], 100))
        return sequence
    
    #items to be saved
    get_set_items = Rabi.get_set_items + ['t_pi2', 't_3pi2']

    # gui elements
    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='FID3pi2',
                       )
  
class HardDQTFID(Rabi):
    
    """Defines a Double Quantum Transition FID Measurement with pi-tau-pi."""

    t_pi = Range(low=1., high=100000., value=1000., desc='pi pulse length', label='pi [ns]', mode='text', auto_set=False, enter_set=True)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi = self.t_pi
        sequence = []
        for t in tau:
            sequence.append((['mw'   ], t_pi))
            sequence.append(([       ], t))
            sequence.append((['mw'   ], t_pi))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([       ], wait))
        sequence.append((['sequence'], 100))
        return sequence

    get_set_items = Rabi.get_set_items + ['t_pi']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi', width= -80, enabled_when='state != "run"'),),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                                     ),
                              ),
                       title='HardDQTFID',
                       )

"""
class HardDQTFIDTauMod( HardDQTFID ):
    tau_gen = Code("tg = np.arange(self.tau_begin, self.tau_end, self.tau_delta)\ntf = np.arange(0., 500., 50.)\ntau = np.array(())\nfor t0 in tg:\n   tau=np.append(tau,tf+t0)\nself.tau=tau")
    def start_up(self):
        # this needs to come first, because Pulsed.start_up() will
        # generate the sequence and thereby call the generate_sequence method of RabiMeasurement
        # and this method needs the correct tau 
        exec self.tau_gen
        Pulsed.start_up(self)
        PulseGenerator().Night()
        Microwave().setOutput(self.power, self.frequency)
        
    traits_view = View( VGroup( HGroup(Item('state', show_label=False, style='custom',
                                            editor=EnumEditor(values={'idle':'1:idle','run':'2:run',},cols=2),),),
                                Tabbed( VGroup(HGroup(Item('frequency',     width=-80, enabled_when='state != "run"'),
                                                      Item('power',         width=-80, enabled_when='state != "run"'),
                                                      Item('t_pi',          width=-80, enabled_when='state != "run"'),),
                                               HGroup(Item('tau_begin',     width=-80, enabled_when='state != "run"'),
                                                      Item('tau_end',       width=-80, enabled_when='state != "run"'),
                                                      Item('tau_delta',     width=-80, enabled_when='state != "run"'),),
                                               label='parameter'),
                                        VGroup(HGroup(Item('laser',         width=-80, enabled_when='state != "run"'),
                                                      Item('wait',          width=-80, enabled_when='state != "run"'),
                                                      Item('record_length', width=-80, enabled_when='state != "run"'),
                                                      Item('bin_width',     width=-80, enabled_when='state != "run"'),),
                                               label='settings'),
                                        VGroup(HGroup(Item('tau_begin',     width=-80, enabled_when='state != "run"'),
                                                      Item('tau_end',       width=-80, enabled_when='state != "run"'),
                                                      Item('tau_delta',     width=-80, enabled_when='state != "run"'),),
                                                Item('tau_gen',   width=-200, height=-200, enabled_when='state != "run"'),
                                               label='taumod'),
                                            
                                ),
                        ),
                        title='HardDQTFIDTauMod',
                  )
"""

class DQTFID3pi2(Pulsed):
    
    """Defines a pulsed measurement with two microwave transitions and FID sequence including 3pi2 readout pulses.TODO: untested"""
    frequency_a = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency A', label='frequency A [Hz]', mode='text', auto_set=False, enter_set=True)
    frequency_b = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency B', label='frequency B [Hz]', mode='text', auto_set=False, enter_set=True)
    power_a = Range(low= -100., high=25., value= -20, desc='microwave power A', label='power A [dBm]', mode='text', auto_set=False, enter_set=True)
    power_b = Range(low= -100., high=25., value= -20, desc='microwave power B', label='power B [dBm]', mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=1., high=1e8, value=10.0, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=500., desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=50., desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    t_pi2_a = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length A', label='pi/2 A [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_a = Range(low=1., high=100000., value=1000., desc='pi pulse length A', label='pi A [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2_a = Range(low=1., high=100000., value=1000., desc='3pi/2 pulse length A', label='3pi/2 A [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi2_b = Range(low=1., high=100000., value=1000., desc='pi/2 pulse length B', label='pi/2 B [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_b = Range(low=1., high=100000., value=1000., desc='pi pulse length B', label='pi B [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2_b = Range(low=1., high=100000., value=1000., desc='3pi/2 pulse length B', label='3pi/2 B [ns]', mode='text', auto_set=False, enter_set=True)

    tau = Array(value=np.array((0., 1.)))

    def start_up(self):
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        PulseGenerator().Night()
        MicrowaveA().setOutput(self.power_a, self.frequency_a)
        MicrowaveB().setOutput(self.power_b, self.frequency_b)

    def shut_down(self):
        PulseGenerator().Light()
        MicrowaveA().setOutput(None, self.frequency_a)
        MicrowaveB().setOutput(None, self.frequency_b)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_a = self.t_pi2_a
        t_pi_a = self.t_pi_a
        t_3pi2_a = self.t_3pi2_a
        t_pi2_b = self.t_pi2_b
        t_pi_b = self.t_pi_b
        t_3pi2_b = self.t_3pi2_b
        sequence = []
        for t in tau:
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append((['mw_b'   ], t_pi_b))
            sequence.append(([         ], t))
            sequence.append((['mw_b'   ], t_pi_b))
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([         ], wait))
        for t in tau:
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append((['mw_b'   ], t_pi_b))
            sequence.append(([         ], t))
            sequence.append((['mw_b'   ], t_pi_b))
            sequence.append((['mw_a'   ], t_3pi2_a))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([         ], wait))
        sequence.append((['sequence'], 100))
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency_a', 'frequency_b', 'power_a', 'power_b',
                                                       't_pi2_a', 't_pi_a', 't_3pi2_a', 't_pi2_b', 't_pi_b', 't_3pi2_b',
                                                       'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency_a', width= -80, enabled_when='state != "run"'),
                                                   Item('power_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2_a', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('frequency_b', width= -80, enabled_when='state != "run"'),
                                                   Item('power_b', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2_b', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_b', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2_b', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                                   label='settings'),
                                     ),
                              ),
                       title='DQTFID3pi2 Measurement',
                       )

class DQTRabi(Pulsed):
    """Defines a pulsed measurement with two microwave transitions and Rabi"""
    frequency_a = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency A', label='frequency A [Hz]', mode='text', auto_set=False, enter_set=True)
    frequency_b = Range(low=1, high=20e9, value=2.8705e9, desc='microwave frequency B', label='frequency B [Hz]', mode='text', auto_set=False, enter_set=True)
    power_a = Range(low= -100., high=25., value= -2, desc='microwave power A', label='power A [dBm]', mode='text', auto_set=False, enter_set=True)
    power_b = Range(low= -100., high=25., value=4, desc='microwave power B', label='power B [dBm]', mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=1., high=1e8, value=10.0, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=1000., desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=5., desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    t_pi2_a = Range(low=1., high=100000., value=50., desc='pi/2 pulse length A', label='pi/2 A [ns]', mode='text', auto_set=False, enter_set=True)
    t_pi_a = Range(low=1., high=100000., value=100., desc='pi pulse length A', label='pi A [ns]', mode='text', auto_set=False, enter_set=True)
    tau_a = Range(low=1., high=100000., value=1000., desc='hahn echo wait time for A', label='Tau A [ns]', mode='text', auto_set=False, enter_set=True)
     
    tau = Array(value=np.array((0., 1.)))

    def start_up(self):
        if self.tau_end > (self.t_pi_a + self.tau_a):
            self.tau_end = self.t_pi_a + self.tau_a
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        PulseGenerator().Night()
        MicrowaveA().setOutput(self.power_a, self.frequency_a)
        MicrowaveB().setOutput(self.power_b, self.frequency_b)

    def shut_down(self):
        PulseGenerator().Light()
        MicrowaveA().setOutput(None, self.frequency_a)
        MicrowaveB().setOutput(None, self.frequency_b)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_a = self.t_pi2_a
        t_pi_a = self.t_pi_a
        tau_a = self.tau_a
        sequence = []
        for t in tau:
            sequence.append((['mw_a'   ], t_pi2_a))
            #sequence.append(  ([         ],  tau_a        )  )
            if t > t_pi_a:
                """
                sequence.append(  (['mw_a','mw_b' ],  t_pi_a  )  )
                sequence.append(  (['mw_b' ],  (t-t_pi_a)  )  )
                sequence.append(  ([         ],  (tau_a- (t-t_pi_a))       )  )
                """
                sequence.append(([         ], tau_a - (t - t_pi_a) / 2.0))
                sequence.append((['mw_b' ], (t - t_pi_a) / 2.0))
                sequence.append((['mw_a', 'mw_b' ], t_pi_a))
                sequence.append((['mw_b' ], (t - t_pi_a) / 2.0))
                sequence.append(([         ], tau_a - (t - t_pi_a) / 2.0))
            else:
                """
                sequence.append(  (['mw_a','mw_b' ],  t  )  )
                sequence.append(  (['mw_a' ],  (t_pi_a-t)  )  )
                sequence.append(  ([         ],  tau_a        )  )
                """
                sequence.append(([         ], tau_a))
                sequence.append((['mw_a' ], (t_pi_a - t) / 2.0))
                sequence.append((['mw_a', 'mw_b' ], t))
                sequence.append((['mw_a' ], (t_pi_a - t) / 2.0))
                sequence.append(([         ], tau_a))
                
                
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([         ], wait))
        sequence.append((['sequence'], 100))
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency_a', 'frequency_b', 'power_a', 'power_b',
                                                       't_pi2_a', 't_pi_a',
                                                       'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'tau', 'tau_a']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency_a', width= -80, enabled_when='state != "run"'),
                                                   Item('power_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi_a', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_a', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('frequency_b', width= -80, enabled_when='state != "run"'),
                                                   Item('power_b', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                                   label='settings'),
                                     ),
                              ),
                       title='DQTRabi Measurement, use rabi to fit it',
                       )

class HH(Pulsed):
    """Defines a HartmannHahn measurement with two microwave transitions and Rabi"""
    frequency_a = Range(low=1, high=20e9, value=2.61e9, desc='microwave frequency A', label='frequency A [Hz]', mode='text', auto_set=False, enter_set=True)
    frequency_b = Range(low=1, high=20e9, value=280.0e6, desc='microwave frequency B', label='frequency B [Hz]', mode='text', auto_set=False, enter_set=True)
    power_a = Range(low= -100., high=25., value=5.0, desc='microwave power A', label='power A [dBm]', mode='text', auto_set=False, enter_set=True)
    power_b = Range(low= -100., high=25., value=8.0, desc='microwave power B', label='power B [dBm]', mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=1., high=1e8, value=15.0, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=30.0e3, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=3.0e2, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    t_pi2_a = Range(low=1., high=100000., value=45., desc='pi/2 pulse length A', label='pi/2 A [ns]', mode='text', auto_set=False, enter_set=True)
    tau_a = Range(low=1., high=100000., value=15., desc='hahn echo wait time for A', label='Tau A [ns]', mode='text', auto_set=False, enter_set=True)
     
    tau = Array(value=np.array((0., 1.)))

    def start_up(self):
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        PulseGenerator().Night()
        MicrowaveA().setOutput(self.power_a, self.frequency_a)
        MicrowaveB().setOutput(self.power_b, self.frequency_b)

    def shut_down(self):
        PulseGenerator().Light()
        MicrowaveA().setOutput(None, self.frequency_a)
        MicrowaveB().setOutput(None, self.frequency_b)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_a = self.t_pi2_a
        tau_a = self.tau_a
        sequence = []
        for t in tau:
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append(([         ], tau_a))
            sequence.append((['mw_c', 'mw_b' ], t))
            sequence.append(([         ], tau_a))
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([         ], wait))
        sequence.append((['sequence'], 100))
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency_a', 'frequency_b', 'power_a', 'power_b', 't_pi2_a',
                                                       'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'tau', 'tau_a']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency_a', width= -80, enabled_when='state != "run"'),
                                                   Item('power_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2_a', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_a', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('frequency_b', width= -80, enabled_when='state != "run"'),
                                                   Item('power_b', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                                   label='settings'),
                                     ),
                              ),
                       title='HartmannHahn Measurement, use rabi to fit or pulsed ',
                       )

class HH3pi2(Pulsed):
    """Defines a HartmannHahn measurement with two microwave transitions and Rabi"""
    frequency_a = Range(low=1, high=20e9, value=2.61e9, desc='microwave frequency A', label='frequency A [Hz]', mode='text', auto_set=False, enter_set=True)
    frequency_b = Range(low=1, high=20e9, value=280.0e6, desc='microwave frequency B', label='frequency B [Hz]', mode='text', auto_set=False, enter_set=True)
    power_a = Range(low= -100., high=25., value=5.0, desc='microwave power A', label='power A [dBm]', mode='text', auto_set=False, enter_set=True)
    power_b = Range(low= -100., high=25., value=8.0, desc='microwave power B', label='power B [dBm]', mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=1., high=1e8, value=15.0, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=30.0e3, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=3.0e2, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)

    t_pi2_a = Range(low=1., high=100000., value=45., desc='pi/2 pulse length A', label='pi/2 A [ns]', mode='text', auto_set=False, enter_set=True)
    t_3pi2_a = Range(low=1., high=100000., value=135., desc='3pi/2 pulse length A', label='3pi/2 A [ns]', mode='text', auto_set=False, enter_set=True)
    tau_a = Range(low=1., high=100000., value=15., desc='hahn echo wait time for A', label='Tau A [ns]', mode='text', auto_set=False, enter_set=True)
     
    tau = Array(value=np.array((0., 1.)))

    def start_up(self):
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        PulseGenerator().Night()
        MicrowaveA().setOutput(self.power_a, self.frequency_a)
        MicrowaveB().setOutput(self.power_b, self.frequency_b)

    def shut_down(self):
        PulseGenerator().Light()
        MicrowaveA().setOutput(None, self.frequency_a)
        MicrowaveB().setOutput(None, self.frequency_b)

    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        t_pi2_a = self.t_pi2_a
        tau_a = self.tau_a
        t_3pi2_a = self.t_3pi2_a
        sequence = []
        for t in tau:
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append(([         ], tau_a))
            sequence.append((['mw_c', 'mw_b' ], t))
            sequence.append(([         ], tau_a))
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([         ], wait))
        for t in tau:    
            sequence.append((['mw_a'   ], t_pi2_a))
            sequence.append(([         ], tau_a))
            sequence.append((['mw_c', 'mw_b' ], t))
            sequence.append(([         ], tau_a))
            sequence.append((['mw_a'   ], t_3pi2_a))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([         ], wait))
        sequence.append((['sequence'], 100))
        return sequence

    get_set_items = Pulsed.get_set_items + ['frequency_a', 'frequency_b', 'power_a', 'power_b', 't_pi2_a',
                                                       'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'tau', 'tau_a']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('frequency_a', width= -80, enabled_when='state != "run"'),
                                                   Item('power_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_pi2_a', width= -80, enabled_when='state != "run"'),
                                                   Item('t_3pi2_a', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_a', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('frequency_b', width= -80, enabled_when='state != "run"'),
                                                   Item('power_b', width= -80, enabled_when='state != "run"'),
                                            ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   Item('stop_time'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('wait', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                                   label='settings'),
                                     ),
                              ),
                       title='HartmannHahn Measurement 3pi/2, use t1pi to fit',
                       )

class DEER(Pulsed):
    
    mw1_power = Range(low= -100., high=25., value=5.0, desc='MW1 Power [dBm]', label='MW1 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    mw1_frequency = Range(low=1., high=20.e9, value=2.61e9, desc='MW1 frequency [Hz]', label='MW1 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi2 = Range(low=1., high=100000., value=83., desc='length of pi/2 pulse of mw1 [ns]', label='mw1 pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi = Range(low=1., high=100000., value=166., desc='length of pi pulse of mw1 [ns]', label='mw1 pi [ns]', mode='text', auto_set=False, enter_set=True)
    mw2_power = Range(low= -100., high=25., value=7.0, desc='MW2 Power [dBm]', label='MW2 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    rf_begin = Range(low=1, high=20e9, value=100.0e6, desc='Start Frequency [Hz]', label='Begin [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    rf_end = Range(low=1, high=20e9, value=400.0e6, desc='Stop Frequency [Hz]', label='End [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    rf_delta = Range(low=1e-3, high=20e9, value=2.0e6, desc='frequency step [Hz]', label='Delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    t_mw2_pi = Range(low=1., high=100000., value=90., desc='length of pi pulse of mw2 [ns]', label='mw2 pi [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=10000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    tau = Range(low=1., high=100000., value=300., desc='tau [ns]', label='tau [ns]', mode='text', auto_set=False, enter_set=True)
    seconds_per_point = Range(low=20e-3, high=1, value=0.2, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
 
    sweeps_per_point = Int()
    run_time = Float(value=0.0)
        
    frequencies = Array(value=np.array((0., 1.)))   
    
      
    def generate_sequence(self):
        if self.t_mw1_pi > self.t_mw2_pi:
            return 100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw2_pi), (['mw_a'], (self.t_mw1_pi - self.t_mw2_pi)), ([], self.tau), (['mw_a'], self.t_mw1_pi2) , (['sequence'], 10)]
        else:
            return 100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw1_pi), (['mw_b'], (self.t_mw2_pi - self.t_mw1_pi)), ([], (self.tau - (self.t_mw2_pi - self.t_mw1_pi))), (['mw_a'], self.t_mw1_pi2) , (['sequence'], 10)]
        
    
    def apply_parameters(self):
        """Apply the current parameters and decide whether to keep previous data."""

        frequencies = np.arange(self.rf_begin, self.rf_end + self.rf_delta, self.rf_delta)
        n_bins = int(self.record_length / self.bin_width)
        time_bins = self.bin_width * np.arange(n_bins)
        sequence = self.generate_sequence()

        if not (self.keep_data and sequence == self.sequence and np.all(time_bins == self.time_bins) and np.all(frequencies == self.frequencies)): # if the sequence and time_bins are the same as previous, keep existing data
            self.count_data = np.zeros((len(frequencies), n_bins))
            self.run_time = 0.0
        
        self.frequencies = frequencies
        self.sequence = sequence 
        self.time_bins = time_bins
        self.n_bins = n_bins
        self.sweeps_per_point = int(np.max((1, int(self.seconds_per_point * 1e9 / (self.laser + self.wait + 2 * (self.t_mw1_pi2 + self.tau) + self.t_mw1_pi)))))
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.
    

    def _run(self):
        """Acquire data."""
        
        try: # try to run the acquisition from start_up to shut_down
            self.state = 'run'
            self.apply_parameters()
            PulseGenerator().Night()
            Microwave().setOutput(self.mw1_power, self.mw1_frequency)
            MicrowaveB().setPower(self.mw2_power)
            tagger = TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), 1, 0, 2, 3)
            tagger.setMaxCounts(self.sweeps_per_point)
            PulseGenerator().Sequence(self.sequence)

            while True:

                if self.thread.stop_request.isSet():
                    break

                t_start = time.time()
                
                for i, fi in enumerate(self.frequencies):
                    
                    MicrowaveB().setOutput(self.mw2_power, fi)                    
                    tagger.clear()
                    while not tagger.ready():
                        time.sleep(1.1 * self.seconds_per_point)
                    self.count_data[i, :] += tagger.getData()[0]
                                                            
                self.trait_property_changed('count_data', self.count_data)
                self.run_time += time.time() - t_start
                
            del tagger
            PulseGenerator().Light()
            Microwave().setOutput(None, self.mw1_frequency)
            MicrowaveB().setOutput(None, self.rf_begin)
        finally: # if anything fails, recover
            self.state = 'idle'        
            PulseGenerator().Light()
        
    get_set_items = Pulsed.get_set_items + ['mw1_power', 'mw1_frequency',
                                                    'mw2_power', 'rf_begin', 'rf_end', 'rf_delta', 't_mw2_pi', 't_mw1_pi2', 't_mw1_pi',
                                                       'laser', 'wait', 'seconds_per_point', 'frequencies', 'count_data', 'sequence']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority', width= -40),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw1_power', width= -40, enabled_when='state != "run"'),
                                                   Item('mw1_frequency', width= -120, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi2', width= -40, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi', width= -40, enabled_when='state != "run"'),
                                                   Item('tau', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('mw2_power', width= -40, enabled_when='state != "run"'),
                                                   Item('rf_begin', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('rf_end', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('rf_delta', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('t_mw2_pi', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait', width= -80, enabled_when='state == "idle"'),
                                                   Item('record_length', width= -80, enabled_when='state == "idle"'),
                                                   Item('bin_width', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('seconds_per_point', width= -120, enabled_when='state == "idle"'),
                                                   Item('sweeps_per_point', width= -120, style='readonly'),
                                                   ),
                                            label='settings'
                                            ),
                                     ),
                              ),
                        title='DEER, use frequencies fitting',
                        )

    
    mw1_power = Range(low= -100., high=25., value=5.0, desc='MW1 Power [dBm]', label='MW1 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    mw1_frequency = Range(low=1., high=20.e9, value=2.61e9, desc='MW1 frequency [Hz]', label='MW1 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi2 = Range(low=1., high=100000., value=83., desc='length of pi/2 pulse of mw1 [ns]', label='mw1 pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi = Range(low=1., high=100000., value=166., desc='length of pi pulse of mw1 [ns]', label='mw1 pi [ns]', mode='text', auto_set=False, enter_set=True)
    mw2_power = Range(low= -100., high=25., value=7.0, desc='MW2 Power [dBm]', label='MW2 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    t_mw2_pi2 = Range(low=1., high=100000., value=83., desc='length of pi/2 pulse of mw1 [ns]', label='mw1 pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw2_pi = Range(low=1., high=100000., value=166., desc='length of pi pulse of mw1 [ns]', label='mw1 pi [ns]', mode='text', auto_set=False, enter_set=True)
    tau_begin = Range(low=1., high=1e8, value=15.0, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=30.0e3, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=3.0e2, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=10000., value=4000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    tau = Range(low=1., high=100000., value=300., desc='tau [ns]', label='tau [ns]', mode='text', auto_set=False, enter_set=True)
    seconds_per_point = Range(low=20e-3, high=1, value=0.2, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
 
    sweeps_per_point = Int()
    run_time = Float(value=0.0)
        
    frequencies = Array(value=np.array((0., 1.)))   
    
      
    def generate_sequence(self):
        if self.t_mw1_pi > self.t_mw2_pi:
            return 100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw2_pi), (['mw_a'], (self.t_mw1_pi - self.t_mw2_pi)), ([], self.tau), (['mw_a'], self.t_mw1_pi2) , (['sequence'], 10)]
        else:
            return 100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw1_pi), (['mw_b'], (self.t_mw2_pi - self.t_mw1_pi)), ([], (self.tau - (self.t_mw2_pi - self.t_mw1_pi))), (['mw_a'], self.t_mw1_pi2) , (['sequence'], 10)]
        
    
    def apply_parameters(self):
        """Apply the current parameters and decide whether to keep previous data."""

        frequencies = np.arange(self.rf_begin, self.rf_end + self.rf_delta, self.rf_delta)
        n_bins = int(self.record_length / self.bin_width)
        time_bins = self.bin_width * np.arange(n_bins)
        sequence = self.generate_sequence()

        if not (self.keep_data and sequence == self.sequence and np.all(time_bins == self.time_bins) and np.all(frequencies == self.frequencies)): # if the sequence and time_bins are the same as previous, keep existing data
            self.count_data = np.zeros((len(frequencies), n_bins))
            self.run_time = 0.0
        
        self.frequencies = frequencies
        self.sequence = sequence 
        self.time_bins = time_bins
        self.n_bins = n_bins
        self.sweeps_per_point = int(np.max((1, int(self.seconds_per_point * 1e9 / (self.laser + self.wait + 2 * (self.t_mw1_pi2 + self.tau) + self.t_mw1_pi)))))
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.
    

    def _run(self):
        """Acquire data."""
        
        try: # try to run the acquisition from start_up to shut_down
            self.state = 'run'
            self.apply_parameters()
            PulseGenerator().Night()
            Microwave().setOutput(self.mw1_power, self.mw1_frequency)
            MicrowaveB().setPower(self.mw2_power)
            tagger = TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), 1, 0, 2, 3)
            tagger.setMaxCounts(self.sweeps_per_point)
            PulseGenerator().Sequence(self.sequence)

            while True:

                if self.thread.stop_request.isSet():
                    break

                t_start = time.time()
                
                for i, fi in enumerate(self.frequencies):
                    
                    MicrowaveB().setOutput(self.mw2_power, fi)                    
                    tagger.clear()
                    while not tagger.ready():
                        time.sleep(1.1 * self.seconds_per_point)
                    self.count_data[i, :] += tagger.getData()[0]
                                                            
                self.trait_property_changed('count_data', self.count_data)
                self.run_time += time.time() - t_start
                
            del tagger
            PulseGenerator().Light()
            Microwave().setOutput(None, self.mw1_frequency)
            MicrowaveB().setOutput(None, self.rf_begin)
        finally: # if anything fails, recover
            self.state = 'idle'        
            PulseGenerator().Light()
        
    get_set_items = Pulsed.get_set_items + ['mw1_power', 'mw1_frequency',
                                                    'mw2_power', 'rf_begin', 'rf_end', 'rf_delta', 't_mw2_pi', 't_mw1_pi2', 't_mw1_pi',
                                                       'laser', 'wait', 'seconds_per_point', 'frequencies', 'count_data', 'sequence']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority', width= -40),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw1_power', width= -40, enabled_when='state != "run"'),
                                                   Item('mw1_frequency', width= -120, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi2', width= -40, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi', width= -40, enabled_when='state != "run"'),
                                                   Item('tau', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('mw2_power', width= -40, enabled_when='state != "run"'),
                                                   Item('rf_begin', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('rf_end', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('rf_delta', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('t_mw2_pi', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait', width= -80, enabled_when='state == "idle"'),
                                                   Item('record_length', width= -80, enabled_when='state == "idle"'),
                                                   Item('bin_width', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('seconds_per_point', width= -120, enabled_when='state == "idle"'),
                                                   Item('sweeps_per_point', width= -120, style='readonly'),
                                                   ),
                                            label='settings'
                                            ),
                                     ),
                              ),
                        title='Ce DEER, use Rabi fitting',
                        )

class DEER3pi2(Pulsed):
    
    mw1_power = Range(low= -100., high=25., value=5.0, desc='MW1 Power [dBm]', label='MW1 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    mw1_frequency = Range(low=1., high=20.e9, value=2.61e9, desc='MW1 frequency [Hz]', label='MW1 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi2 = Range(low=1., high=100000., value=83., desc='length of pi/2 pulse of mw1 [ns]', label='mw1 pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi = Range(low=1., high=100000., value=166., desc='length of pi pulse of mw1 [ns]', label='mw1 pi [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw1_3pi2 = Range(low=1., high=100000., value=250., desc='length of 3pi/2 pulse of mw1 [ns]', label='mw1 3pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    mw2_power = Range(low= -100., high=25., value=7.0, desc='MW2 Power [dBm]', label='MW2 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    rf_begin = Range(low=1, high=20e9, value=100.0e6, desc='Start Frequency [Hz]', label='Begin [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    rf_end = Range(low=1, high=20e9, value=400.0e6, desc='Stop Frequency [Hz]', label='End [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    rf_delta = Range(low=1e-3, high=20e9, value=2.0e6, desc='frequency step [Hz]', label='Delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    t_mw2_pi = Range(low=1., high=100000., value=90., desc='length of pi pulse of mw2 [ns]', label='mw2 pi [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=10000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    tau = Range(low=1., high=100000., value=300., desc='tau [ns]', label='tau [ns]', mode='text', auto_set=False, enter_set=True)
    seconds_per_point = Range(low=20e-3, high=1, value=0.2, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
 
    sweeps_per_point = Int()
    run_time = Float(value=0.0)
        
    frequencies = Array(value=np.array((0., 1.)))   
    
      
    def generate_sequence(self):
        if self.t_mw1_pi > self.t_mw2_pi:
            return 100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw2_pi), (['mw_a'], (self.t_mw1_pi - self.t_mw2_pi)), ([], self.tau), (['mw_a'], self.t_mw1_pi2) , (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw2_pi), (['mw_a'], (self.t_mw1_pi - self.t_mw2_pi)), ([], self.tau), (['mw_a'], self.t_mw1_3pi2) , (['sequence'], 10)]
        else:
            return 100 * [ (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw1_pi), (['mw_b'], (self.t_mw2_pi - self.t_mw1_pi)), ([], (self.tau - (self.t_mw2_pi - self.t_mw1_pi))), (['mw_a'], self.t_mw1_pi2) , (['laser', 'aom'], self.laser), ([], self.wait), (['mw_a'], self.t_mw1_pi2), ([], self.tau), (['mw_a', 'mw_b'], self.t_mw1_pi), (['mw_b'], (self.t_mw2_pi - self.t_mw1_pi)), ([], (self.tau - (self.t_mw2_pi - self.t_mw1_pi))), (['mw_a'], self.t_mw1_3pi2) , (['sequence'], 10)]
        
    
    def apply_parameters(self):
        """Apply the current parameters and decide whether to keep previous data."""

        frequencies = np.arange(self.rf_begin, self.rf_end + self.rf_delta, self.rf_delta)
        n_bins = int(self.record_length / self.bin_width)
        time_bins = self.bin_width * np.arange(n_bins)
        sequence = self.generate_sequence()

        if not (self.keep_data and sequence == self.sequence and np.all(time_bins == self.time_bins) and np.all(frequencies == self.frequencies)): # if the sequence and time_bins are the same as previous, keep existing data
            self.count_data = np.zeros((2 * len(frequencies), n_bins))
            self.run_time = 0.0
        
        self.frequencies = frequencies
        self.sequence = sequence 
        self.time_bins = time_bins
        self.n_bins = n_bins
        self.sweeps_per_point = int(np.max((1, int(self.seconds_per_point * 1e9 / (self.laser + self.wait + 2 * (self.t_mw1_pi2 + self.tau) + self.t_mw1_pi)))))
        self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.
    

    def _run(self):
        """Acquire data."""
        
        try: # try to run the acquisition from start_up to shut_down
            self.state = 'run'
            self.apply_parameters()
            PulseGenerator().Night()
            Microwave().setOutput(self.mw1_power, self.mw1_frequency)
            MicrowaveB().setPower(self.mw2_power)
            tagger = TimeTagger.Pulsed(self.n_bins, int(np.round(self.bin_width * 1000)), 2, 0, 2, 3)
            tagger.setMaxCounts(self.sweeps_per_point)
            PulseGenerator().Sequence(self.sequence)

            while True:

                if self.thread.stop_request.isSet():
                    break

                t_start = time.time()
                
                for i, fi in enumerate(self.frequencies):
                    
                    MicrowaveB().setOutput(self.mw2_power, fi)                    
                    tagger.clear()
                    while not tagger.ready():
                        time.sleep(1.1 * self.seconds_per_point)
                    count = tagger.getData()
                    self.count_data[i, :] += count[0]
                    self.count_data[i + len(self.frequencies), :] += count[1]
                                                            
                self.trait_property_changed('count_data', self.count_data)
                self.run_time += time.time() - t_start
                
            del tagger
            PulseGenerator().Light()
            Microwave().setOutput(None, self.mw1_frequency)
            MicrowaveB().setOutput(None, self.rf_begin)
        finally: # if anything fails, recover
            self.state = 'idle'        
            PulseGenerator().Light()
        
    get_set_items = Pulsed.get_set_items + ['mw1_power', 'mw1_frequency',
                                                    'mw2_power', 'rf_begin', 'rf_end', 'rf_delta', 't_mw2_pi', 't_mw1_pi2', 't_mw1_pi',
                                                       'laser', 'wait', 'seconds_per_point', 'frequencies', 'count_data', 'sequence']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority', width= -40),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw1_power', width= -40, enabled_when='state != "run"'),
                                                   Item('mw1_frequency', width= -120, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi2', width= -40, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi', width= -40, enabled_when='state != "run"'),
                                                   Item('t_mw1_3pi2', width= -40, enabled_when='state != "run"'),
                                                   Item('tau', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('mw2_power', width= -40, enabled_when='state != "run"'),
                                                   Item('rf_begin', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('rf_end', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('rf_delta', width= -80, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_func=lambda x:'%e' % x)),
                                                   Item('t_mw2_pi', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait', width= -80, enabled_when='state == "idle"'),
                                                   Item('record_length', width= -80, enabled_when='state == "idle"'),
                                                   Item('bin_width', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('seconds_per_point', width= -120, enabled_when='state == "idle"'),
                                                   Item('sweeps_per_point', width= -120, style='readonly'),
                                                   ),
                                            label='settings'
                                            ),
                                     ),
                              ),
                        title='DEER 3pi/2, use frequencies 3pi2 fitting',
                        )


class Ce_DEER(Pulsed):
        
    mw1_power = Range(low= -100., high=25., value=4.0, desc='MW1 Power [dBm]', label='MW1 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    mw1_frequency = Range(low=1., high=20.e9, value=1.316995e9, desc='MW1 frequency [Hz]', label='MW1 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi2 = Range(low=1., high=100000., value=21.0, desc='length of pi/2 pulse of mw1 [ns]', label='mw1 pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw1_pi = Range(low=1., high=100000., value=45.0, desc='length of pi pulse of mw1 [ns]', label='mw1 pi [ns]', mode='text', auto_set=False, enter_set=True)
    mw0_frequency = Range(low=1., high=20.e9, value=1.34855e9, desc='MW0 frequency [Hz]', label='MW0 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    mw0_power = Range(low= -100., high=25., value=10.0, desc='MW0 Power [dBm]', label='MW0 Power [dBm]', mode='text', auto_set=False, enter_set=True)
    t_mw2_pi2 = Range(low=1., high=100000., value=21., desc='length of pi/2 pulse of mw1 [ns]', label='mw1 pi/2 [ns]', mode='text', auto_set=False, enter_set=True)
    t_mw2_pi = Range(low=1., high=100000., value=45., desc='length of pi pulse of mw1 [ns]', label='mw1 pi [ns]', mode='text', auto_set=False, enter_set=True)
    n_pi = Range(low= 1., high=1000000, value=2, desc='Num pi', label='Num pi', mode='text', auto_set=False, enter_set=True)
    tau_begin = Range(low=1., high=1e8, value=12.0, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=1e8, value=1500, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=15, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=10000., value=4000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
    seconds_per_point = Range(low=20e-3, high=1, value=0.2, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
 
    sweeps_per_point = Int()
    run_time = Float(value=0.0)
        
    tau = Array(value=np.array((0., 1.)))  
    
      
    def generate_sequence(self):
        tau = self.tau
        laser = self.laser
        wait = self.wait
        
        sequence = []
        for t in tau:
            sequence=sequence+[(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi2),([], t/(self.n_pi*2.0))]
            #sequence.append(((['mw_x', 'mw', 'mw_c'], self.t_mw2_pi2),([], t/(self.n_pi*2.0))))
            sequence=sequence+int(self.n_pi-1)*[(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi),([], t/(self.n_pi))]
            #sequence.append(int(self.n_pi-1)*((['mw_x', 'mw', 'mw_c'], self.t_mw2_pi),([], t/(self.n_pi))))
            sequence=sequence+[(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi),([], t/(self.n_pi*2.0))]
            #sequence.append(((['mw_x', 'mw', 'mw_c'], self.t_mw2_pi),([], t/(self.n_pi*2.0))))
            sequence=sequence+[(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi2)]
            #sequence.append((['mw_x', 'mw', 'mw_c'], self.t_mw2_pi2))
            sequence=sequence+[(['laser', 'aom'], laser)]
            sequence=sequence+[([], wait)]
            #sequence.append((['laser', 'aom'], laser))
            #sequence.append(([], wait))
        #if self.t_mw1_pi > self.t_mw2_pi:
        #    for t in tau:
        #        sequence.append((['mw_x', 'mw', 'mw_b'], self.t_mw2_pi2),(['mw_x', 'mw', 'mw_c'], self.t_mw1_pi2-self.t_mw2_pi2),([], t/(self.n_pi*2.0)))
        #        sequence.append(round(self.n_pi-1)*((['mw_x', 'mw', 'mw_b'], self.t_mw2_pi),(['mw_x', 'mw', 'mw_c'], self.t_mw1_pi-self.t_mw2_pi),([], t/(self.n_pi))))
        #        sequence.append((['mw_x', 'mw', 'mw_b'], self.t_mw2_pi),(['mw_x', 'mw', 'mw_c'], self.t_mw1_pi-self.t_mw2_pi),([], t/(self.n_pi*2.0)))
        #        sequence.append((['mw_x', 'mw', 'mw_b'], self.t_mw2_pi2),(['mw_x', 'mw', 'mw_c'], self.t_mw1_pi2-self.t_mw2_pi2))
        #        sequence.append((['laser', 'aom'], laser))
        #        sequence.append(([         ], wait))
        #else:
        #        sequence.append((['mw_x', 'mw', 'mw_b'], self.t_mw1_pi2),(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi2-self.t_mw1_pi2),([], t/(self.n_pi*2.0)))
        #        sequence.append(round(self.n_pi-1)*((['mw_x', 'mw', 'mw_b'], self.t_mw1_pi),(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi-self.t_mw1_pi),([], t/(self.n_pi))))
        #        sequence.append((['mw_x', 'mw', 'mw_b'], self.t_mw1_pi),(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi-self.t_mw1_pi),([], t/(self.n_pi*2.0)))
        #        sequence.append((['mw_x', 'mw', 'mw_b'], self.t_mw1_pi2),(['mw_x', 'mw', 'mw_c'], self.t_mw2_pi2-self.t_mw1_pi2))
        #        sequence.append((['laser', 'aom'], laser))
        #        sequence.append(([         ], wait))
        sequence.append((['sequence'], 120))
        return sequence
    
 
    def start_up(self):
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        PulseGenerator().Night()
        Microwave().setOutput(self.mw1_power, self.mw1_frequency)
        MicrowaveD().setOutput(self.mw0_power, self.mw0_frequency)

    def shut_down(self):
        PulseGenerator().Light()
        Microwave().setOutput(None, self.mw1_frequency)
        MicrowaveD().setOutput(None, self.mw0_frequency)


    get_set_items = Pulsed.get_set_items + ['mw1_power', 'mw1_frequency','mw0_frequency',
                                                    'mw0_power', 'tau_begin', 'tau_end', 'tau_delta', 't_mw2_pi', 't_mw1_pi2', 't_mw1_pi',
                                                       'laser', 'wait', 'seconds_per_point','tau', 'count_data', 'sequence']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority', width= -40),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw1_power', width= -40, enabled_when='state != "run"'),
                                                   Item('mw1_frequency', width= -120, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi2', width= -40, enabled_when='state != "run"'),
                                                   Item('t_mw1_pi', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_end', width= -80, enabled_when='state != "run"'),
                                                   Item('tau_delta', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            HGroup(Item('mw0_frequency', width= -120, enabled_when='state != "run"'),
                                                   Item('mw0_power', width= -40, enabled_when='state != "run"'),
                                                   Item('n_pi', width= -40, enabled_when='state != "run"'),
                                                   Item('t_mw2_pi', width= -40, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait', width= -80, enabled_when='state == "idle"'),
                                                   Item('record_length', width= -80, enabled_when='state == "idle"'),
                                                   Item('bin_width', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('seconds_per_point', width= -120, enabled_when='state == "idle"'),
                                                   Item('sweeps_per_point', width= -120, style='readonly'),
                                                   ),
                                            label='settings'
                                            ),
                                     ),
                              ),
                        title='Ce DEER, use Rabi fitting',
                        )

              
                        
if __name__ == '__main__':
    
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().info('Starting logger.')
    
    from tools.emod import JobManager
    
    JobManager().start()
    
    r1 = Rabi()
    r2 = Rabi()
    
    r1.edit_traits()
    r2.edit_traits()
    

