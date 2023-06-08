from enthought.traits.ui.table_column import ObjectColumn
from enthought.traits.api import *
from enthought.traits.ui.api import *
import os
import copy
import re
import cPickle as pickle


#DTG = pi3d.get_pulse_generator()

from hardware.DTG_PF import DTG_PF as DTG


#DTG2 = pi3d.get_pulse_generator2()
#channel_map = pi3d.channel_map

from tools.utility import GetSetItemsMixin

# class CloseHandler(CloseHandler):
#     def close(self, info, is_ok):
#         os.chdir('D:\\Python\\pi3diamond')
#         pi3d.dump(info.object)
#         for editor in info.ui._editors:
#             if hasattr(editor, 'grid'):
#                 editor.grid.control.HideCellEditControl()
#         return Handler.close(self, info, is_ok)
selected_block=None
number_of_channels = 8
class BlockDataStep(HasTraits):
    """Represents one 'step' for the creation of a new block"""
    channels = Str(label='channels')
    length = Int(label='Length')
    increment = Int(0, label='Increment')  
    multiplier = Float(1., label='multiplier')
    #ignore_for_analysis = Bool(False)   #If True this pulsestep (if laser on) is not used for analyis
    use_as_tau = Bool(False)    #States whether length of this block is used as tau (x-axis of sequence) 
    repeat = Bool(True)
    model_selection=0
    
#define columns for blackdata-table
columns = []
number_of_columns = 6
length = 1./number_of_columns
columns.append( ObjectColumn(name='channels', width=2*length) )
columns.append( ObjectColumn(name='length', width=length) )
columns.append( ObjectColumn(name='increment', width=length) )
columns.append( ObjectColumn(name='multiplier', width=length) )
columns.append( ObjectColumn(name='use_as_tau', width=0.5*length) )
columns.append( ObjectColumn(name='repeat', width=0.5*length) )
blockdata_editor = TableEditor(
    columns = columns,
    deletable   = True,
    auto_size   = False,
    orientation = 'vertical',
    selection_mode = 'row',
    show_toolbar = True,
    row_factory = BlockDataStep )

class Block(HasTraits):
    """Represents one block in the DTG, to be displayed in the table.
    Needs name and sequence(=[(['channel'], length), ...]) for initialization"""
    def __init__(self, name, sequence, pp=None, stepdata=None, stepdata_repetitions=1):
        HasTraits.__init__(self)
        self.pp = pp

        self.name = name
        self.old_name = name
        self.sequence = sequence
        if stepdata != None:
            self.stepdata = stepdata
        self.stepdata_repetitions = stepdata_repetitions
    name = Str(label='Name')
    length = Int(label='Length')
    desc = Str('', label='Description')
    write2dtg = Bool(False, label='Write to DTG?')
    sequence = List(label='Sequence')   #sequence with labels for channels (according to channel_map)
    use_as_tau = List(label='Sequence-steps used as tau')   #defines which steps of the sequence are used as tau
    #stepdata = List(BlockDataStep)
    model_selection=0
    def _name_changed(self):
        "Deletes old block from DTG and writes new block if write2dtg=True"
        if hasattr(self, 'old_name') and (not self.pp.fast_write):
            print 'name changed'
            self.pp.DTG.write('BLOC:DEL "%s"' %str(self.old_name))
            if self.write2dtg == True:
                self._write2dtg_changed()
            self.old_name = self.name       
    def _write2dtg_changed(self):
        if self.pp.fast_write == False:
            if self.write2dtg == True:
                self.pp.DTG.ask('BLOC:LENG? "%s"' %str(self.name))
                if (self.pp.DTG.ask('BLOC:LENG? "%s"' %str(self.name)))[0:2] != '-1':
                    print 'Blockname already exist. Uncheck to delete Block in DTG.'
                else:
                    self.pp.Stop()
                    self.pp.WriteBlock(str(self.name), self.sequence)
                    self.pp.blocks_in_dtg.append(self.name)
        if self.write2dtg == False:
            self.pp.Stop()
            self.pp.DTG.write('BLOC:DEL "%s"' %str(self.name))
            self.pp.blocks_in_dtg.remove(self.name)            
    def _sequence_changed(self):
        if self.write2dtg:
            self.write2dtg = False
        length = 0
        for step in self.sequence:
            length += step[1]
        self.length = length
        self.stepdata = []
        for channels, length in self.sequence:
            step = BlockDataStep()
            for channel in channels:
                step.channels += channel + ', '
            step.length = length
            self.stepdata.append(step)
    def get_datavector(self):
        datavector = []
        for step in self.sequence:
            ch_vector = self.pp.ChannelsToString(step[0])
            for i in range(step[1]):
                datavector.append(ch_vector)
        return datavector

