
from tools.utility import singleton

@singleton
def Scanner():
    from nidaq import Scanner
    return Scanner( CounterIn='/Dev1/Ctr1',
                    CounterOut='/Dev1/Ctr0',
                    TickSource='/Dev1/PFI3',
                    AOChannels='/Dev1/ao0:2',
                    x_range=(0.0,200.0),#100x
                    y_range=(0.0,200.0),
                    z_range=(0,100.0),
                    v_range=(-1.00,1.00)) 


ScnnerA=Scanner

def DigitalOut():
    import do
    return do.DigitalOut('/Dev1/port0/line8' )

@singleton
def Counter():
    from nidaq import PulseTrainCounter
    return PulseTrainCounter( CounterIn='/Dev1/Ctr3',
                              CounterOut='/Dev1/Ctr2',
                              TickSource='/Dev1/PFI3' )
    
CounterA=Counter


def CountTask(bin_width, length):
    return  TimeTagger.Counter(0,int(bin_width*1e12), length)
	
	
@singleton
def Microwave():
    import microwave_sources
    return microwave_sources.SMIQ(visa_address='GPIB0::25')

MicrowaveA = Microwave

@singleton
def RFSource():
    import rf_source
    
    return rf_source.SMIQ_RF(visa_address='GPIB0::29')
 
@singleton
def PulseGenerator():
    # return PulseGeneratorClass(serial='1634000FWV',channel_map={'green':0,'aom':0, 'mw_x':1, 'mw':1,'rf':2,'laser':3,'sequence':4, 'mw_2':5, 'test':6, 'blue':7, 'flip':8})
    #return PulseGeneratorClass(serial='1729000I9M',channel_map={'green':0,'aom':0, 'mw_x':1, 'mw':1,'rf':2,'laser':3,'sequence':4, 'blue':7})
    return PulseGeneratorClass(serial='2021000TCD',channel_map={'green':0,'aom':0, 'mw_x':1, 'mw':1,'rf':2,'laser':3,'sequence':4, 'mw_2':5, 'test':6, 'blue':7, 'flip':8})

import hardware.TimeTagger as tt
#tagger=tt.TimeTagger('1634000FWQ')
#tagger=tt.TimeTagger('2138000XIC')
tagger=tt.TimeTagger('1634000FWP')
import time_tagger_control
TimeTagger=time_tagger_control.TimeTaggerControl(tagger)
