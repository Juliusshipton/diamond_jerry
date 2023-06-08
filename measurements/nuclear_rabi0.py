import numpy as np

from traits.api import Range, Array, Enum
from traitsui.api import View, Item, Tabbed, HGroup, VGroup, VSplit, EnumEditor, TextEditor

import logging
import time
import hardware.api as ha

from pulsed import Pulsed

class NuclearRabi0(Pulsed):

    """Defines a Nuclear Rabi 0 measurement."""

    mw1_frequency   = Range(low=1,      high=20e9,  value=2.882551e9, desc='microwave1 frequency', label='MW1 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    mw1_power       = Range(low=-100.,  high=25.,   value=-25,      desc='microwave1 power',     label='MW1 power [dBm]',    mode='text', auto_set=False, enter_set=True)
    t_pi1           = Range(low=1.,     high=100000., value=1380., desc='length of pi1 pulse [ns]', label='pi1 [ns]', mode='text', auto_set=False, enter_set=True)
    
    mw2_frequency   = Range(low=1,      high=20e9,  value=2.882551e9, desc='microwave2 frequency', label='MW2 frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    mw2_power       = Range(low=-100.,  high=25.,   value=-25,      desc='microwave2 power',     label='MW2 power [dBm]',    mode='text', auto_set=False, enter_set=True)
    t_pi2           = Range(low=1.,     high=100000., value=1380., desc='length of pi2 pulse [ns]', label='pi2 [ns]', mode='text', auto_set=False, enter_set=True)

    
    switch = Enum('rf_1', 'rf_2', desc='switch to use for different RF source', label='switch')
    rf_frequency   = Range(low=1,      high=20e6,  value=4.9463e6, desc='RF frequency', label='RF frequency [Hz]', mode='text', auto_set=False, enter_set=True)
    rf_power       = Range(low=-130.,  high=25.,   value=-6.0,      desc='RF power',     label='RF power [dBm]',    mode='text', auto_set=False, enter_set=True)

    tau_begin = Range(low=0., high=1e8, value=1200, desc='tau begin [ns]', label='tau begin [ns]', mode='text', auto_set=False, enter_set=True)
    tau_end = Range(low=1., high=10e6, value=8.0e5, desc='tau end [ns]', label='tau end [ns]', mode='text', auto_set=False, enter_set=True)
    tau_delta = Range(low=1., high=1e6, value=14000.0, desc='delta tau [ns]', label='delta tau [ns]', mode='text', auto_set=False, enter_set=True)
    laser = Range(low=1., high=1.0e7, value=6000.0, desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait        = Range(low=1., high=1.0e8,   value=4.5e5,    desc='wait [ns]',       label='wait [ns]',        mode='text', auto_set=False, enter_set=True)
    wait2       = Range(low=1., high=1.0e8,   value=1500,    desc='wait_rf_mw [ns]',       label='wait rf_mw [ns]',        mode='text', auto_set=False, enter_set=True)

    tau = Array(value=np.array((0., 1.)))

    get_set_items = Pulsed.get_set_items + ['mw1_frequency', 'mw1_power', 't_pi1', 'rf_frequency', 'rf_power', 'tau_begin', 'tau_end', 'tau_delta', 'laser', 'wait', 'wait2','tau']

    traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('mw1_frequency', width= -80, enabled_when='state == "idle"'),
                                                   Item('mw1_power', width= -80, enabled_when='state == "idle"'),
                                                   Item('t_pi1', width= -80, enabled_when='state == "idle"'),
                                                   ),
                                            HGroup(Item('mw2_frequency', width= -80, enabled_when='state == "idle"'),
                                                   Item('mw2_power', width= -80, enabled_when='state == "idle"'),
                                                   Item('t_pi2', width= -80, enabled_when='state == "idle"'),
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
                       title='Nuclear Rabi0 Measurement',
                  )

    def generate_sequence(self):
        t_pi1 = self.t_pi1
        t_pi2 = self.t_pi2
        laser = self.laser
        tau = self.tau
        wait = self.wait
        sequence = []
        for t in tau:
            sequence.append((['mw','mw_x'], t_pi1))
            if self.switch == 'rf_1':
                sequence.append((['rf'], t))
            else:
                sequence.append((['rf2'], t))
            sequence.append(([], self.wait2))
            sequence.append((['mw_c'], t_pi2))
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
        ha.Microwave().setOutput(self.mw1_power, self.mw1_frequency)
        ha.MicrowaveD().setOutput(self.mw2_power, self.mw2_frequency)
        if self.switch == 'rf_1':
            ha.RFSource().setOutput(self.rf_power, self.rf_frequency)
            ha.RFSource().setMode()
        else:
            ha.RFSource2().setOutput(self.rf_power, self.rf_frequency)
            ha.RFSource2().setMode()
        time.sleep(0.2) 

    def shut_down(self):
        ha.PulseGenerator().Light()
        #ha.Microwave().setOutput(None, self.mw_frequency)
        """if self.switch == 'rf_1':
            ha.RFSource().setOutput(None, self.rf_frequency)
        else:
            ha.RFSource2().setOutput(None, self.rf_frequency) 
        """
    