def on_select(block):
    if block != None:   #Sometimes gets called with block = None
        block.pp.selected_block = block
        
block_editor = TableEditor(
    columns = [
               ObjectColumn( name='name', width=0.25 ),
               ObjectColumn( name='length', width=0.25, editable=False ),
               ObjectColumn( name='desc', label='Description', width=0.25 ),
               ObjectColumn( name='write2dtg', label='Write to DTG?', width=0.25 ),
               ],
    deletable   = False,
    auto_size   = False,
    orientation = 'vertical',
    selection_mode = 'row',
    show_toolbar = False,
    #row_factory = Block,
    on_select = on_select
    )

class SequenceRow(HasTraits):
    """Represents one row in the DTG-sequence"""
    def __init__(self, label="", wait_trigger=False, block="", repetitions=0, event="", goto=""):
        HasTraits.__init__(self)
        self.label = label
        self.wait_trigger = wait_trigger
        self.block = block
        self.repetitions = repetitions
        self.event = event
        self.goto =goto
    label = Str(label='Label')
    wait_trigger = Bool(False, label='Wait Trig.')
    block  = Str(label='Block')
    repetitions = Int(label='Repetitions')
    event = Str(label='Event')
    goto = Str(label='Goto')   
    model_selection=0
sequence_editor = TableEditor(
    columns = [ObjectColumn( name='label', width=0.20 ),
               ObjectColumn( name='wait_trigger', label='Wait trig.', width=0.1),
               ObjectColumn( name='block', width=0.20 ),
               ObjectColumn( name='repetitions', width=0.10 ),
               ObjectColumn( name='event', width=0.20 ),
               ObjectColumn( name='goto', width=0.20 ),],
    deletable   = True,
    auto_size   = False,
    orientation = 'vertical',
    selection_mode = 'row',
    show_toolbar = True,
    row_factory = SequenceRow
    )

#class DTGChannel(HasTraits):

