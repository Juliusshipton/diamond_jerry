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

from tools.emod import ManagedJob

import hardware.api as ha

from analysis import fitting

from tools.utility import GetSetItemsHandler, GetSetItemsMixin

class ODMRHandler(GetSetItemsHandler):

	def saveLinePlot(self, info):
		filename = save_file(title='Save Line Plot')
		if filename is '':
			return
		else:
			if filename.find('.png') == -1:
				filename = filename + '.png'
			info.object.save_line_plot(filename)

	def saveMatrixPlot(self, info):
		filename = save_file(title='Save Matrix Plot')
		if filename is '':
			return
		else:
			if filename.find('.png') == -1:
				filename = filename + '.png'
			info.object.save_matrix_plot(filename)
	
	def saveAll(self, info):
		filename = save_file(title='Save All')
		if filename is '':
			return
		else:
			info.object.save_all(filename)


class gatedODMR(ManagedJob, GetSetItemsMixin):
	"""Provides ODMR measurements."""

	# starting and stopping
	keep_data = Bool(False) # helper variable to decide whether to keep existing data
	resubmit_button = Button(label='resubmit', desc='Submits the measurement to the job manager. Tries to keep previously acquired data. Behaves like a normal submit if sequence or time bins have changed since previous run.')	 
	
	# measurement parameters
	power = Range(low= -100., high=25., value= -18, desc='Power [dBm]', label='Power [dBm]', mode='text', auto_set=False, enter_set=True)
	frequency_begin = Range(low=1, high=20e9, value=2.85e9, desc='Start Frequency [Hz]', label='Begin [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	frequency_end = Range(low=1, high=20e9, value=2.90e9, desc='Stop Frequency [Hz]', label='End [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	frequency_delta = Range(low=1e-3, high=20e9, value=1e6, desc='frequency step [Hz]', label='Delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	freq_length = Int(value = 0, label='length of freq list')
	# measurement data	  
	frequency = Array()
	counts = Array()
	counts_matrix = Array()
	run_time = Float(value=0.0, desc='Run time [s]', label='Run time [s]')
	
	exposure = Int(value = 0, label='ccd exposure time [us]') 
	trigger_delay = Int(value = 0, label='random trigger delay [ns]') 
	def __init__(self):
		super(gatedODMR, self).__init__()
		self.on_trait_change(self._update_freq_length, 'frequency_begin,frequency_end,frequency_delta', dispatch='ui')


	def _frequency_default(self):
		return np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)

	# data acquisition

	def apply_parameters(self):
		"""Apply the current parameters and decide whether to keep previous data."""
		frequency = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)

		if not self.keep_data or np.any(frequency != self.frequency):
			self.frequency = frequency
			self.run_time = 0.0

		self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.

	def _run(self):
				
		try:
			self.state = 'run'
			self.apply_parameters()


			n = len(self.frequency)
			ha.Microwave().setPower(self.power)
			for i in range(n):
				ha.Microwave().setFrequency(self.frequency[i])
				ha.PulseGenerator().Sequence([ (['mw_2', 'laser'], self.trigger_delay), (['laser', 'mw'], self.exposure*10**3) ], loop=False) #the delay of random trigger is unknown
			time.sleep(0.5)

	
			self.state = 'done'
			ha.Microwave().setOutput(None, self.frequency_begin)
			ha.PulseGenerator().Light()
		except:
			logging.getLogger().exception('Error in odmr.')
			self.state = 'error'
		finally:
			ha.Microwave().setOutput(None, self.frequency_begin)

	def _update_freq_length(self):
		self.apply_parameters()
		self.freq_length = len(self.frequency)
		
	# saving data
	
	def save_line_plot(self, filename):
		self.save_figure(self.line_plot, filename)

	def save_matrix_plot(self, filename):
		self.save_figure(self.matrix_plot, filename)
	
	def save_all(self, filename):
		self.save_line_plot(filename + '_ODMR_Line_Plot.png')
		self.save_matrix_plot(filename + '_ODMR_Matrix_Plot.png')
		self.save(filename + '_ODMR.pys')

	# react to GUI events

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

	traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
									 Item('remove_button', show_label=False),
									 Item('resubmit_button', show_label=False),
									 Item('priority', enabled_when='state != "run"'),
									 Item('state', style='readonly'),
									 Item('run_time', style='readonly', format_str='%.f'),
									 Item('freq_length', style='readonly', format_str='%.f'),
									 ),
							  VGroup(HGroup(Item('power', enabled_when='state != "run"'),
											Item('frequency_begin', enabled_when='state != "run"'),
											Item('frequency_end', enabled_when='state != "run"'),
											Item('frequency_delta', enabled_when='state != "run"'),
											),
									 HGroup(Item('exposure', enabled_when='state != "run"'),
											Item('trigger_delay', enabled_when='state != "run"'),
											),
									 ),
							  ),
					   menubar=MenuBar(Menu(Action(action='saveLinePlot', name='SaveLinePlot (.png)'),
											  Action(action='saveMatrixPlot', name='SaveMatrixPlot (.png)'),
											  Action(action='save', name='Save (.pyd or .pys)'),
											  Action(action='saveAll', name='Save All (.png+.pys)'),
											  Action(action='export', name='Export as Ascii (.asc)'),
											  Action(action='load', name='Load'),
											  Action(action='_on_close', name='Quit'),
											  name='File')),
					   title='gatedODMR', width=900, height=800, buttons=[], resizable=True, handler=ODMRHandler
					   )

	get_set_items = ['frequency', 'run_time',
					 'power', 'frequency_begin', 'frequency_end', 'frequency_delta',
					 'exposure', 'trigger_delay',
					 '__doc__']

					 
if __name__ == '__main__':

	logging.getLogger().addHandler(logging.StreamHandler())
	logging.getLogger().setLevel(logging.DEBUG)
	logging.getLogger().info('Starting logger.')

	from tools.emod import JobManager
	JobManager().start()

	o = gatedODMR()
	o.edit_traits()
	
	
