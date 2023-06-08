
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

About ODMRP:
Without pulsed box checked, it is just the usual ODMR.
With the box checked, it will go to pulsed mode, which means the sequence is the loop of [-> (laser + mw) -> wait -> laser ->].

About MW:
User can define the MW parameters for different target. Make sure the MWUser is activated. Please take note that MWPulsed and MWUser are controlled by two different option. 
"""

class Target(HasTraits):
    ID=Str
    #MWPower=Float
    MWBegin=Float
    MWEnd=Float
    MWDelta=Float
    #MWPulsed=Bool
    #MWLaser=Float
    #MWWait=Float
    Perform=Bool
    

class AutoPanelODMR( FreeJob,HasTraits):
    
    UseReference=Bool(True,label='Refocus')
    ReferenceSpot=Str('ref',label='Reference spot')
    FreeRuns=Int(10,label='Free runs')
    n=0
    CurrentSpot=Str('None', label='Current spot')
    LoopOption=Bool(False,label='Loop')
    LoopNumber=Int(1, desc='Start from 1', label='Number of loops')
    SleepTime=Int(0, label='Sleep time [s]')  
    
    SpotInfo =List(Target)
    ImportSpots=Button(label='Import New Spots')
    EmptyList=Button(label='empty spot list')
    
    folderUser = Bool(False,label='User defined folder name')
    folderName = Str('0', label = 'Folder name')
    
    MWUser = Bool(False,label='User defined MW parameters')
    
    #measurement control panel
    
    PerformforeachND=Bool(False,label='perform a list of measurements for each ND')
      
    PerformODMR=Bool(False,label='perform ODMR')
    ODMRTime=Float(100.,label='ODMR integration time [s]')
    ODMROrder=Int(0, label='Job Priority')
    ODMRWaitTime=Float(0, label='Wait time after ODMR[s]')
    
    PerformODMRP=Bool(False,label='perform ODMRP')
    ODMRPTime=Float(100.,label='ODMRP integration time [s]')
    ODMRPOrder=Int(0, label='Job Priority')
    ODMRPWaitTime=Float(0, label='Wait time after ODMRP[s]')
    
    PerformODMRPP=Bool(False,label='perform ODMRPP')
    ODMRPPTime=Float(100.,label='ODMRPP integration time [s]')
    ODMRPPOrder=Int(0, label='Job Priority')
    ODMRPPWaitTime=Float(0, label='Wait time after ODMRPP[s]')
    
    PerformODMRN=Bool(False,label='perform ODMRN')
    ODMRNTime=Float(100.,label='ODMRN integration time [s]')
    ODMRNOrder=Int(0, label='Job Priority')
    ODMRNWaitTime=Float(0, label='Wait time after ODMRN[s]')
    
    PerformODMRJ=Bool(False,label='perform ODMRJ')
    ODMRJTime=Float(100.,label='ODMRJ integration time [s]')
    ODMRJOrder=Int(0, label='Job Priority')
    ODMRJWaitTime=Float(0, label='Wait time after ODMRJ[s]')
    JMWBegin=Float(-40, label='MW Power Begins[dBm]')
    JMWEnd=Float(-30, label='MW Power Ends[dBm]')
    JMWDelta=Float(1.0, label='MW Power Delta[dBm]')
   
    SaveString=Str(label='pre-savename')
    LoadData=Button(label='Load Target Info')
    SaveData=Button(label='Save Target Info')
    ExportASCI=Button(label='export table as ascii')
    
    table_editor = TableEditor(columns = [ObjectColumn(name='ID',width=120),
                                          #ObjectColumn(name='MWPower',format='%3.2f',width=50),
                                          ObjectColumn(name='MWBegin',format='%3.2f',width=50),
                                          ObjectColumn(name='MWEnd',format='%3.2f',width=50),
                                          ObjectColumn(name='MWDelta',format='%3.2f',width=50),
                                          #ObjectColumn(name='MWPulsed',width=200),
                                          #ObjectColumn(name='MWLaser',format='%3.2f',width=50),
                                          #ObjectColumn(name='MWWait',format='%3.2f',width=50),
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
        #Header=list(['ID','MWPower','MWBegin','MWEnd','MWDelta','MWPulsed','MWLaser','MWWait'])
        Header=list(['ID','MWBegin','MWEnd','MWDelta'])
        for items in Header:
            f.write(items)
            f.write('\t')
        f.write('\n')   
        for target in self.SpotInfo:
            #Info=list([str(target.ID),str(target.MWPower),str(target.MWBegin),str(target.MWEnd),str(target.MWDelta),str(target.MWPulsed),str(target.MWLaser),str(target.MWWait)])
            Info=list([str(target.ID),str(target.MWBegin),str(target.MWEnd),str(target.MWDelta)])
            for items in Info:
                f.write(items)
                f.write('\t')
            f.write('\n') 
        
        f.close()     
        
    #def __init__(self,auto_focus, confocal,odmr,odmrp):
    def __init__(self,auto_focus,confocal,odmr,odmrp,odmrpp,odmrn):
        super(AutoPanelODMR, self).__init__()     
        self.auto_focus=auto_focus   
        self.confocal=confocal
        self.odmr = odmr
        self.odmrp = odmrp
        self.odmrpp = odmrpp
        self.odmrn = odmrn
      
        
        print "Welcome to AutoPanelODMR! For the SC measurement, please keep the default mw power!!! (SMIQ = -18 dBm)"
          
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
    
    def target(self, x, y, z):
        self.confocal.x - self.a
    
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
                self.confocal.x, self.confocal.y, self.confocal.z = self.auto_focus.targets[TargetID] + self.auto_focus.current_drift
                time.sleep(1.0)
                self.auto_focus.submit()
        
            return 'True'
    
        except:
            print 'Refocus failed'
            return 'False'
            
    def performodmrpp(self, TargetID, TargetMWBegin, TargetMWEnd, TargetMWDelta, Ln):
        if (self.PerformODMRPP and self.odmrpp):
            self.odmrpp.stop_time=self.ODMRPPTime
            if self.MWUser == True:
                #self.odmrp.power=Target.MWPower
                self.odmrpp.frequency_begin=TargetMWBegin
                self.odmrpp.frequency_end=TargetMWEnd
                self.odmrpp.frequency_delta=TargetMWDelta
            #if Target.MWPulsed == True:
            #    self.odmrpp.pulsed=True
            #    self.odmrpp.laser=Target.MWLaser
            #    self.odmrpp.wait=Target.MWWait
            #if Target.MWPulsed == False:
            #    self.odmrpp.pulsed=False
            self.odmrpp.submit()
            while self.odmrp.state != 'done':
                threading.currentThread().stop_request.wait(1.0)
                if threading.currentThread().stop_request.isSet():
                    break
                               
            savename= self.SaveString+TargetID+'_ODMRPP_Loop'+str(Ln)
            try:                    
                self.odmrpp.save_all(savename)
                                                       
            except:
                logging.getLogger().exception('File could not be saved.(ODMRPP)')
            try:                    
                focusXYZ = open("focusXYZ_ODMRPP" + str(TargetID) + "_Loop" + str(Ln) + ".txt","w+")
                focusXYZ.write("Focus:" + str(self.confocal.x) + "," + str(self.confocal.y) + "," + str(self.confocal.z))
                focusXYZ.close()      
            except:
                logging.getLogger().exception('File could not be saved.(FocusXYZ_ODMRPP)')
                                
            print('Wait for' + str(self.ODMRPPWaitTime) + 'seconds.')
            time.sleep(self.ODMRPPWaitTime)
                  
    def performodmrp(self, TargetID, TargetMWBegin, TargetMWEnd, TargetMWDelta, Ln):
        if (self.PerformODMRP and self.odmrp):
            self.odmrp.stop_time=self.ODMRPTime
            if self.MWUser == True:
                #self.odmrp.power=Target.MWPower
                self.odmrp.frequency_begin=TargetMWBegin
                self.odmrp.frequency_end=TargetMWEnd
                self.odmrp.frequency_delta=TargetMWDelta
            #if Target.MWPulsed == True:
            #    self.odmrp.pulsed=True
            #    self.odmrp.laser=Target.MWLaser
            #    self.odmrp.wait=Target.MWWait
            #if Target.MWPulsed == False:
            #    self.odmrp.pulsed=False
            self.odmrp.submit()
            while self.odmrp.state != 'done':
                threading.currentThread().stop_request.wait(1.0)
                if threading.currentThread().stop_request.isSet():
                    break
                                
            savename= self.SaveString+TargetID+'_ODMRP_Loop'+str(Ln)
            try:                    
                self.odmrp.save_all(savename)
                                                       
            except:
                logging.getLogger().exception('File could not be saved.(ODMRP)')
            try:                    
                focusXYZ = open("focusXYZ_ODMRP" + str(TargetID) + "_Loop" + str(Ln) + ".txt","w+")
                focusXYZ.write("Focus:" + str(self.confocal.x) + "," + str(self.confocal.y) + "," + str(self.confocal.z))
                focusXYZ.close()      
            except:
                logging.getLogger().exception('File could not be saved.(FocusXYZ_ODMRP)')
                                
            print('Wait for' + str(self.ODMRPWaitTime) + 'seconds.')
            time.sleep(self.ODMRPWaitTime)
    
    def performodmrn(self, TargetID, TargetMWBegin, TargetMWEnd, TargetMWDelta, Ln):
        if (self.PerformODMRN and self.odmrn):
            self.odmrn.stop_time=self.ODMRNTime
            if self.MWUser == True:
                #self.odmrp.power=Target.MWPower
                self.odmrn.frequency_begin=TargetMWBegin
                self.odmrn.frequency_end=TargetMWEnd
                self.odmrn.frequency_delta=TargetMWDelta
            #if Target.MWPulsed == True:
            #    self.odmrp.pulsed=True
            #    self.odmrp.laser=Target.MWLaser
            #    self.odmrp.wait=Target.MWWait
            #if Target.MWPulsed == False:
            #    self.odmrp.pulsed=False
            self.odmrn.submit()
            while self.odmrn.state != 'done':
                threading.currentThread().stop_request.wait(1.0)
                if threading.currentThread().stop_request.isSet():
                    break
                                
            savename= self.SaveString+TargetID+'_ODMRN_Loop'+str(Ln)
            try:                    
                self.odmrn.save_all(savename)
                                                       
            except:
                logging.getLogger().exception('File could not be saved.(ODMRN)')
            try:                    
                focusXYZ = open("focusXYZ_ODMRN" + str(TargetID) + "_Loop" + str(Ln) + ".txt","w+")
                focusXYZ.write("Focus:" + str(self.confocal.x) + "," + str(self.confocal.y) + "," + str(self.confocal.z))
                focusXYZ.close()      
            except:
                logging.getLogger().exception('File could not be saved.(FocusXYZ_ODMRN)')
                                
            print('Wait for' + str(self.ODMRNWaitTime) + 'seconds.')
            time.sleep(self.ODMRNWaitTime)
    
    def performodmr(self, TargetID, TargetMWBegin, TargetMWEnd, TargetMWDelta, Ln):
        if (self.PerformODMR and self.odmr):
            self.odmr.stop_time=self.ODMRTime
            if self.MWUser == True:
                #self.odmr.power=Target.MWPower
                self.odmr.frequency_begin=TargetMWBegin
                self.odmr.frequency_end=TargetMWEnd
                self.odmr.frequency_delta=TargetMWDelta
            #if Target.MWPulsed == True:
            #    self.odmr.pulsed=True
            #    self.odmr.laser=Target.MWLaser
            #    self.odmr.wait=Target.MWWait
            #if Target.MWPulsed == False:
            #    self.odmr.pulsed=False
            self.odmr.submit()
            while self.odmr.state != 'done':
                threading.currentThread().stop_request.wait(1.0)
                if threading.currentThread().stop_request.isSet():
                    break
                                
            savename= self.SaveString+TargetID+'_ODMR_Loop'+str(Ln)
            try:                    
                self.odmr.save_all(savename)
                                                       
            except:
                logging.getLogger().exception('File could not be saved.(ODMR)')
                                
            try:                    
                focusXYZ = open("focusXYZ_ODMR" + str(TargetID) + "_Loop" + str(Ln) + ".txt","w+")
                focusXYZ.write("Focus:" + str(self.confocal.x) + "," + str(self.confocal.y) + "," + str(self.confocal.z))
                focusXYZ.close()      
            except:
                logging.getLogger().exception('File could not be saved.(FocusXYZ_ODMR)')
                                
            print('Wait for' + str(int(self.ODMRWaitTime)) + 'seconds.')
            time.sleep(self.ODMRWaitTime)
    
    def performodmrj(self, TargetID, TargetMWBegin, TargetMWEnd, TargetMWDelta, Ln):
        if (self.PerformODMRJ and self.odmr):              
            powerlist = np.arange(self.JMWBegin, self.JMWEnd+self.JMWDelta, self.JMWDelta)            
            for p in powerlist:
                print(p)
                self.odmr.stop_time=self.ODMRJTime
                if self.MWUser == True:
                    self.odmr.power=p
                    # self.odmr.frequency_begin=Target.MWBegin
                    # self.odmr.frequency_end=Target.MWEnd
                    # self.odmr.frequency_delta=Target.MWDelta
                    # if Target.MWPulsed == True:
                    # self.odmr.pulsed=True
                    # self.odmr.laser=Target.MWLaser
                    # self.odmr.wait=Target.MWWait
                    # if Target.MWPulsed == False:
                    # self.odmr.pulsed=False
                self.odmr.submit()
                while self.odmr.state != 'done':
                    threading.currentThread().stop_request.wait(1.0)
                    if threading.currentThread().stop_request.isSet():
                        break
                                    
                savename= self.SaveString+TargetID+'_ODMRJ_Loop'+str(Ln)+str(p)+'dBm'
                try:                    
                    self.odmr.save_all(savename)
                                                           
                except:
                    logging.getLogger().exception('File could not be saved.(ODMRJ)')
                                    
                try:                    
                    focusXYZ = open("focusXYZ_ODMRJ" + str(TargetID) + "_Loop" + str(Ln) + ".txt","w+")
                    focusXYZ.write("Focus:" + str(self.confocal.x) + "," + str(self.confocal.y) + "," + str(self.confocal.z))
                    focusXYZ.close()      
                except:
                    logging.getLogger().exception('File could not be saved.(FocusXYZ_ODMRJ)')
                                    
                print('Wait for' + str(int(self.ODMRJWaitTime)) + 'seconds.')
                time.sleep(self.ODMRJWaitTime)
    
    
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
        
        if self.folderUser == True:
            folder = folder=path+'/'+self.folderName
            while os.path.exists(folder):
                folder=folder + '_warning'
        if self.folderUser == False:
            folder=path+'/'+str(number).zfill(3)
            while os.path.exists(folder):
               number +=1
               folder=path+'/'+ str(number).zfill(3)
        
        #folder=path+'/'+str(number).zfill(3)
        #while os.path.exists(folder):
        #    number +=1
        #    folder=path+'/'+ str(number).zfill(3)
        
        os.makedirs(folder)
        os.chdir(folder)
        
        endLabView = open("toLabView.txt","w+")
        endLabView.write("0")
        endLabView.close()
        
        funclist=[self.performodmrpp,self.performodmrp,self.performodmrn,self.performodmr,self.performodmrj]    
        prioritylist=[self.ODMRPPOrder,self.ODMRPOrder,self.ODMRNOrder,self.ODMROrder,self.ODMRJOrder]          
        orderedfunclist=[]      

        while 0 in prioritylist:
            prioritylist.remove(0)
        orderedfunclist=[i for j,i in sorted(zip(prioritylist,funclist))]
        
        try:
            self.state='run'
            self.n=0
            if self.LoopOption != True:
                self.LoopNumber = 1
                self.SleepTime = 0  
            for ln in range(0,self.LoopNumber):
                if self.PerformforeachND == True:
                    for Target in self.SpotInfo:
                    
                        self.n+=1
                        #print Target.ID
                        self.CurrentSpot=Target.ID
                        if Target.Perform and self.refocus(Target.ID):
                            for k in range(len(orderedfunclist)):
                                orderedfunclist[k](Target.ID, Target.MWBegin, Target.MWEnd, Target.MWDelta, ln)
                        if threading.currentThread().stop_request.isSet():
                            break
                else:
                    for k in range(len(orderedfunclist)):
                        for Target in self.SpotInfo:
                            print(Target.ID)
                            if Target.Perform and self.refocus(Target.ID):

                                self.n+=1
                                #print Target.ID
                                self.CurrentSpot=Target.ID
                                orderedfunclist[k](Target.ID, Target.MWBegin, Target.MWEnd, Target.MWDelta, ln)
                                print('done')
                                if threading.currentThread().stop_request.isSet():
                                    break
                            
                startTime = "Start : %s" % time.ctime()
                print startTime
                startLabView = open("toLabView.txt","w+")
                startLabView.write("1")
                startLabView.close()
                if self.UseReference:
                    self.auto_focus.current_target=self.ReferenceSpot
                    self.auto_focus.submit()
                if ln == (self.LoopNumber-1):
                    self.SleepTime = 1
                time.sleep(self.SleepTime)                    
                endTime = "End : %s" % time.ctime()
                print endTime
                endLabView = open("toLabView.txt","w+")
                endLabView.write("0")
                endLabView.close()
                timeRecord = timeRecord + startTime + ", " + endTime + "\n"
            
            timeFile = open("timeRecord.txt","w+")          
            timeFile.write(timeRecord)
            timeFile.close()
            self.folderUser = False
            self.folderName = 'new name'
            os.chdir(path)
                   
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
                                     Tabbed(VGroup(HGroup(Item('folderUser'),
                                                          Item('folderName', enabled_when='folderUser == Ture')
                                                          ),
                                                   HGroup(Item('MWUser')
                                                          ),
                                                   HGroup(Item('UseReference'),
                                                          Item('ReferenceSpot', enabled_when='UseReference == True'),
                                                          Item('FreeRuns', enabled_when='UseReference == True')
                                                          ),
                                                   HGroup(Item('LoopOption'),
                                                          Item('LoopNumber', enabled_when='LoopOption == True'),
                                                          Item('SleepTime', enabled_when='LoopOption == True')
                                                          ),
                                                   HGroup(Item('PerformforeachND')),    
                                                   HGroup(Item('PerformODMRPP', enabled_when='odmrpp != None'),
                                                          Item('ODMRPPOrder', enabled_when='odmrpp != None')
                                                          ),
                                                   HGroup(Item('ODMRPPTime', enabled_when='odmrpp != None'),
                                                          Item('ODMRPPWaitTime', enabled_when='odmrpp != None')
                                                          ),
                                                   HGroup(Item('PerformODMRP', enabled_when='odmrp != None'),
                                                          Item('ODMRPOrder', enabled_when='odmrp != None')
                                                          ),
                                                   HGroup(Item('ODMRPTime', enabled_when='odmrp != None'),
                                                          Item('ODMRPWaitTime', enabled_when='odmrp != None')
                                                          ),
                                                   HGroup(Item('PerformODMRN', enabled_when='odmrn != None'),
                                                          Item('ODMRNOrder', enabled_when='odmrp != None')
                                                          ),
                                                   HGroup(Item('ODMRNTime', enabled_when='odmrn != None'),
                                                          Item('ODMRNWaitTime', enabled_when='odmrn != None')
                                                          ),
                                                   HGroup(Item('PerformODMR', enabled_when='odmr != None'),
                                                          Item('ODMROrder', enabled_when='odmr != None')
                                                          ),
                                                   HGroup(Item('ODMRTime', enabled_when='odmr != None'),
                                                          Item('ODMRWaitTime', enabled_when='odmr != None')
                                                          ), 
                                                   VGroup(HGroup(Item('PerformODMRJ', enabled_when='odmr != None'),
                                                                 Item('ODMRJOrder', enabled_when='odmr != None')
                                                                 ),
                                                          HGroup(Item('ODMRJTime', enabled_when='odmr != None'),
                                                                 Item('ODMRJWaitTime', enabled_when='odmr != None')),
                                                          HGroup(Item('JMWBegin', enabled_when='odmr != None'),
                                                                 Item('JMWEnd', enabled_when='odmr != None'),
                                                                 Item('JMWDelta', enabled_when='odmr != None'),
                                                          )),
                                                   label='measure'
                                                   ),
                                            VGroup(HGroup(Item('confocal')
                                                          ),
                                                   label='confocal'
                                                   )
                                            )
                                     )
                              ),
                       
                       width=1024,height=768,title='AutoPanelODMR', buttons=['OK','CANCEL'],
                       resizable=True, x=0, y=0
                       )
