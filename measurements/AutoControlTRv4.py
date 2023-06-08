
import threading, time, os, logging
from datetime import datetime
from tools.emod import FreeJob
from tools.utility import timestamp
#from tools import save_toolbox
import numpy as np
import pickle

from traits.api import List,Dict, HasTraits, Int, Str, Float,Array,Button,Bool,Enum
from traitsui.table_column  import ObjectColumn 
from traitsui.api import View, Item, TableEditor, Group, HGroup, VGroup, Tabbed, EnumEditor, TextEditor, Action, Menu, MenuBar

#save_toolbox.CreateFolder(folderpys) #all folders will be checked and created if necessary

"""
About LoopOption:
Without activate this option, everything is the normal autopanel. (Automatically change LoopNumber to 1 and SleepTime to 0 s.)
With the box checked, it will change to Loop mode.
Default is LoopNumber = 1 and SleepTime = 0 s, which is the normal one.
LoopNumber is the repeat times, after one measurement it will wait for the SleepTime. After that it goes to another loop. This continous until the current loop is equal to LoopNumber.
LoopNumber cannot be equal or smaller than 0.
"""

class Target(HasTraits):
    ID=Str
    N=Int
    Fodmr=Float
    T1=Float
    T2Star=Float
    piTau=Float
    MWpower=Float
    T2=Float
    Perform=Bool
    