class PulsePattern(SingletonHasTraits, GetSetItemsMixin, DTG):
    def __init__(self,pulse_generator):
        SingletonHasTraits.__init__(self)
        self.autoloadBlocks()
        self.DTG=pulse_generator.instr
    autosave_filename='d:\\src\\pi3diamond\\DTG_Blocks.pyd'
    filepath = Str('D:\\Data\\Pulsefiles')
    run_dtg = Button(label='Run DTG')
    stop_dtg = Button(label='Stop DTG')
    initialize_dtg = Button(label='Initialize DTG')
    dtg_frequency = Float(1000, label='Freq. [MHz]')
    ch1_labels = Str('1, Laser', label='Ch1')
    ch2_labels = Str('2, MW, mw', label='Ch2')
    ch3_labels = Str('3, RF', label='Ch3')
    ch4_labels = Str('4, GATE', label='Ch4')
    ch5_labels = Str('5, vfgtrig', label='Ch5')
    ch6_labels = Str('6', label='Ch6')
    ch7_labels = Str('7', label='Ch7')
    ch8_labels = Str('8', label='Ch8')
    channel_map = Property(trait=Dict, label='Channel Map', depends_on='ch1_labels, ch2_labels, ch3_labels, ch4_labels, ch5_labels, ch6_labels, ch7_labels, ch8_labels')
    
    blocks = List(Block)
    delete_blocks = Button(label='Delete all blocks from DTG')
    fast_write = Bool(False, label='Fast write mode', transient=True)
    update_blocks = Button(label='Update')
    available_blocks = Property(trait=List, label='Available blocks', depends_on='blocks')
    selected_block = Trait(Block)
    selected_block_name = Str(label='Selected block', style='readonly')
    delete_block = Button(label='Delete block')
    save_block2file = Button(label='Save block to file')
    blocks_in_dtg = List(['custom'], label='Blocks written to DTG')
    running_block = Str(label='Running block')
    load_block_from_file = Button(label='Load block from file')
    block_file = File(label='Block file')
    #block_file_view = View(Item('block_file', editor=FileEditor()),
    #                       buttons=OKCancelButtons)
    
    sequence = List(SequenceRow)
    write_sequence = Button(label='Write seqeuence')
    sequence_filename = String(label='filename')
    sequence_save=Button(label='save sequence')
    sequence_load=Button(label='load sequence')
    sequence_folder='d:\\data\\dtg sequences\\'
    
    newblock = List(BlockDataStep)
    repetitions = Int(1, label='Number of Repetitions')
    newblockname = Str('blockname', label='Blockname')
    generate_block = Button(label='Generate Block')
    #fast_write_block = Button(label='Fast-write as sequence')
    block_to_load = Str('choose block', label='')
    load_block = Button(label='Load block')
    #trigger_4_awg = Bool(False, label='Make trigger for AWG?')
    awg_trigger_channel = Int(0, label='AWG trigger channel')
    
    traits_view = View(
        VGroup(HGroup(VGroup(Item('run_dtg', show_label=False),
                             Item('stop_dtg', show_label=False),
                             Item('initialize_dtg', show_label=False),
                             Item('dtg_frequency')
                             ),
                      VGroup(Item('ch1_labels', width=-150),
                             Item('ch2_labels', width=-150),
                             Item('ch3_labels', width=-150),
                             Item('ch4_labels', width=-150),
                             ),
                      VGroup(Item('ch5_labels', width=-150),
                             Item('ch6_labels', width=-150),
                             Item('ch7_labels', width=-150),
                             Item('ch8_labels', width=-150),
                             ),
                      ),
                Tabbed(VGroup(HGroup(Item('delete_blocks', show_label=False),
                                     Item('fast_write'),
                                     Item('update_blocks', show_label=False, visible_when='fast_write'),),
                              HGroup(Item('blocks', show_label=False, editor=block_editor),),
                              HGroup(Item('running_block', editor=EnumEditor(name='blocks_in_dtg')),
                                     Item('selected_block_name'),
                                     Item('delete_block', show_label=False),
                                     Item('save_block2file', show_label=False),
                                     ),
                              HGroup(Item('block_file', editor=FileEditor(filter=['*.dat'])),
                                     Item('load_block_from_file', show_label=False),
                                     ),
                              label='Blocks'),
                       VGroup(HGroup(Item('sequence', show_label=False, editor=sequence_editor),),
                              HGroup(Item('write_sequence', show_label=False),Item('sequence_filename'),Item('sequence_save',show_label=False),Item('sequence_load',show_label=False)),
                              label='Sequence'),
                       VGroup(HGroup(Item('block_to_load', editor=EnumEditor(name='available_blocks'), show_label=False),
                                     Item('load_block', show_label=False),
                                     #Item('trigger_4_awg'),
                                     Item('awg_trigger_channel', visible_when='trigger_4_awg'),
                                     ),
                              Item('newblock', show_label=False, editor=blockdata_editor),
                              HGroup(Item('repetitions'),
                                     Item('newblockname'),
                                     Item('generate_block', show_label=False)
                                     ),
                              label='Block generator',
                              ),
                        ),
               ),
        title='PulsePattern', width=700, height=560, x=1090, y=0,
        resizable=True, buttons = ['OK'], kind='live',)
    
    def _write_sequence_changed(self):
        if self.running_block == 'custom':
            self._running_block_changed()
        else:
            if 'custom' not in self.blocks_in_dtg:
                self.blocks_in_dtg.append('custom')
            self.running_block = 'custom'
    
    def _sequence_save_changed(self):
        try:
            f=open(self.sequence_folder+self.sequence_filename+'.pyd','w')
            dump=[]
            for entry in self.sequence:
                dump.append(entry)
            pickle.dump(dump,f)
        except:
            pass
        finally:
            f.close()
    
    def _sequence_load_changed(self):
        try:
            f=open(self.sequence_folder+self.sequence_filename+'.pyd','r')
            seq=pickle.load(f)
            self.sequence=[]
            for entry in seq:
                self.sequence.append(SequenceRow(label=entry.label,wait_trigger=entry.wait_trigger,block=entry.block,repetitions=entry.repetitions,event=entry.event,goto=entry.goto))
        except:
            pass
        finally:
            f.close()
            
    def _nuclearOPs_change_sequence(self):
        self.Stop()
        self.DTG.write('SEQ:LENG %s' %len(self.sequence))
        for i, line in enumerate(self.sequence):
            self.DTG.write('SEQ:DATA %i, '%i  + '"%s",%i,"%s",%i,"%s","%s"' %(line.label, line.wait_trigger, line.block, line.repetitions, line.event, line.goto))
        #self.running_block = 'custom'
    
    @cached_property
    def _get_available_blocks(self):
        available_blocks = []
        for block in self.blocks:
            available_blocks.append(block.name)
        return available_blocks
    
    def _load_block_from_file_changed(self):
        #os.chdir(self.filepath)
        file = open(self.block_file, 'r')
        #reader = csv.reader(file)
        sequence = []
        name = file.next()[:-1]
        desc = file.next()[:-1]
        for line in file:
            if line != '':
                data = line.split(', ')
                sequence.append( (data[:-1], int(data[-1])) )
        file.close()
        block = Block(name=name, sequence=sequence, pp=self)
        block.desc = desc
        self.blocks.append(block)
    
    def _save_block2file_changed(self):
        os.chdir(self.filepath)
        block = self.selected_block
        file = open( block.name + '.dat', 'w' )
        file.write( '%s\n'%(block.name) )
        file.write( '%s\n'%(block.desc) )
        for step in block.sequence:
            for channel in step[0]:
                file.write( channel+', ' )
            file.write('%s\n'%step[-1])
        file.close()
        file = open( block.name + '.txt', 'w' )
        datavector = block.get_datavector()
        for row in datavector[:-1]:
            file.write(row + '\n')
        file.write(datavector[-1])
        file.close()
        if hasattr(block, 'stepdata'):
            pass
        print 'block %s saved' %(block.name)
    
    def _delete_block_changed(self, block=None):
        #if block == None:
        block = self.selected_block
        for i in range(len(self.blocks)):
            if self.blocks[i] == block:
                if self.blocks[i].write2dtg == True:
                    self.blocks[i].write2dtg = False
                self.blocks.remove(block)
                self.selected_block = None
                break
    
    def _selected_block_changed(self):
        if self.selected_block != None:
            self.selected_block_name = self.selected_block.name
        else:
            self.selected_block_name = ''
    
    def add_block(self, newblock, write2dtg=False):
        for block in self.blocks:
            if str(block.name) == str(newblock.name):
                print 'delete old block'
                self.selected_block = block
                self._delete_block_changed()
        self.blocks.append(newblock)
        if write2dtg:
            self.blocks[-1].write2dtg = True
    
    def _generate_block_changed(self):
        """Generates a new block using the given 'BlockDataSteps'. Also creates 
        the DTG-vector-data and a sequence-data (=[(['channels'], length), etc.], this is used by the DTG module).
        use_as_tau can be set to True so that the pulsed module can automatically generate the x-axis."""
        #first create a commandlist of the form [('channelvector', length), ...]
        
        def make_step(step, reps):
            """Transform one row into [['channels'], length]"""
            length = step.length + reps * step.increment
            if step.multiplier != 1.:
                length = int(round(step.length * step.multiplier**reps))
                temp = length % 4
                length += temp
            #length = step.length + reps * step.increment * step.multiplier**reps
            if length < 0:
                length = 0
            channels = []
            for channel in re.findall('\w+', step.channels):
                channels.append(str(channel))
            return [channels, int(length)]
        
        sequence = []
        use_as_tau = []
        stop_step = []
        use_as_tau_stop = []
        start = True
        for i in range(1, len(self.newblock)-1):
            #only initial or final non-repeated steps are possible
            if self.newblock[i].repeat == False and self.newblock[i-1].repeat == True and self.newblock[i+1].repeat == True:
                print 'non-repeated steps only possible at start or end of sequence'
                return
        for step in self.newblock:
            if start:
                if step.repeat == False:
                    sequence.append(make_step(step, 0))
                    use_as_tau.append(step.use_as_tau)
                else:
                    start = False
            else:
                if step.repeat == False:
                    stop_step.append(make_step(step, 0))
                    use_as_tau_stop.append(step.use_as_tau)
            
        for rep in range(self.repetitions):
            for i in range(len(self.newblock)):
                if self.newblock[i].repeat == True:
                    sequence.append( make_step(self.newblock[i], rep) )
                    use_as_tau.append(self.newblock[i].use_as_tau)
                    
        #now append final steps to the sequence
        sequence.extend(stop_step)
        use_as_tau.extend(use_as_tau_stop)
        
        #if self.trigger_4_awg:
        #    channel = reverse_channel_map['%s'%self.awg_trigger_channel]
        #    sequence[0][0].append(channel)
        
        block = Block(name=str(self.newblockname), sequence=sequence, pp=self,
                      stepdata=copy.deepcopy(self.newblock), stepdata_repetitions=self.repetitions)
        block.use_as_tau = use_as_tau
        #block.stepdata = copy.deepcopy(self.newblock)
        for oldblock in self.blocks:
            if str(oldblock.name) == str(block.name):
                print 'delete old block'
                self.selected_block = oldblock
                self._delete_block_changed()
        self.blocks.append(block)
        print "block '"+str(block.name)+"' generated"
		#self.autosaveBlocks()
		
	
        self.autosaveBlocks()	
    def store_dtg_state(self):
        self.save_state = self.State()        
        self.save_running_block = self.running_block
        self.save_dtg_frequency = self.dtg_frequency
        
    def restore_dtg_state(self):
        self.Stop()
        self.dtg_frequency  = self.save_dtg_frequency        
        if self.save_state == '1':
            self.run_block(self.save_running_block)
        elif self.save_state == '0':
            self.set_running_block_to_DTG(self.save_running_block)
        else:
            print 'Error: unknown DTG state: ', self.save_state
        
    
    def run_block(self, blockname):
        if self.running_block == blockname:
            self._running_block_changed()
        else:
            self.running_block = blockname
    
    def _running_block_changed(self):
        self.Stop()
        if self.running_block == 'custom':
            self.DTG.write('SEQ:LENG %s' %len(self.sequence))
            for i, line in enumerate(self.sequence):
                self.DTG.write('SEQ:DATA %i, '%i  + '"%s",%i,"%s",%i,"%s","%s"' %(line.label, line.wait_trigger, line.block, line.repetitions, line.event, line.goto))
            self.running_block = 'custom'
        else:
            self.DTG.write('SEQ:LENG 1')
            self.DTG.write('SEQ:DATA 0, "",0,"%s",0,"",""' %str(self.running_block))     
        self.Run()
            
    def _load_block_changed(self):
        for block in self.blocks:
            if str(block.name) == str(self.block_to_load):
                del self.newblock[:]
                for entry in block.stepdata:
                    self.newblock.append(copy.deepcopy(entry))
                self.repetitions = block.stepdata_repetitions
                self.newblockname = block.name
                break
        else:
            print 'block not found'
    
    def set_sequence(self, sequence):
        del self.sequence[:]
        self.sequence = copy.deepcopy(sequence)
    
    def _run_dtg_changed(self):
        self.Run()
        
    def _stop_dtg_changed(self):
        self.Stop()
        
    def _delete_blocks_changed(self):
        self.Stop()
        for block in self.blocks:
            block.write2dtg = False
        self.DTG.write('BLOC:DEL:ALL')
        
    def _dtg_frequency_changed(self):
        #DTG.Stop()
        self.setTimeBase(self.dtg_frequency*1e6)
    
    def _initialize_dtg_changed(self):
        if self.fast_write:
            self._update_blocks_changed()
        else:
            self.Stop()
            self.setTimeBase(self.dtg_frequency*1e6)
            self.DTG.write('BLOC:DEL:ALL')
            self.blocks_in_dtg = ['custom']
            for block in self.blocks:
                if block.write2dtg == True:
                    block._write2dtg_changed()
            self._running_block_changed()
    
    def _update_blocks_changed(self):
        try:
            self.autosaveBlocks()
        except:
            pass
        updatingblocks = []
        self.blocks_in_dtg = ['custom']
        for block in self.blocks:
            if block.write2dtg == True:
                updatingblocks.append(block)
                self.blocks_in_dtg.append(block.name)
        self.FastWrite(updatingblocks)
        self._dtg_frequency_changed()
        self.DTG.ask('TBAS:RUN?')
        #self.running_block = ''
        self._running_block_changed()
    

    #Nathan take a look here
    def autosaveBlocks(self):
        f=open(self.autosave_filename,'wb')
        a=list()
        for block in self.blocks:
            a.append(block)
        pickle.dump(a,f)
        f.close()
        
    def autoloadBlocks(self):
        try:
            f=open(self.autosave_filename,'rb')
            blocks=pickle.load(f)
            self.blocks=[]
            for b in blocks:
                b.pp=self
                self.blocks.append(b)
            f.close()
        except:
            pass
        
    def _get_channel_map(self):
        channel_map = {0:[], 1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[]}
        for label in re.findall('\w+', self.ch1_labels):
            channel_map[0].append(label)
        for label in re.findall('\w+', self.ch2_labels):
            channel_map[1].append(label)
        for label in re.findall('\w+', self.ch3_labels):
            channel_map[2].append(label)
        for label in re.findall('\w+', self.ch4_labels):
            channel_map[3].append(label)
        for label in re.findall('\w+', self.ch5_labels):
            channel_map[4].append(label)
        for label in re.findall('\w+', self.ch6_labels):
            channel_map[5].append(label)
        for label in re.findall('\w+', self.ch7_labels):
            channel_map[6].append(label)
        for label in re.findall('\w+', self.ch8_labels):
            channel_map[7].append(label)
        return channel_map
    
    def __getstate__(self):
        """Returns current state of a selection of traits.
        Overwritten HasTraits.
        """
        state = SingletonHasTraits.__getstate__(self)
        for key in ['available_blocks']:
            if state.has_key( key ):
                del state[ key ]  
        return state  
    






