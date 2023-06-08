
from tools.utility import edit_singleton
from datetime import date
import os

# start confocal including auto_focus tool and Toolbox
if __name__ == '__main__':

    import hardware.api as ha
    
    # start confocal including auto_focus tool
    from measurements.confocal import Confocal
    scanner= ha.Scanner()
    confocal = Confocal(scanner)
    confocal.edit_traits()
    
    from measurements.auto_focus import AutoFocus
    auto_focus = AutoFocus(confocal)
    auto_focus.edit_traits()

    try:
        auto_focus.load('defaults/auto_focus.pyd')
    except:
        pass
    
    # some imports providing short names for the main modules
    import numpy as np
    import measurements as me
    import analysis as an
    
    
    from measurements.photon_time_trace1 import PhotonTimeTrace
    time_trace = PhotonTimeTrace()
    time_trace.edit_traits()
        
    
    # from measurements.odmr import ODMR
    # odmr=ODMR()
    # odmr.edit_traits()
    
    # from measurements.WideFieldPannel import WideFieldPannel
    # wfp=WideFieldPannel()
    # wfp.edit_traits()
    
    #from measurements.odmr import ODMRP
    #odmrp=ODMRP()
    # odmrp.edit_traits()
    #odmrp2=ODMRP()
    # odmrp2.edit_traits()
    #from measurements.odmr_nonuniform import ODMRN
    #odmrn=ODMRN()
    # odmrn.edit_traits()
    from measurements.odmrr import ODMRR #edit by jerry (53-55)
    odmrr=ODMRR()
    odmrr.edit_traits()
    from measurements.rabi import Rabi
    rabi=Rabi()
    from analysis.pulsed import PulsedAnalyzer
    p=PulsedAnalyzer()
    # p=PulsedAnalyzer()
    p.edit_traits()
#     
    #from measurements.nmr import NMR
#    
    #nmr=NMR()
    #m_nmr=PulsedAnalyzer()
    #m_nmr.measurement=nmr
    # m_nmr.edit_traits()
     
    #m_deer=PulsedAnalyzer()
    # m_deer.edit_traits()
    
    #from measurements.autocorrelation import Autocorrelation
    #ac=Autocorrelation()
    #ac.edit_traits()
    #####
    '''
    odmr2=ODMR()
    odmr2.edit_traits()
    
    odmrp2=ODMRP()
    odmrp2.edit_traits()
    
    odmrp3=ODMRP()
    odmrp3.edit_traits()
    
    odmrp4=ODMRP()
    odmrp4.edit_traits()
    
    from measurements.AutoControlTRv4 import AutoPanel
    autopanel=AutoPanel(auto_focus,confocal,odmr,odmrp,odmr2,odmrp2,odmrp3,odmrp4)
    autopanel.edit_traits()
    
    autopanel2=AutoPanel(auto_focus,confocal,odmr,odmrp,odmr2,odmrp2,odmrp3,odmrp4)
    autopanel2.edit_traits()
    '''
    #from measurements.AutoControlODMR import AutoPanelODMR
    #autopaneodmr=AutoPanelODMR(auto_focus,confocal,odmr,odmrp)
    #autopaneodmr=AutoPanelODMR(auto_focus,confocal,odmr,odmrp,odmrp2,odmrn)
    #autopaneodmr.edit_traits()
    #from measurements.AutoControlODMR2 import AutoPanelODMR2
    #autopaneodmr2=AutoPanelODMR2(auto_focus,confocal,odmr,odmrp)
    #autopaneodmr=AutoPanelODMR(auto_focus,confocal,odmr,odmrp,odmrp2)
    #autopaneodmr2.edit_traits()
    
    #from measurements.AutoControlODMR_wf import AutoControlODMR_wf
    #autopaneodmr=AutoPanelODMR(auto_focus,confocal,odmr,odmrp)
    #autopaneodmr_wf=AutoControlODMR_wf(auto_focus,confocal,odmr,odmrp,odmrp2,odmrn)
    # autopaneodmr_wf.edit_traits()
    
    #from measurements.AutoControlODMRR import AutoPanelODMRR     #edit by jerry (111-113)
    #autopaneodmrr=AutoPanelODMRR(auto_focus,confocal,odmr,odmrp,odmrp2,odmrn,odmrr)
    #autopaneodmrr.edit_traits()
    
    # from measurements.odmr_ccd import CCDODMR     #edit by jerry (111-113)
    # ccdodmr = CCDODMR()
    # ccdodmr.edit_traits()
    
    
    # from measurements.odmr_ccd_test import CCDODMR_test     #edit by jerry (111-113)
    # ccdodmra = CCDODMR_test()
    # ccdodmra.edit_traits()

    # from measurements.odmr_ccd_test_v2 import CCDODMR_test2     #edit by jerry (111-113)
    # ccdodmra2 = CCDODMR_test2()
    # ccdodmra2.edit_traits()
    #from measurements.odmr_ccd_test_v3 import CCDODMR_test3     #edit by jerry (111-113)
    #ccdodmra3 = CCDODMR_test3()
    #ccdodmra3.edit_traits()
    ha.PulseGenerator().Light()
	
    t = date.today()
    t = t.timetuple()
    if t.tm_mday < 10:
        d = '0' + str(t.tm_mday)
    else:
        d = str(t.tm_mday)
    
    if t.tm_mon < 10:
        m = '0' + str(t.tm_mon)
    else:
        m = str(t.tm_mon)
    y = str(t.tm_year)
    dirpath='E:/Data/' + y + '/' + y + '-' + m + '-' + d
    if not os.path.exists(dirpath):
        os.mkdir(dirpath)
        