class AutoPanel( FreeJob,HasTraits):
    
    UseReference=Bool(True,label='Refocus')
    ReferenceSpot=Str('ref',label='Reference spot')
    FreeRuns=Int(10,label='Free runs')
    n=0
    CurrentSpot=Str('None', label='Current spot')
    LoopOption=Bool(False,label='Loop')
    LoopNumber=Int(1, desc='Start from 1', label='Number of loops')
    SleepTime=Int(0, label='Sleep time [s]')
    
    VoltageLevel=List()
    PowerLevel=List()
    DoPowerSeries=Bool(False)
    
    
    SpotInfo =List(Target)
    ImportSpots=Button(label='Import New Spots')
    EmptyList=Button(label='empty spot list')
    
    #measurement control panel
      
    PerformODMR=Bool(True,label='perform ODMR')
    ODMRTime=Float(100.,label='ODMR integration time [s]')
    
    PerformODMRP=Bool(True,label='perform ODMRP')
    ODMRPTime=Float(100.,label='ODMRP integration time [s]')
    
    PerformODMR2=Bool(True,label='perform ODMR2')
    ODMR2Time=Float(100.,label='ODMR2 integration time [s]')
    
    PerformODMRP2=Bool(True,label='perform ODMRP2')
    ODMRP2Time=Float(100.,label='ODMRP2 integration time [s]')
    
    PerformODMRP3=Bool(True,label='perform ODMRP3')
    ODMRP3Time=Float(100.,label='ODMRP3 integration time [s]')
    
    PerformODMRP4=Bool(True,label='perform ODMRP4')
    ODMRP4Time=Float(100.,label='ODMRP4 integration time [s]')
    
    PerformAC=Bool(label='perform autocorrelation')
    ACTime=Float(label='ac integration time [s]')
    
    PerformT1=Bool(label='perform T1')
    T1Time=Float(label='T1 Decay integration time [s]')
    AddPi=Bool(label='use a pi pulse')
    
    PerformLifetime=Bool(label='perform Lifetime')
    DoAllLifetime=Bool(label='do all')
    LifetimeTime=Float(label='T1 Decay integration time [s]')
    
    PerformRabi=Bool(label='perform rabi')
    RabiTime=Float(label='rabi integration time [s]')
    
    PerformHahnEcho=Bool(label='perform Hahn echo')
    HahnEchoTime=Float(label='Hahn echo integration time [s]')
    
    
    PerformRamsey=Bool(label='perform Hahn echo')
    RamseyTime=Float(label='ramsey integration time [s]')
    # Analysis control pannel
    FitAC =Button(label='Fit AC data')  
    
   
    SaveString=Str(label='savename')
    LoadData=Button(label='Load Target Info')
    SaveData=Button(label='Save Target Info')
    ExportASCI=Button(label='export table as ascii')
    
    table_editor = TableEditor(columns = [ObjectColumn(name='ID',width=120),
                                          ObjectColumn(name='N',width=200),
                                          ObjectColumn(name='Fodmr',format='%3.2f',width=200),
                                          ObjectColumn(name='T1',format='%3.2f',width=50),
                                          ObjectColumn(name='T2Star',format='%3.2f',width=50),
                                          ObjectColumn(name='piTau',format='%3.2f',width=50),
                                          ObjectColumn(name='MWpower',format='%3.2f',width=50),
                                          ObjectColumn(name='T2',format='%3.2f',width=50),
                                          ObjectColumn(name='Perform',width=200)
                                          ])
    
    def _LoadData_fired(self):
        try:
            f=open(self.SaveString+'_SpotData.pys','rb')
            self.SpotInfo=pickle.load(f)
            f.close()
        except:
            print 'could not load data'
      
    def _SaveData_fired(self):
        
        f=open(self.SaveString+'_SpotData.pys','wb')
        pickle.dump(self.SpotInfo,f)
        f.close() 
        
    def _ExportASCI_fired(self):
        f=open(self.SaveString+'_SpotData.txt','w')
        #write header
        Header=list(['ID','N','Fodmr','T1','T2Star','piTau','MWpower','T2'])
        for items in Header:
            f.write(items)
            f.write('\t')
        f.write('\n')   
        for target in self.SpotInfo:
            Info=list([str(target.ID),str(target.N),str(target.Fodmr),str(target.T1),str(target.T2Star),str(target.piTau),str(target.MWpower),str(target.T2)])
            for items in Info:
                f.write(items)
                f.write('\t')
            f.write('\n') 
        
        f.close()
            
        
    def _FitAC_fired(self):
            for j,Target in  enumerate(self.SpotInfo):
                print j
                loadname= self.SaveString+'_'+Target.ID+'_AB'
                try:                    
                    self.autocorrelation.load(loadname+'.pys')
                    self.autocorrelation._counts_changed()
                    self.autocorrelation._FitData_fired()
                    #threading.currentThread().stop_request.wait(1.0)
                    self.SpotInfo[j].N=int(self.autocorrelation.FitResults[1])
                                                     
                except:
                    logging.getLogger().exception('File could not be loaded. (AC)')
                    
                    
                    
    def __init__(self,auto_focus, confocal,odmr,odmrp,odmr2,odmrp2,odmrp3,odmrp4,autocorrelation=None,pulsed_tool_taut1=None,pulsed_tool_tau=None,pulsed_tool_tauHE=None):
        super(AutoPanel, self).__init__()     
        self.auto_focus=auto_focus   
        self.confocal=confocal
        self.odmr = odmr
        self.odmrp = odmrp
        self.odmr2 = odmr2
        self.odmrp2 = odmrp2
        self.odmrp3 = odmrp3
        self.odmrp4 = odmrp4
        
        print "Welcome to Autopanel!"
        
        if autocorrelation is not None:
            self.autocorrelation = autocorrelation
        else:
            self.autocorrelation = None
            
        if pulsed_tool_taut1 is not None:
            self.tauT1 = pulsed_tool_taut1
        else:
            self.tauT1 = None
           
        if pulsed_tool_tau is not None:
            self.rabi = pulsed_tool_tau
        else:
            self.rabi = None
           
        if pulsed_tool_tauHE is not None:
            self.HahnEcho=pulsed_tool_tauHE
        else:
            self.HahnEcho=None
           
            
    def _ImportSpots_fired(self):
        MarkedTargets=self.auto_focus.target_list[1:]
        
        for TargetI in MarkedTargets:
            #print TargetI
            Flag=False
            for Spot in self.SpotInfo:
                if Spot.ID == TargetI:
                    Flag = True
            if Flag == False:
                NewTarget=Target()
                #print NewTarget
                #print '##33333'
                NewTarget.ID = TargetI
                NewTarget.Perform=True
                self.SpotInfo.append(NewTarget)
                
    def _EmptyList_fired(self):
        self.SpotInfo=[]
        
    def refocus(self,TargetID):
        try:
            if self.UseReference is False:
                self.auto_focus.current_target=TargetID
                self.auto_focus.submit()
            else:
                if (self.n % self.FreeRuns) == 0:
                    self.auto_focus.current_target=self.ReferenceSpot
                    self.auto_focus.submit()
                    while self.auto_focus.state != 'idle':
                        threading.currentThread().stop_request.wait(1.0)
                        
                self.auto_focus.current_target=None
                self.confocal.x, self.confocal.y, self.confocal.z = self.auto_focus.targets[TargetID] + self.auto_focus.current_drift
                time.sleep(1.0)
                self.auto_focus.submit()
   
           
            
            return 'True'
        
        except:
            print 'Refocus failed'
            return 'False'
            
    def _run(self):
        
        t = datetime.today()
        t = t.timetuple()
        y = t.tm_year
        m = str(t.tm_mon).zfill(2)
        d = str(t.tm_mday).zfill(2)
        
        timeRecord = ""
        
        path = 'E:/Data/' + str(y)
        
        if not os.path.exists(path):
            os.makedirs(path)
        
        path = path + '/'+ str(y)+ '-' + m + '-' + d
        
        if not os.path.exists(path):
            os.makedirs(path)
        
        number = 0        
        folder=path+'/'+str(number).zfill(3)
        
        while os.path.exists(folder):
            number +=1
            folder=path+'/'+ str(number).zfill(3)
        
        os.makedirs(folder)
        os.chdir(folder)
    
        endLabView = open("toLabView.txt","w+")
        endLabView.write("0")
        endLabView.close()
        
        try:
            self.state='run'
            self.n=0
            if self.LoopOption != True:
                self.LoopNumber = 1
                self.SleepTime = 0
            for ln in range(0,self.LoopNumber):
                for Target in  self.SpotInfo:
                    
                    self.n+=1
                    #print Target.ID
                    self.CurrentSpot=Target.ID
                    if self.PerformAC:
                        if Target.Perform:
                            self.refocus(Target.ID)
                            
                            self.autocorrelation.stop_time=self.ACTime
                            self.autocorrelation.submit()
                            while self.autocorrelation.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                            if self.DoPowerseries:
                                savename= self.SaveString+'_'+PSL+'_'+Target.ID+'_AB'
                            else:    
                                savename= self.SaveString+'_'+Target.ID+'_AB'
                            end
                            try:                    
                                self.autocorrelation.plot.save(savename+'.png')
                                self.autocorrelation.save(savename+'.pys')
                                                     
                            except:
                                logging.getLogger().exception('File could not be saved. (AC)')
                            
                    if (self.PerformODMR and self.odmr):
                        if Target.Perform and self.refocus(Target.ID):
                            self.odmr.stop_time=self.ODMRTime
                            self.odmr.submit()
                            while self.odmr.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                                
                            savename= self.SaveString+Target.ID+'_ODMR_Loop'+str(ln)
                            try:                    
                                self.odmr.save_all(savename)
                                                       
                            except:
                                logging.getLogger().exception('File could not be saved.(ODMR)')
                    
                    if (self.PerformODMRP and self.odmrp):
                        if Target.Perform and self.refocus(Target.ID):
                            self.odmrp.stop_time=self.ODMRPTime
                            self.odmrp.submit()
                            while self.odmrp.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                                
                            savename= self.SaveString+Target.ID+'_ODMRP_Loop'+str(ln)
                            try:                    
                                self.odmrp.save_all(savename)
                                                       
                            except:
                                logging.getLogger().exception('File could not be saved.(ODMRP)')
                    
                    if (self.PerformODMR2 and self.odmr2):
                        if Target.Perform and self.refocus(Target.ID):
                            self.odmr2.stop_time=self.ODMR2Time
                            self.odmr2.submit()
                            while self.odmr2.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                                
                            savename= self.SaveString+Target.ID+'_ODMR2_Loop'+str(ln)
                            try:                    
                                self.odmr2.save_all(savename)
                                                       
                            except:
                                logging.getLogger().exception('File could not be saved.(ODMR2)')
                    
                    if (self.PerformODMRP2 and self.odmrp2):
                        if Target.Perform and self.refocus(Target.ID):
                            self.odmrp2.stop_time=self.ODMRP2Time
                            self.odmrp2.submit()
                            while self.odmrp2.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                                
                            savename= self.SaveString+Target.ID+'_ODMRP2_Loop'+str(ln)
                            try:                    
                                self.odmrp2.save_all(savename)
                                                       
                            except:
                                logging.getLogger().exception('File could not be saved.(ODMRP2)')
                    
                    if (self.PerformODMRP3 and self.odmrp3):
                        if Target.Perform and self.refocus(Target.ID):
                            self.odmrp3.stop_time=self.ODMRP3Time
                            self.odmrp3.submit()
                            while self.odmrp3.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                                
                            savename= self.SaveString+Target.ID+'_ODMRP3_Loop'+str(ln)
                            try:                    
                                self.odmrp3.save_all(savename)
                                                       
                            except:
                                logging.getLogger().exception('File could not be saved.(ODMRP3)')
                    
                    if (self.PerformODMRP4 and self.odmrp4):
                        if Target.Perform and self.refocus(Target.ID):
                            self.odmrp4.stop_time=self.ODMRP4Time
                            self.odmrp4.submit()
                            while self.odmrp4.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                                
                            savename= self.SaveString+Target.ID+'_ODMRP4_Loop'+str(ln)
                            try:                    
                                self.odmrp4.save_all(savename)
                                                       
                            except:
                                logging.getLogger().exception('File could not be saved.(ODMRP4)')
                    
                    if self.PerformT1 and self.tauT1 is not None:
                        if Target.Perform:
                            self.refocus(Target.ID)
                            self.tauT1.measurement.stop_time=self.T1Time
                            if self.AddPi:
                                self.tauT1.pulse_me='rf after init'
                                addtag='withpi_'
                            else:
                               self.tauT1.pulse_me='no rf'
                               addtag='withoutpi_'
                               
                            self.tauT1.measurement.submit()
                            while self.tauT1.measurement.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                            if self.DoPowerseries:
                                savename= self.SaveString+'_'+PSL+'_'+Target.ID+'_tauT1_'+addtag
                            else:
                                savename= self.SaveString+'_'+Target.ID+'_tauT1_'+addtag
                                
                            try:                    
                                self.tauT1.figure_container.save(savename+'.png')
                                self.tauT1.measurement.save(savename+'.pys')
                                                     
                            except:
                                logging.getLogger().exception('File could not be saved. (T1)')
                                  
                    if self.PerformRabi and self.rabi is not None:
                        if Target.Perform:
                            self.refocus(Target.ID)
                            self.rabi.measurement.stop_time=self.RabiTime
                            self.rabi.measurement.frequency=Target.Fodmr
                            self.rabi.measurement.power=Target.MWpower
                            self.rabi.measurement.submit()
                            while self.rabi.measurement.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                            if self.DoPowerseries:
                                 savename= self.SaveString+'_'+PSL+'_'+Target.ID+'_rabi'
                            else:
                                 savename= self.SaveString+'_'+Target.ID+'_rabi'
                                
                            try:                    
                                self.rabi.line_plot.save(savename+'_LinePlot.png')
                                self.rabi.matrix_plot.save(savename+'_MatrixPlot.png')
                                self.rabi.measurement.save(savename+'.pys')
                                                     
                            except:
                                logging.getLogger().exception('File could not be saved. (rabi)')
                                
                    if self.PerformHahnEcho and self.HahnEcho is not None:
                        if Target.Perform:
                            self.refocus(Target.ID)
                            self.HahnEcho.measurement.stop_time=self.HahnEchoTime
                            self.HahnEcho.measurement.frequency=Target.Fodmr
                            self.HahnEcho.measurement.power=Target.MWpower
                            self.HahnEcho.measurement.t_pi=Target.piTau
                            self.HahnEcho.measurement.t_pi2=Target.piTau/2
                            self.HahnEcho.measurement.submit()
                            while self.HahnEcho.measurement.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                            if self.DoPowerseries:
                                savename= self.SaveString+'_'+PSL+'_'+Target.ID+'_HahnEcho'
                            else:
                                savename= self.SaveString+'_'+Target.ID+'_HahnEcho'
                            
                            try:                    
                                self.HahnEcho.line_plot.save(savename+'_LinePlot.png')
                                self.HahnEcho.matrix_plot.save(savename+'_MatrixPlot.png')
                                self.HahnEcho.measurement.save(savename+'.pys')
                                                     
                            except:
                                logging.getLogger().exception('File could not be saved. (hahnecho)')
                                
                    if self.PerformRamsey and self.HahnEcho is not None:
                        if Target.Perform:
                            self.refocus(Target.ID)
                            self.HahnEcho.measurement.stop_time=self.RamseyTime
                            self.HahnEcho.measurement.frequency=Target.Fodmr
                            self.HahnEcho.measurement.power=Target.MWpower
                            self.HahnEcho.measurement.t_pi=0
                            self.HahnEcho.measurement.t_pi2=Target.piTau/2
                            self.HahnEcho.measurement.submit()
                            while self.HahnEcho.measurement.state != 'done':
                                threading.currentThread().stop_request.wait(1.0)
                                if threading.currentThread().stop_request.isSet():
                                   break
                            if threading.currentThread().stop_request.isSet():
                                break
                            if self.DoPowerseries:
                                savename= self.SaveString+'_'+PSL+'_'+Target.ID+'_Ramsey'
                            else:
                                savename= self.SaveString+'_'+Target.ID+'_Ramsey'
                            
                            try:                    
                                self.HahnEcho.line_plot.save(savename+'_LinePlot.png')
                                self.HahnEcho.matrix_plot.save(savename+'_MatrixPlot.png')
                                self.HahnEcho.measurement.save(savename+'.pys')
                                                     
                            except:
                                logging.getLogger().exception('File could not be saved. (ramsey)') 
                startTime = "Start : %s" % time.ctime()
                print startTime
                startLabView = open("toLabView.txt","w+")
                startLabView.write("1")
                startLabView.close()
                if ln == (self.LoopNumber-1):
                    self.SleepTime = 1
                time.sleep(self.SleepTime)                    
                endTime = "End : %s" % time.ctime()
                print endTime
                endLabView = open("toLabView.txt","w+")
                endLabView.write("0")
                endLabView.close()
                timeRecord = timeRecord + startTime + "," + endTime + "\n"
            timeFile = open("timeRecord.txt","w+")
            timeFile.write(timeRecord)
            timeFile.close()
        
        except:
            logging.getLogger().exception('There was an Error.')
            self.state = 'error'
        finally:
            self.state='done'
            if self.UseReference:
                self.auto_focus.current_target=self.ReferenceSpot
                self.auto_focus.focus_interval=2
                self.auto_focus.periodic_focus=True

    traits_view = View(VGroup(HGroup(Item('start_button', show_label=False),
                                     Item('stop_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('CurrentSpot', style='readonly')
                                     ),
                              HGroup(Item('SaveString'),
                                     Item('SaveData'),
                                     Item('LoadData'),
                                     Item('ExportASCI')),
                              HGroup(VGroup(HGroup(Item('ImportSpots'),
                                                   Item('EmptyList')
                                                   ),

                                            Item('SpotInfo', editor=table_editor,show_label=False)
                                            ),
                                     Tabbed(VGroup(HGroup(Item('UseReference'),
                                                          Item('ReferenceSpot', enabled_when='UseReference == True'),
                                                          Item('FreeRuns', enabled_when='UseReference == True')
                                                          ),
                                                   HGroup(Item('LoopOption'),
                                                          Item('LoopNumber', enabled_when='LoopOption == True'),
                                                          Item('SleepTime', enabled_when='LoopOption == True')
                                                          ),
                                                   HGroup(Item('PerformODMR', enabled_when='odmr != None'),
                                                          Item('ODMRTime', enabled_when='odmr != None')
                                                          ),
                                                   HGroup(Item('PerformODMRP', enabled_when='odmrp != None'),
                                                          Item('ODMRPTime', enabled_when='odmrp != None')
                                                          ),
                                                   HGroup(Item('PerformODMR2', enabled_when='odmr2 != None'),
                                                          Item('ODMR2Time', enabled_when='odmr2 != None')
                                                          ),
                                                   HGroup(Item('PerformODMRP2', enabled_when='odmrp2 != None'),
                                                          Item('ODMRP2Time', enabled_when='odmrp2 != None')
                                                          ),
                                                   HGroup(Item('PerformODMRP3', enabled_when='odmrp3 != None'),
                                                          Item('ODMRP3Time', enabled_when='odmrp3 != None')
                                                          ),
                                                   HGroup(Item('PerformODMRP4', enabled_when='odmrp4 != None'),
                                                          Item('ODMRP4Time', enabled_when='odmrp4 != None')
                                                          ),
                                                   HGroup(Item('PerformAC'),
                                                          Item('ACTime')
                                                          ),
                                                   HGroup(Item('PerformT1', enabled_when='tauT1 != None'),
                                                          Item('T1Time', enabled_when='tauT1 != None'),
                                                          Item('AddPi', enabled_when='tauT1 != None')
                                                          ),
                                                   HGroup(Item('PerformRabi', enabled_when='rabi != None'),
                                                          Item('RabiTime', enabled_when='rabi != None')
                                                          ),
                                                   HGroup(Item('PerformHahnEcho', enabled_when='HahnEcho != None'),
                                                          Item('HahnEchoTime', enabled_when='HahnEcho != None')
                                                          ),
                                                   HGroup(Item('PerformRamsey', enabled_when='HahnEcho != None'),
                                                          Item('RamseyTime', enabled_when='HahnEcho != None')
                                                          ),
                                                  
                                                   label='measure'
                                                   ),
                                            VGroup(HGroup(Item('FitAC')
                                                          ),
                                                   label='analysis'
                                                   ),
                                            VGroup(HGroup(Item('confocal')
                                                          ),
                                                   label='confocal'
                                                   )
                                            )
                                     )
                              ),
                       
                       width=1024,height=768,title='AutoPanel', buttons=['OK','CANCEL'],
                       resizable=True, x=0, y=0
                       )
