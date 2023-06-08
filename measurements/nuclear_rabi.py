import numpy as np

from traits.api import Range, Array, Enum
from traitsui.api import View, Item, Tabbed, HGroup, VGroup, VSplit, EnumEditor, TextEditor

import logging
import time
import hardware.api as ha

from pulsed import Pulsed

class NuclearRabi(Pulsed):

    """Defines a Nuclear Rabi measurement."""

    mw_frequency   = Range(low=1,      high=20e9,  value=2.879837e9, desc='microwave frequency', label='MW frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    mw_power       = Range(low=-100.,  high=25.,   value=-16,      desc='microwave power',     label='MW power [dBm]',    mode='text', auto_set=False, enter_set=True)
    t_pi           = Range(low=1.,     high=1.0e9, value=1137., desc='length of pi pulse [ns]', label='pi [ns]', mode='text', auto_set=False, enter_set=True)

    switch = Enum('rf_2', 'rf_1','mw_b', desc='switch to use for different RF source', label='switch')
    rf_frequency   = Range(low=1,      high=200e6,  value=2.761e6, desc='RF frequency', label='RF frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    rf_power       = Range(low=-130.,  high=25.,   value=-5.0,      desc='RF power',     label='RF power [dBm]',    mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=0., high=1e8, value=1200, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=10e6, value=8.0e5, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=14000.0, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=1.0e7, value=6000.0, desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait        = Range(low=1., high=1.0e8,   value=9.0e5,    desc='wait [ns]',       label='wait [ns]',        mode='text', auto_set=False, enter_set=True)
    wait2       = Range(low=1., high=1.0e8,   value=1500,    desc='wait_rf_mw [ns]',       label='wait rf_mw [ns]',        mode='text', auto_set=False, enter_set=True)

    tau = Array(value=np.array((0., 1.)))

    get_set_items = Pulsed.get_set_items + ['mw_frequency', 'mw_power', 't_pi', 'rf_frequency', 'rf_power', 'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'wait2','tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw_frequency', width= -80, enabled_when='state == "idle"'),
                                                   Item('mw_power', width= -80, enabled_when='state == "idle"'),
                                                   Item('t_pi', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('switch', style='custom'),
                                                   Item('rf_frequency', width= -80, enabled_when='state == "idle"'),
                                                   Item('rf_power', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state == "idle"'),
                                                   Item('tau_end', width= -80, enabled_when='state == "idle"'),
                                                   Item('tau_delta', width= -80, enabled_when='state == "idle"'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait2',          width=-80, enabled_when='state == "idle"'),
                                                   Item('record_length', width= -80, enabled_when='state == "idle"'),
                                                   Item('bin_width', width= -80, enabled_when='state == "idle"'),),
                                                   label='settings'),
                              ),
                        ),
                       title='Nuclear Rabi Measurement',
                  )

    def generate_sequence(self):
        t_pi = self.t_pi
        laser = self.laser
        tau = self.tau
        wait = self.wait
        sequence = []
        for t in tau:
            #sequence.append((['mw','mw_x'], t_pi))
            sequence.append((['mw_x'], t_pi))
            if self.switch == 'rf_1':
                sequence.append((['rf'], t))
            elif self.switch == 'rf_2':
                sequence.append((['rf2'], t))
            elif self.switch == 'mw_b':
                sequence.append((['mw_b'], t))
                
            sequence.append(([], self.wait2))
            #sequence.append((['mw','mw_x'], t_pi))
            sequence.append((['mw_x'], t_pi))
            sequence.append((['laser', 'aom'], laser))
            sequence.append(([], wait))
        sequence.append((['sequence'], 100))
        return sequence

    def apply_parameters(self):
        """Overwrites apply_parameters() from pulsed. Prior to generating sequence, etc., generate the tau mesh."""
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        Pulsed.apply_parameters(self)
        
    def start_up(self):
        ha.PulseGenerator().Night()
        ha.Microwave().setOutput(self.mw_power, self.mw_frequency)
        if self.switch == 'rf_2':
            ha.RFSource2().setOutput(self.rf_power, self.rf_frequency)
            #ha.RFSource2().setMode()
        elif self.switch == 'rf_1':
            ha.RFSource().setOutput(self.rf_power, self.rf_frequency)
        elif self.switch == 'mw_b':
            ha.MicrowaveE().setOutput(self.rf_power, self.rf_frequency)
            #ha.RFSource().setMode()
        time.sleep(0.2) 

    def shut_down(self):
        ha.PulseGenerator().Light()
        #ha.Microwave().setOutput(None, self.mw_frequency)
        """if self.switch == 'rf_1':
            ha.RFSource().setOutput(None, self.rf_frequency)
        else:
            ha.RFSource2().setOutput(None, self.rf_frequency) 
        """
    

class NuclearRabi0(Pulsed):

    """Defines a Nuclear Rabi measurement."""

    mw_frequency   = Range(low=1,      high=20e9,  value=2.879833e9, desc='microwave frequency', label='MW frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    mw_power       = Range(low=-100.,  high=25.,   value=-24,      desc='microwave power',     label='MW power [dBm]',    mode='text', auto_set=False, enter_set=True)
    t_pi           = Range(low=1.,     high=100000., value=1170., desc='length of pi pulse [ns]', label='pi [ns]', mode='text', auto_set=False, enter_set=True)
    rf_pi          = Range(low=1.,     high=500.e3, value=200.e3, desc='RF pi [ns]', label='RF pi [ns]', mode='text', auto_set=False, enter_set=True)

    switch = Enum('rf_2', 'rf_1','rf_y', desc='switch to use for different RF source', label='switch')
    rf_frequency   = Range(low=1,      high=20e6,  value=2.761e6, desc='RF frequency', label='RF frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    rf_power       = Range(low=-130.,  high=25.,   value=2.0,      desc='RF power',     label='RF power [dBm]',    mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=0., high=1e8, value=1200, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=10e6, value=8.0e5, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=14000.0, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=1.0e7, value=6000.0, desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait        = Range(low=1., high=1.0e8,   value=4.5e5,    desc='wait [ns]',       label='wait [ns]',        mode='text', auto_set=False, enter_set=True)
    wait2       = Range(low=1., high=1.0e8,   value=1500,    desc='wait_rf_mw [ns]',       label='wait rf_mw [ns]',        mode='text', auto_set=False, enter_set=True)

    tau = Array(value=np.array((0., 1.)))

    get_set_items = Pulsed.get_set_items + ['mw_frequency', 'mw_power', 't_pi', 'rf_frequency', 'rf_power', 'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'wait2','tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw_frequency', width= -80, enabled_when='state == "idle"'),
                                                   Item('mw_power', width= -80, enabled_when='state == "idle"'),
                                                   Item('t_pi', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(#Item('switch', style='custom'),
                                                   Item('rf_frequency', width= -80, enabled_when='state == "idle"'),
                                                   Item('rf_power', width= -40, enabled_when='state == "idle"'),
                                                   Item('rf_pi', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('tau_begin', width= -80, enabled_when='state == "idle"'),
                                                   Item('tau_end', width= -80, enabled_when='state == "idle"'),
                                                   Item('tau_delta', width= -80, enabled_when='state == "idle"'),),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait', width= -80, enabled_when='state == "idle"'),
                                                   Item('wait2',          width=-80, enabled_when='state == "idle"'),
                                                   Item('record_length', width= -80, enabled_when='state == "idle"'),
                                                   Item('bin_width', width= -80, enabled_when='state == "idle"'),),
                                                   label='settings'),
                              ),
                        ),
                       title='Nuclear Rabi 0y Measurement',
                  )

    def generate_sequence(self):
        t_pi = self.t_pi
        laser = self.laser
        tau = self.tau
        wait = self.wait
        sequence = []
        for t in tau:
            sequence += [(['mw_x'], self.t_pi), (['rf', 'rf_t'],self.rf_pi/2.), ([], 2000)]
            sequence += [(['rf_y'], t), ([],  2000), (['rf', 'rf_t'],self.rf_pi/2.) ,([], 2000), (['mw_c'], self.t_pi), ([], 60)]
            sequence += [(['laser', 'aom'], self.laser), ([], self.wait)]
        
        #for t in tau:
        #    sequence += [(['mw_x'], self.t_pi), (['rf'],self.rf_pi), ([], 2000)]
        #    sequence += [(['rf_y'], t), ([],  2000), (['mw_c'], 1100), ([], 60)]
        #    sequence += [(['laser', 'aom'], self.laser), ([], self.wait)]
         
        sequence.append((['sequence'], 100))
        return sequence

    def apply_parameters(self):
        """Overwrites apply_parameters() from pulsed. Prior to generating sequence, etc., generate the tau mesh."""
        self.tau = np.arange(self.tau_begin, self.tau_end, self.tau_delta)
        Pulsed.apply_parameters(self)
        
    def start_up(self):
        ha.PulseGenerator().Night()
        ha.Microwave().setOutput(self.mw_power, self.mw_frequency)
        #ha.RFSource().setOutput(self.rf_power, self.rf_frequency)
        time.sleep(0.2) 

    def shut_down(self):
        ha.PulseGenerator().Light()
        #ha.Microwave().setOutput(None, self.mw_frequency)
        """if self.switch == 'rf_1':
            ha.RFSource().setOutput(None, self.rf_frequency)
        else:
            ha.RFSource2().setOutput(None, self.rf_frequency) 
        """
  