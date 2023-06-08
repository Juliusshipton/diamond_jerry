import sys
import PIL.Image
sys.modules['Image'] = PIL.Image

import numpy as np
import random
import cPickle
from pypylon import pylon as py
from grab_ccd import *#grab_ccd_triggered, grab_ccd_triggered2, grab_ccd_fast, grab_ccd_multiple, grab_ccd_multipleSing,grab_ccd_multiple_ref 

# import matplotlib.pyplot as plt
from traits.api import SingletonHasTraits, Trait, Instance, Property, String, Range, Float, Int, Bool, Array, Enum, Button, on_trait_change, cached_property, Code, List, NO_COMPARE, Str
from traitsui.api import View, Item, HGroup, VGroup, VSplit, Tabbed, EnumEditor, TextEditor, Group
from enable.api import Component, ComponentEditor
from chaco.api import ArrayPlotData, Plot, Spectral, PlotLabel, jet, CMapImagePlot, HPlotContainer
from chaco.tools.cursor_tool import CursorTool2D
#customized zoom tool to keep aspect ratio
from tools.utility import AspectZoomTool

from traitsui.file_dialog import save_file, open_file
from traitsui.menu import Action, Menu, MenuBar

import time
import threading
import logging

from tools.emod import ManagedJob
from tools.cron import CronDaemon, CronEvent

import hardware.api as ha

from analysis import fitting

from tools.utility import GetSetItemsHandler, GetSetItemsMixin


class CCDODMRHandler(GetSetItemsHandler):

	def saveLinePlot(self, info):
		filename = save_file(title='Save Line Plot')
		if filename is '':
			return
		else:
			if filename.find('.png') == -1:
				filename = filename + '.png'
			info.object.save_line_plot(filename)

	def saveCCDPlot(self, info):
		filename = save_file(title='Save CCD Plot')
		if filename is '':
			return
		else:
			if filename.find('.png') == -1:
				filename = filename + '.png'
			info.object.save_ccd_plot(filename)
			
	def saveSumLinePlot(self, info):
		filename = save_file(title='Save Sum Line Plot')
		if filename is '':
			return
		else:
			if filename.find('.png') == -1:
				filename = filename + '.png'
			info.object.save_sum_line_plot(filename)
			
	def saveAll(self, info):
		filename = save_file(title='Save All')
		if filename is '':
			return
		else:
			info.object.save_all(filename)
	#'''starts here'''		  
	def loadcomp(self, info):
		filename = open_file(title='Load Comparison')
		if filename is '':
			return
		else:
			info.object.load_comp(filename)
	#'''ends here'''


