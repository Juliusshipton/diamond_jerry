import numpy as np

from traits.api import SingletonHasTraits, Trait, Instance, Property, String, Range, Float, Int, Bool, Array, Enum, Button, on_trait_change, cached_property, Code, List, NO_COMPARE
from traitsui.api import View, Item, HGroup, VGroup, VSplit, Tabbed, EnumEditor, TextEditor, Group
from enable.api import Component, ComponentEditor
from chaco.api import ArrayPlotData, Plot, Spectral, PlotLabel

from traitsui.file_dialog import save_file
from traitsui.menu import Action, Menu, MenuBar

import time
import threading
import logging
from kim_mw import QDM
from tools.emod import ManagedJob

import hardware.api as ha

from analysis import fitting

from tools.utility import GetSetItemsHandler, GetSetItemsMixin

class WideFieldPannel(ManagedJob, GetSetItemsMixin):
    

	# profile
    check = Bool(True, label='Apply the input number')
    mwPower = Range(low= -100., high=2., value= -20, desc='Microwave power of ODMR', label='Microwave Power [dBm]', mode='text', auto_set=False, enter_set=True)
    mwFrequency = Range(low=1, high=20e9, value=2.87e9, desc='Microwave frequency Of ODMR', label='Microwave Frequency [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    Kimmw_power = Range(low= -40., high=2., value= -20, desc='Microwave power of KIM', label='KIM Microwave Power [dBm]', mode='text', auto_set=False, enter_set=True)
    Kimmw_Frequency = Range(low=3.4375e7, high=4.400e9, value=2.87e9, desc='Microwave frequency Of KIM', label='KIM Microwave Frequency [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
    def __init__(self):
        super(WideFieldPannel, self).__init__()
       
		
    def _run(self):
        try:
            if self.check:
                ha.Microwave().setOutput(self.mwPower, self.mwFrequency)
                
            #ha.Microwave().setOutput(self.mwPower, self.mwFrequency)
                print(self.Kimmw_Frequency)
                q=QDM()
                q.setPower(self.Kimmw_power)
                q.setFrequency(self.Kimmw_Frequency/1e6)
                ha.PulseGenerator().Continuous(['green','mw_x'])
                print("Hello world")
            else:
                #ha.Microwave().resetListPos()
                ha.Microwave().setOutput(None, self.mwFrequency)
                ha.PulseGenerator().Light()
                print("Bye world")
               
        except:
            logging.getLogger().exception('Error in the Panel.')

    def submit(self):
        ManagedJob.submit(self)
    
    


    traits_view = View(VGroup(HGroup(VGroup(HGroup(Item('submit_button', show_label=False),
                                                   Item('check')
                                                   ),
                                                   
                                            HGroup(Item('mwPower', width = -50),
                                                   Item('mwFrequency', width = -100)
                                                   ),
                                            HGroup(Item('Kimmw_power', width = -50),
                                                   Item('Kimmw_Frequency', width = -100),
                                                   ),
                                            ),
                                    ),
                                ),
                        title='Wide Field Pannel', width=1000, height=250, buttons=[], resizable=True
                        )
    get_set_items = ['check','mwPower','mwFrequency','Kimmw_power','Kimmw_Frequency','__doc__']
    
if __name__ == '__main__':

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().info('Starting logger.')

    from tools.emod import JobManager
    JobManager().start()
    
    