class CCDODMR_test3(ManagedJob, GetSetItemsMixin):
	"""Provides ODMR measurements."""
	'''
	goals: movable cursor which can provide the current index of the point it is pointing to.
			An image plot for ccd and a line plot of ODMR for a selected pixel point
	'''
	
	# starting and stopping
	keep_data = Bool(False) # helper variable to decide whether to keep existing data
	resubmit_button = Button(label='resubmit', desc='Submits the measurement to the job manager. Tries to keep previously acquired data. Behaves like a normal submit if sequence or time bins have changed since previous run.')	 
	
	# measurement parameters
	power = Range(low= -100., high=25., value= -10, desc='Power [dBm]', label='Power [dBm]', mode='text', auto_set=False, enter_set=True)
	frequency_begin = Range(low=1, high=20e9, value=2.85e9, desc='Start Frequency [Hz]', label='Begin [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	frequency_end = Range(low=1, high=20e9, value=2.90e9, desc='Stop Frequency [Hz]', label='End [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	frequency_delta = Range(low=1e-3, high=20e9, value=1e6, desc='frequency step [Hz]', label='Delta [Hz]', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	laser = Range(low=1., high=10000., value=300., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
	wait = Range(low=1., high=10000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
	seconds_per_point = Range(low=1e-6, high=1, value=10e-3, desc='Seconds per point', label='Seconds per point', mode='text', auto_set=False, enter_set=True)
	stop_time = Range(low=1., value=np.inf, desc='Time after which the experiment stops by itself [s]', label='Stop time [s]', mode='text', auto_set=False, enter_set=True)
	stop_reps = Range(low=1., value=100000000, desc='Reps after which the experiment stops by itself', label='total reps', mode='text', auto_set=False, enter_set=True)
	# control data fitting
	perform_fit = Bool(False, label='perform fit')
	number_of_resonances = Trait('auto', String('auto', auto_set=False, enter_set=True), Int(10000., desc='Number of Lorentzians used in fit', label='N', auto_set=False, enter_set=True))
	threshold = Range(low= -99, high=99., value= -50., desc='Threshold for detection of resonances [%]. The sign of the threshold specifies whether the resonances are negative or positive.', label='threshold [%]', mode='text', auto_set=False, enter_set=True)
	perform_sum_fit = Bool(False, label='perform sum fit')
	
	
	# fit result
	fit_parameters = Array(value=np.array((np.nan, np.nan, np.nan, np.nan)))
	fit_frequencies = Array(value=np.array((np.nan,)), label='frequency [Hz]') 
	fit_line_width = Array(value=np.array((np.nan,)), label='line_width [Hz]') 
	fit_contrast = Array(value=np.array((np.nan,)), label='contrast [%]')

	sum_fit_parameters = Array(value=np.array((np.nan, np.nan, np.nan, np.nan)))
	sum_fit_frequencies = Array(value=np.array((np.nan,)), label='frequency [Hz]') 
	sum_fit_line_width = Array(value=np.array((np.nan,)), label='line_width [Hz]') 
	sum_fit_contrast = Array(value=np.array((np.nan,)), label='contrast [%]')

	#ccd control
	ccd_single_shot = Button(label='single')
	ccd_con_shot = Button(label='continuous')
	switch = Enum('Mono12','Mono8', desc='pixel format', label='pixel format', editor=EnumEditor(cols=3, values={'Mono12':'12 bits','Mono8':'8 bits'}))
	switchTri = Enum('RisingEdge','TriggerWidth', 'multiple', desc='pixel format', label='pixel format', editor=EnumEditor(cols=3, values={'RisingEdge':'fast edge','TriggerWidth':'trigger width', 'multiple':'multiple picture'}))
	switchBin = Enum(1,2,3,4, desc='binning', label='binning', editor=EnumEditor(cols=3, values={1:'1 bin',2:'2 bin',3:'3 bin',4:'4 bin'}))


	tlf = py.TlFactory.GetInstance()
	devices = tlf.EnumerateDevices()
	# the active camera will be an InstantCamera based on a device created with the corresponding DeviceInfo
	#to open the camera need to tell transport layer to create a device
	cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
	
	exposure = Range(low= 20, high=10000000, value= 3000, desc='ccd exposure [us]', label='ccd exposure [us]', mode='text', auto_set=False, enter_set=True)
	ccdwait = Range(low= 5, high=10000000, value= 50, desc='ccd wait [us]', label='ccd wait [us]', mode='text', auto_set=False, enter_set=True)
	nacc = Range(low= 1, high=50, value= 10, desc='no. of image accquire', label='no. of accquisition', mode='text', auto_set=False, enter_set=True)
	x_pixel = 1920
	x_min_pixel = 0
	y_pixel = 1200
	y_min_pixel = 0
	x1 = Range(low=0, high=1920, value=x_min_pixel, desc='x1 [micron]', label='x1', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
	y1 = Range(low=0, high=1200, value=y_min_pixel, desc='y1 [micron]', label='y1', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
	x2 = Range(low=1, high=1920, value=x_pixel, desc='x2 [micron]', label='x2', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
	y2 = Range(low=1, high=1200, value=y_pixel, desc='y2 [micron]', label='y2', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
	ccdwidth = Range(low=4, high=1920, value=x_pixel-x_min_pixel, desc='ccdwidth', label='ccdwidth', editor=TextEditor(auto_set=False, enter_set=True, evaluate=int))
	ccdheight = Range(low=0, high=1200, value=y_pixel-y_min_pixel, desc='ccdheight', label='ccdheight', editor=TextEditor(auto_set=False, enter_set=True, evaluate=int))
	ccdxoff = Range(low=0, high=1920, value=0, desc='ccdxoff', label='ccdxoff', editor=TextEditor(auto_set=False, enter_set=True, evaluate=int))
	ccdyoff = Range(low=0, high=1200, value=0, desc='ccdyoff', label='ccdyoff', editor=TextEditor(auto_set=False, enter_set=True, evaluate=int))
	# measurement data	  
	frequency = Array()
	counts_ccd = Array()
	counts_ccd_data = Array()
	counts_ccd_line = Array()
	run_time = Float(value=0.0, desc='Run time [s]', label='Run time [s]')
	repetitions = Int(value=0, desc='number of repetitions', label='no. of reps')
		
	# plotting
	line_label = Instance(PlotLabel)
	line_data = Instance(ArrayPlotData)
	matrix_data = Instance(ArrayPlotData)
	line_plot = Instance(Plot, editor=ComponentEditor())
	ccd_plot = Instance(Plot, editor=ComponentEditor())
	scan_plot = Instance( CMapImagePlot )
	thresh_high = Trait( 'auto', Str('auto'), Float(10000.), desc='High Limit of image plot', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
	thresh_low = Trait( 'auto', Str('auto'), Float(0.), desc='Low Limit of image plot', editor=TextEditor(auto_set=False, enter_set=True, evaluate=float))
	colormaps = Enum('jet')
	figure_container = Instance( HPlotContainer, editor=ComponentEditor() )

	# summing
	perform_sum = Bool(False, label='perform sum')
	x_sum=Range(low=1., high=1920., value=x_pixel, desc='x sum', label='x sum', mode='text', auto_set=False, enter_set=True)
	x_min_sum=Range(low=0, high=1920, value=x_min_pixel, desc='x min sum', label='x min sum', mode='text', auto_set=False, enter_set=True)
	y_sum=Range(low=1, high=1200, value=y_pixel, desc='y sum', label='y sum', mode='text', auto_set=False, enter_set=True)
	y_min_sum=Range(low=0, high=1200., value=y_min_pixel, desc='y min sum', label='y min sum', mode='text', auto_set=False, enter_set=True)
	sum_counts=Array()
	sum_line_data = Instance(ArrayPlotData)
	sum_line_plot = Instance(Plot, editor=ComponentEditor())
	
	# scanner position
	y = Range(low=y_min_pixel, high=y_pixel, value=int((y_pixel+y_min_pixel)/2), desc='y [Pixel]', label='y [Pixel]', mode='slider')
	x = Range(low=x_min_pixel, high=x_pixel, value=int((x_pixel+x_min_pixel)/2), desc='x [Pixel]', label='x [Pixel]', mode='slider')
	cursor = Instance( CursorTool2D )
	cursor_position = Property(depends_on=['x','y'])#,'z','constant_axis'])
	
	
	def __init__(self):
		super(CCDODMR_test3, self).__init__()
		self._create_ccd_plot()
		self._create_line_plot()
		self._create_sum_line_plot()
		self.sync_trait('cursor_position', self.cursor, 'current_position')
		self.sync_trait('x_min_pixel', self, 'x1')
		self.sync_trait('x_pixel', self, 'x2')
		self.sync_trait('y_min_pixel', self, 'y1')
		self.sync_trait('y_pixel', self, 'y2')
		self.sync_trait('thresh_high', self.scan_plot.value_range, 'high_setting')
		self.sync_trait('thresh_low', self.scan_plot.value_range, 'low_setting')
		self.ccd_plot.index_range.on_trait_change(self.update_axis_li, '_low_value', dispatch='ui')
		self.ccd_plot.index_range.on_trait_change(self.update_axis_hi, '_high_value', dispatch='ui')
		self.ccd_plot.value_range.on_trait_change(self.update_axis_lv, '_low_value', dispatch='ui')
		self.ccd_plot.value_range.on_trait_change(self.update_axis_hv, '_high_value', dispatch='ui')
		self.zoom.on_trait_change(self.check_zoom, 'box', dispatch='ui')
		self.on_trait_change(self.set_mesh_and_aspect_ratio, 'x1,x2,y1,y2', dispatch='ui')
		self.on_trait_change(self.scan_plot.request_redraw, 'thresh_high,thresh_low', dispatch='ui')
		self.on_trait_change(self._update_line_data_index, 'frequency', dispatch='ui')
		self.on_trait_change(self._update_line_data_value, 'counts_ccd_data,x,y', dispatch='ui')
		self.on_trait_change(self._update_line_data_fit, 'fit_parameters', dispatch='ui')
		self.on_trait_change(self._update_sum_line_data_index, 'frequency', dispatch='ui')
		self.on_trait_change(self._update_sum_line_data_value, 'counts_ccd_data,x_min_sum,x_sum,y_min_sum,y_sum', dispatch='ui')
		self.on_trait_change(self._update_sum_line_data_fit, 'sum_fit_parameters', dispatch='ui')
		self.on_trait_change(self._update_ccd_data_value, 'counts_ccd', dispatch='ui')
		self.on_trait_change(self._update_fit, 'counts_ccd_data,counts_ccd_line,x,y,perform_fit,number_of_resonances,threshold', dispatch='ui')
		self.on_trait_change(self._update_sum_fit, 'counts_ccd_data,counts_ccd_line,perform_sum_fit,number_of_resonances,threshold', dispatch='ui')
		self.on_trait_change(self._update_sum, 'x_min_sum,x_sum,y_min_sum,y_sum', dispatch='ui')		
		self.on_trait_change(self._update_ROI, 'ccdxoff,ccdyoff,ccdheight,ccdwidth', dispatch='ui')		

	@cached_property
	def _get_cursor_position(self): #update the cursor when moving x/y
		return self.x, self.y
	
	def _set_cursor_position(self, position): #update x/y when moving cursor
		self.x, self.y = (int(position[0]),int(position[1]))
			
	def _frequency_default(self):
		freq = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)
		return freq
			
	def _counts_ccd_default(self):
		return np.zeros((self.y_pixel-self.y_min_pixel,self.x_pixel-self.x_min_pixel))
	
	def _counts_ccd_data_default(self):
		return np.zeros((1, self.y_pixel-self.y_min_pixel,self.x_pixel-self.x_min_pixel))
	
	def _counts_default(self):
		return np.zeros(self.frequency.shape)
		
	def _counts_ccd_line_default(self):
		return np.zeros(self.frequency.shape)
		
	def _sum_counts_default(self):
		return np.zeros(self.frequency.shape)
	# data acquisition				  
		
	def apply_parameters(self):
		"""Apply the current parameters and decide whether to keep previous data."""
		frequency = np.arange(self.frequency_begin, self.frequency_end + self.frequency_delta, self.frequency_delta)
		if not self.keep_data or np.any(frequency != self.frequency):
			self.frequency = frequency
			self.sum_counts = np.zeros(frequency.shape)
			self.counts_ccd_data = np.zeros(shape=(len(self.frequency), self.y_pixel-self.y_min_pixel,self.x_pixel-self.x_min_pixel))#original:1200x1920
			self.run_time = 0.0
			self.repetitions = 0
		self.keep_data = True # when job manager stops and starts the job, data should be kept. Only new submission should clear data.

	def _run(self):
		try:
			self.state = 'run'
			self.apply_parameters()

			if self.run_time >= self.stop_time or self.repetitions>=self.stop_reps:
				self.state = 'done'
				return
			
				
			n = len(self.frequency)
			time.sleep(0.5)
			self.cam.Open()

			self.cam.AcquisitionMode.SetValue('SingleFrame')
			self.cam.ExposureAuto.SetValue('Off')
			self.cam.TriggerSelector.SetValue('FrameStart')	   
			self.cam.TriggerMode.SetValue("On")
			self.cam.TriggerSource.SetValue("Line1")
			self.cam.TriggerActivation.SetValue('RisingEdge')
			self.cam.PixelFormat.SetValue(self.switch)
			self.cam.BinningVertical = self.switchBin
			self.cam.BinningHorizontal = self.switchBin

			if self.switchTri == 'RisingEdge' or self.switchTri == 'multiple':
				self.cam.ExposureMode.SetValue('Timed')
				self.cam.ExposureTime = self.exposure
			else:
				self.cam.ExposureMode.SetValue('TriggerWidth')	  
			
			
			ha.PulseGenerator().Night()
			# self.counts_ccd = grab_ccd_triggered2(self.cam, self.exposure, self.ccdwait)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]
			counts_ccd = np.zeros((n,self.y_pixel-self.y_min_pixel,self.x_pixel-self.x_min_pixel)) #original:1200x1920
			ha.PulseGenerator().Night()
			
			ha.Microwave().setPower(self.power)
			if self.switchTri == 'RisingEdge':
				while (self.run_time < self.stop_time and self.repetitions < int(self.stop_reps)):
					start_time = time.time()
					for i in range(n):
						ha.Microwave().setFrequency(self.frequency[i]) #jitter of 0.5ms
						counts_ccd[i] = grab_ccd_fast(self.cam, self.exposure, self.ccdwait)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]#+np.random.normal(127, 9, size=(1200, 1920))#self.laser, self.exposure, self.wait)
						if threading.currentThread().stop_request.isSet():
							break
					if threading.currentThread().stop_request.isSet():
						break
					self.counts_ccd_data += counts_ccd
					self.sum_counts+=np.sum(np.sum(counts_ccd[:,int(self.y_min_sum)-self.y_min_pixel:int(self.y_sum)-self.y_min_pixel,int(self.x_min_sum)-self.x_min_pixel:int(self.x_sum)-self.x_min_pixel],axis=1),axis=1)		
					self.trait_property_changed('counts_ccd_data', self.counts_ccd_data)
					self.run_time += time.time() - start_time
					self.repetitions += 1
			elif self.switchTri == 'multiple':
				self.cam.AcquisitionMode.SetValue('Continuous')
				while (self.run_time < self.stop_time and self.repetitions < int(self.stop_reps)):
					start_time = time.time()
					for i in range(n):
						ha.Microwave().setFrequency(self.frequency[i]) #jitter of 0.5ms
						counts_ccd[i] = grab_ccd_multiple_ref(self.cam, self.exposure, self.ccdwait, self.nacc)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]#+np.random.normal(127, 9, size=(1200, 1920))#self.laser, self.exposure, self.wait)
						if threading.currentThread().stop_request.isSet():
							break
					if threading.currentThread().stop_request.isSet():
						break
					self.counts_ccd_data += counts_ccd
					self.sum_counts+=np.sum(np.sum(counts_ccd[:,int(self.y_min_sum)-self.y_min_pixel:int(self.y_sum)-self.y_min_pixel,int(self.x_min_sum)-self.x_min_pixel:int(self.x_sum)-self.x_min_pixel],axis=1),axis=1)		
					self.trait_property_changed('counts_ccd_data', self.counts_ccd_data)
					self.run_time += time.time() - start_time
					self.repetitions += 1
			else:
				while (self.run_time < self.stop_time and self.repetitions < int(self.stop_reps)):
					start_time = time.time()
					for i in range(n):
						ha.Microwave().setFrequency(self.frequency[i]) #jitter of 0.5ms
						counts_ccd[i] = grab_ccd_triggered2(self.cam, self.exposure, self.ccdwait)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]#+np.random.normal(127, 9, size=(1200, 1920))#self.laser, self.exposure, self.wait)
						if threading.currentThread().stop_request.isSet():
							break
					if threading.currentThread().stop_request.isSet():
						break
					# self.sum_counts+=np.sum(np.sum(counts_ccd[:,int(self.y_min_sum)-self.y_min_pixel:int(self.y_sum)-self.y_min_pixel,int(self.x_min_sum)-self.x_min_pixel:int(self.x_sum)-self.x_min_pixel],axis=1),axis=1)		
					self.counts_ccd_data += counts_ccd
					self.trait_property_changed('counts_ccd_data', self.counts_ccd_data)
					self.run_time += time.time() - start_time
					self.repetitions += 1

			self.cam.Close()
			if self.run_time < self.stop_time and self.repetitions < int(self.stop_reps):
				self.state = 'idle'
			else:
				self.state = 'done'

			ha.Microwave().setOutput(None, self.frequency_begin)
			ha.PulseGenerator().Light()
		except:
			self.cam.Close()
			logging.getLogger().exception('Error in ccdodmr.')
			self.state = 'error'
		finally:
			ha.Microwave().setOutput(None, self.frequency_begin)

	def _update_fit(self):
		if self.perform_fit:
			N = self.number_of_resonances 
			if N != 'auto':
				N = int(N)
			try:
				p = fitting.fit_multiple_lorentzians(self.frequency, self.line_data['counts_ccd_line'], N, threshold=self.threshold * 0.01)
			except Exception:
				logging.getLogger().debug('ODMR fit failed.', exc_info=True)
				p = np.nan * np.empty(4)
		else:
			p = np.nan * np.empty(4)

		self.fit_parameters = p
		self.fit_frequencies = p[1::3]
		self.fit_line_width = p[2::3]
		N = len(p) / 3
		contrast = np.empty(N)
		c = p[0]
		pp = p[1:].reshape((N, 3))
		for i, pi in enumerate(pp):
			a = pi[2]
			g = pi[1]
			A = np.abs(a / (np.pi * g))
			if a > 0:
				contrast[i] = 100 * A / (A + c)
			else:
				contrast[i] = 100 * A / c
		self.fit_contrast = contrast
		
	def _update_sum_fit(self):
		if self.perform_sum_fit:
			N = self.number_of_resonances 
			if N != 'auto':
				N = int(N)
			try:
				p_sum = fitting.fit_multiple_lorentzians(self.frequency, self.sum_line_data['sum_counts'], N, threshold=self.threshold * 0.01)
			except Exception:
				logging.getLogger().debug('CCDODMR sum fit failed.', exc_info=True)
				p_sum = np.nan * np.empty(4)
		else:
			p_sum = np.nan * np.empty(4)
		self.sum_fit_parameters = p_sum
		self.sum_fit_frequencies = p_sum[1::3]
		self.sum_fit_line_width = p_sum[2::3]
		N = len(p_sum) / 3
		contrast = np.empty(N)
		c = p_sum[0]
		pp_sum = p_sum[1:].reshape((N, 3))
		for i, pi in enumerate(pp_sum):
			a = pi[2]
			g = pi[1]
			A = np.abs(a / (np.pi * g))
			if a > 0:
				contrast[i] = 100 * A / (A + c)
			else:
				contrast[i] = 100 * A / c
		self.sum_fit_contrast = contrast

	#plotting
		
	def _create_line_plot(self):
		line_data = ArrayPlotData(frequency=np.array((0., 1.)), counts_ccd_line=np.array((0., 0.)), fit=np.array((0., 0.))) 
		line_plot = Plot(line_data, padding=8, padding_left=64, padding_bottom=32)
		line_plot.plot(('frequency', 'counts_ccd_line'), style='line', color='blue')
		line_plot.index_axis.title = 'Frequency [MHz]'
		line_plot.value_axis.title = 'Fluorescence counts'
		line_label = PlotLabel(text='', hjustify='left', vjustify='bottom', position=[64, 128])
		line_plot.overlays.append(line_label)
		self.line_label = line_label
		self.line_data = line_data
		self.line_plot = line_plot
				
	def _create_ccd_plot(self):
		ccd_data = ArrayPlotData(image=self.counts_ccd)#original:(1200,1920)
		ccd_plot = Plot(ccd_data, width=500, height=500, resizable='hv', aspect_ratio=1.6,padding=8, padding_left=64, padding_bottom=32)
		ccd_plot.img_plot('image',	colormap=jet, xbounds=(self.x_min_pixel,self.x_pixel), ybounds=(self.y_min_pixel,self.y_pixel), name='image')
		image = ccd_plot.plots['image'][0]
		image.x_mapper.domain_limits = (self.x_min_pixel,self.x_pixel)
		image.y_mapper.domain_limits = (self.y_min_pixel,self.y_pixel)
		zoom = AspectZoomTool(image, enable_wheel=False)
		cursor = CursorTool2D(image, drag_button='left', color='white', marker_size=1.0, line_width=1.0 )
		image.overlays.append(cursor)
		image.overlays.append(zoom)
		self.cursor = cursor
		self.zoom = zoom
		self.scan_plot = image
		self.ccd_data = ccd_data
		self.ccd_plot = ccd_plot
		# container = HPlotContainer()
		# container.add(ccd_plot)
		# self.figure_container = container
		
	def _create_sum_line_plot(self):
		sum_line_data = ArrayPlotData(frequency=np.array((0., 1.)), sum_counts=np.array((0., 0.)), sum_fit=np.array((0., 0.))) 
		sum_line_plot = Plot(sum_line_data, padding=8, padding_left=64, padding_bottom=32)
		sum_line_plot.plot(('frequency', 'sum_counts'), style='line', color='red', name='sum_plot')
		sum_line_plot.index_axis.title = 'Frequency [MHz]'
		sum_line_plot.value_axis.title = 'Fluorescence counts'
		sum_line_label = PlotLabel(text='', hjustify='left', vjustify='bottom', position=[64, 128])
		sum_line_plot.overlays.append(sum_line_label)
		self.sum_line_label = sum_line_label
		self.sum_line_data = sum_line_data
		self.sum_line_plot = sum_line_plot
	
	
	def _perform_fit_changed(self, new):
		plot = self.line_plot
		if new:
			plot.plot(('frequency', 'fit'), style='line', color='red', name='fit')
			self.line_label.visible = True
		else:
			plot.delplot('fit')
			self.line_label.visible = False
		plot.request_redraw()
	def _perform_sum_fit_changed(self, new):
		sum_plot = self.sum_line_plot
		if new:
			sum_plot.plot(('frequency', 'sum_fit'), style='line', line_style='dash', color='green', name='sum_fit')
			self.sum_line_label.visible = True
		else:
			sum_plot.delplot('sum_fit')
			self.sum_line_label.visible = False
		sum_plot.request_redraw()
	def _update_line_data_index(self):
		self.line_data.set_data('frequency', self.frequency * 1e-6)

	def _update_line_data_value(self):
		self.line_data.set_data('counts_ccd_line', self.counts_ccd_data[:,self.y-self.y_min_pixel,self.x-self.x_min_pixel])
	def _update_sum_line_data_index(self):
		self.sum_line_data.set_data('frequency', self.frequency * 1e-6)
	def _update_sum_line_data_value(self):
		# self.sum_counts=np.sum(np.sum(self.counts_ccd_data[:,int(self.y_min_sum)-self.y_min_pixel:int(self.y_sum)-self.y_min_pixel,int(self.x_min_sum)-self.x_min_pixel:int(self.x_sum)-self.x_min_pixel],axis=1),axis=1)		
		self.sum_line_data.set_data('sum_counts', self.sum_counts)
	
	def _update_line_data_fit(self):
		if not np.isnan(self.fit_parameters[0]):
			self.line_data.set_data('fit', fitting.NLorentzians(*self.fit_parameters)(self.frequency))
			p = self.fit_parameters
			f = p[1::3]
			w = p[2::3]
			N = len(p) / 3
			contrast = np.empty(N)
			c = p[0]
			pp = p[1:].reshape((N, 3))
			for i, pi in enumerate(pp):
				a = pi[2]
				g = pi[1]
				A = np.abs(a / (np.pi * g))
				if a > 0:
					contrast[i] = 100 * A / (A + c)
				else:
					contrast[i] = 100 * A / c
			s = ''
			for i, fi in enumerate(f):
				s += 'f %i: %.6e Hz, FWHM %.3e Hz, contrast %.1f%%\n' % (i + 1, fi, w[i]*2, contrast[i])
			self.line_label.text = s
	
	def _update_sum_line_data_fit(self):
		if not np.isnan(self.sum_fit_parameters[0]):
			self.sum_line_data.set_data('sum_fit', fitting.NLorentzians(*self.sum_fit_parameters)(self.frequency))
			p = self.sum_fit_parameters
			f = p[1::3]
			w = p[2::3]
			N = len(p) / 3
			contrast = np.empty(N)
			c = p[0]
			pp = p[1:].reshape((N, 3))
			for i, pi in enumerate(pp):
				a = pi[2]
				g = pi[1]
				A = np.abs(a / (np.pi * g))
				if a > 0:
					contrast[i] = 100 * A / (A + c)
				else:
					contrast[i] = 100 * A / c
			s = ''
			for i, fi in enumerate(f):
				s += 'f %i: %.6e Hz, FWHM %.3e Hz, contrast %.1f%%\n' % (i + 1, fi, w[i]*2, contrast[i])
			self.sum_line_label.text = s

	def _update_ccd_data_value(self):
		self.ccd_data.set_data('image', self.counts_ccd)

	
	def update_axis_li(self):
		self.x1 = int(self.ccd_plot.index_range.low)
	def update_axis_hi(self):
		self.x2 = int(self.ccd_plot.index_range.high)
	def update_axis_lv(self):
		self.y1 = int(self.ccd_plot.value_range.low) 
	def update_axis_hv(self):
		self.y2 = int(self.ccd_plot.value_range.high)
		
	def set_mesh_and_aspect_ratio(self):
		x1 = self.x1
		x2 = self.x2
		y1 = self.y1
		y2 = self.y2
		self.ccd_plot.aspect_ratio = (x2-x1) / float((y2-y1))
		self.ccd_plot.index_range.low = x1
		self.ccd_plot.index_range.high = x2
		self.ccd_plot.value_range.low = y1
		self.ccd_plot.value_range.high = y2
		self.x = int((x1+x2)/2)
		self.y = int((y1+y2)/2)
	
	def check_zoom(self, box):
		li,lv,hi,hv=box
		self.x = int((li+hi)/2)
		self.y = int((lv+hv)/2)
	# saving data
	
	def save_line_plot(self, filename):
		self.save_figure(self.line_plot, filename)

	def save_sum_line_plot(self, filename):
		self.save_figure(self.sum_line_plot, filename)
		
	def save_ccd_plot(self, filename):
		self.save_figure(self.ccd_plot, filename)
	
	def save_all(self, filename):
		self.save(filename + '_CCDODMR.pys')
		self.save_line_plot(filename + '_CCDODMR_Line_Plot.png')
		self.save_ccd_plot(filename + '_CCDODMR_Matrix_Plot.png')

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
		
	def _ccd_single_shot_fired(self):
		self.ccd_single()
		
	def ccd_single(self):
		self.cam.Open()
		self.cam.ExposureAuto.SetValue('Off')
		self.cam.TriggerSelector.SetValue('FrameStart')	   
		self.cam.TriggerMode.SetValue("On")
		self.cam.TriggerSource.SetValue("Line1")
		self.cam.TriggerActivation.SetValue('RisingEdge')
		self.cam.PixelFormat.SetValue(self.switch)
		self.cam.BinningVertical = self.switchBin
		self.cam.BinningHorizontal = self.switchBin
		
		if self.switchTri == 'RisingEdge':
			self.cam.AcquisitionMode.SetValue('SingleFrame')
			self.cam.ExposureMode.SetValue('Timed')
			self.cam.ExposureTime = self.exposure
			self.counts_ccd = grab_ccd_fast(self.cam, self.exposure, self.wait)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]			
		elif self.switchTri == 'multiple':
			self.cam.AcquisitionMode.SetValue('Continuous')
			self.cam.ExposureMode.SetValue('Timed')
			self.cam.ExposureTime = self.exposure
			self.counts_ccd = grab_ccd_multipleSing(self.cam, self.exposure, self.ccdwait, self.nacc)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]#+np.random.normal(127, 9, size=(1200, 1920))#self.laser, self.exposure, self.wait)
		else:
			self.cam.AcquisitionMode.SetValue('SingleFrame')
			self.cam.ExposureMode.SetValue('TriggerWidth')
			self.counts_ccd = grab_ccd_triggered2(self.cam, self.exposure, self.wait)[self.y_min_pixel:self.y_pixel,self.x_min_pixel:self.x_pixel]			  
		self.cam.Close()
		return
		
	def _update_ROI(self):
		self.cam.Open()
		self.cam.Width.SetValue(int(self.ccdwidth/4)*4)
		self.cam.Height.SetValue(int(self.ccdheight))
		self.cam.OffsetX.SetValue(int(self.ccdxoff/4)*4)
		self.cam.OffsetY.SetValue(int(self.ccdyoff/2)*2)
		self.ccdwidth=self.cam.Width.GetValue()
		self.ccdheight=self.cam.Height.GetValue()
		self.cam.Close()
		self.x2 = int(self.ccdwidth/4)*4
		self.x1 = 0
		self.y2 = int(self.ccdheight)
		self.y1 = 0
		self.scan_plot.index.set_data(np.arange(self.ccdwidth+1),np.arange(self.ccdheight+1))
		return
	
	def _switchBin_changed(self):
		self.x2 = 1920/self.switchBin
		self.x1 = 0
		self.y2 = 1200/self.switchBin
		self.y1 = 0
		self.scan_plot.index.set_data(np.arange(self.x2+1),np.arange(self.y2+1))
		return
	
	def _perform_sum_changed(self, new):
		self._update_sum()
		plot = self.ccd_plot
		if new:
			plot.plot(('x_range_sum', 'y_min_sum'), style='line', color='red', name='y_min_sum')
			plot.plot(('x_range_sum', 'y_sum'), style='line', color='red', name='y_sum')
			plot.plot(('x_min_sum','y_range_sum'), style='line', color='red', name='x_min_sum')
			plot.plot(('x_sum','y_range_sum'), style='line', color='red', name='x_sum')
		else:
			plot.delplot('y_min_sum')
			plot.delplot('y_sum')
			plot.delplot('x_min_sum')
			plot.delplot('x_sum')
		plot.request_redraw()
		return
		
	def _update_sum(self):
		self.ccd_data.set_data('x_range_sum', np.arange(int(self.x2-self.x1)))	  
		self.ccd_data.set_data('y_range_sum', np.arange(int(self.y2-self.y1)))	
		self.ccd_data.set_data('x_sum', np.ones(int(self.y2-self.y1))*self.x_sum)		
		self.ccd_data.set_data('x_min_sum', np.ones(int(self.y2-self.y1))*self.x_min_sum)		
		self.ccd_data.set_data('y_min_sum', np.ones(int(self.x2-self.x1))*self.y_min_sum)		
		self.ccd_data.set_data('y_sum', np.ones(int(self.x2-self.x1))*self.y_sum)	
		# self.sum_counts=np.sum(np.sum(self.counts_ccd_data[:,int(self.y_min_sum)-self.y_min_pixel:int(self.y_sum)-self.y_min_pixel,int(self.x_min_sum)-self.x_min_pixel:int(self.x_sum)-self.x_min_pixel],axis=1),axis=1)		
		# if self.perform_sum:
			# self.sum_line_data.set_data('sum_counts',self.sum_counts)
		return

	traits_view = View(VSplit(HGroup(Item('submit_button',show_label=False),
									 Item('remove_button', show_label=False),
									 Item('resubmit_button', show_label=False),
									 Item('ccd_single_shot', show_label=False),
									 Item('priority', enabled_when='state != "run"'),
									 Item('state', style='readonly'),
									 Item('repetitions', style='readonly'),
									 Item('stop_reps'),
									 Item('run_time', style='readonly', format_str='%.f'),
									 Item('stop_time'),
									 ),
							  Tabbed(VGroup(HGroup(Item('power', width= -40, enabled_when='state != "run"'),
											Item('frequency_begin', width= -80, enabled_when='state != "run"'),
											Item('frequency_end', width= -80, enabled_when='state != "run"'),
											Item('frequency_delta', width= -80, enabled_when='state != "run"'),
											Item('seconds_per_point', width= -80, enabled_when='state != "run"'),
											),
									 HGroup(Item('perform_fit'),
											Item('perform_sum_fit'),
											Item('number_of_resonances', width= -60),
											Item('threshold', width= -60),
											),
									 label='ODMR control'
									 ),
									  VGroup(HGroup(Item('thresh_low', width=-80),
											 Item('thresh_high', width=-80),
											 Item('x1', width=-60,enabled_when='state != "run"'),
											 Item('x2', width=-60,enabled_when='state != "run"'),
											 Item('y1', width=-60,enabled_when='state != "run"'),
											 Item('y2', width=-60,enabled_when='state != "run"'),
											),
									 HGroup(Item('exposure', width=-80),
											Item('ccdwait', width=-80),
											Item('nacc', width=-80),
											Item('ccdheight', width=-80),
											Item('ccdwidth', width=-80),
											Item('ccdxoff', width=-80),
											Item('ccdyoff', width=-80),
											),
											HGroup(Item('perform_sum'),
											Item('x_sum', width=-80),
											Item('x_min_sum', width=-80),
											Item('y_sum', width=-80),
											Item('y_min_sum', width=-80),											 
											),
											HGroup(Item('switch', style='custom', enabled_when='state != "run"'),
											Item('switchTri', style='custom', enabled_when='state != "run"'),	
											Item('switchBin', style='custom', enabled_when='state != "run"'),	
											),
											 label='CCD control'
											 ),
									 ),
									HGroup(Item('ccd_plot', show_label=False, resizable=True),
									Item('line_plot', show_label=False, resizable=True),
									),
									Item('sum_line_plot', show_label=False, resizable=True),
							  VGroup(Item('x', enabled_when='state != "run" or (state == "run" and constant_axis == "x")'),
							  Item('y', enabled_when='state != "run" or (state == "run" and constant_axis == "y")'),
							  ),
							  ),
							 menubar=MenuBar(Menu(Action(action='saveLinePlot', name='SaveLinePlot (.png)'),
											  Action(action='saveCCDPlot', name='SaveCCDPlot (.png)'),
											  Action(action='saveSumLinePlot', name='SaveSumLinePlot (.png)'),
											  Action(action='save', name='Save (.pyd or .pys)'),
											  Action(action='saveAll', name='Save All (.png+.pys)'),
											  Action(action='export', name='Export as Ascii (.asc)'),
											  Action(action='load', name='Load'),
											  Action(action='_on_close', name='Quit'),
											  name='File')),
					   title='CCD ODMR test v3', width=900, height=500, buttons=[], resizable=True, handler=CCDODMRHandler
					   )

	get_set_items = ['frequency', 'counts_ccd', 'counts_ccd_data','x1','x2','y1','y2','thresh_high','thresh_low','exposure','ccdwait',
					 'run_time','perform_fit','repetitions','stop_reps','switch','switchTri','switchBin','sum_counts',
					 'ccdwidth', 'ccdheight','ccdxoff','ccdyoff','perform_sum_fit','x_sum','y_sum','x_min_sum','y_min_sum','perform_sum',
					 'fit_parameters', 'fit_contrast', 'fit_line_width', 'fit_frequencies',
					 'sum_fit_parameters', 'sum_fit_contrast', 'sum_fit_line_width', 'sum_fit_frequencies',
					 'power', 'frequency_begin', 'frequency_end', 'frequency_delta',
					'laser', 'wait', 'seconds_per_point',
					 'number_of_resonances', 'threshold',
					  'stop_time', 
					 '__doc__']


if __name__ == '__main__':

	logging.getLogger().addHandler(logging.StreamHandler())
	logging.getLogger().setLevel(logging.DEBUG)
	logging.getLogger().info('Starting logger.')

	from tools.emod import JobManager
	JobManager().start()

	o = CCDODMR_test3()
	o.edit_traits()
	
	
