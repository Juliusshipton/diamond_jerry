class ionization(PulsedTau):
	laser = Range(low=1., high=100000., value=3000., desc='laser [ns]', label='laser [ns]', mode='text', auto_set=False, enter_set=True)
    wait = Range(low=0., high=100000., value=1000., desc='wait [ns]', label='wait [ns]', mode='text', auto_set=False, enter_set=True)
	
	MW_frequency=Range(low=1, high=20e9, value=2.8705e9, desc='frequency electron flip', label='frequency [Hz]', mode='text', auto_set=False, enter_set=True, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	MW_power=Range(low= -100., high=25., value= -20, desc='power for electron flip', label='power [dBm]', mode='text', auto_set=False, enter_set=True)
	
	RF_frequency=Range(low=1, high=20e9, value=2.8705e9, desc='frequency for nuclear flip', label='frequency [Hz]', mode='text', auto_set=False, enter_set=True, editor=TextEditor(auto_set=False, enter_set=True, evaluate=float, format_str='%e'))
	RF_power=Range(low= -100., high=25., value= -20, desc='power for nuclear flip', label='power [dBm]', mode='text', auto_set=False, enter_set=True)
	
	t_piMW=Range(low=0., high=100000., value=1000., desc='pi/2 pulse length (x)', label='Tpi for electron flip [ns]', mode='text', auto_set=False, enter_set=True)
	t_piRF=Range(low=0., high=100000., value=1000., desc='pi/2 pulse length (x)', label='Tpi for nuclear flip [ns]', mode='text', auto_set=False, enter_set=True)
	
	def start_up(self):
        PulseGenerator().Night()
        MicrowaveA().setOutput(self.MW_power, self.MW_frequency)
		MicrowaveB().setOutput(self.RF_power, self.RF_frequency)
		
    def shut_down(self):
        PulseGenerator().Light()
        MicrowaveB().setOutput(None, self.RF_frequency)
		MicrowaveA().setOutput(None, self.MW_frequency)
		
	def generate_sequence(self):
		laser = self.laser
        wait = self.wait
		t_piMW=self.t_piMW
		t_piRF=self.t_piRF
		sequence=[]
		sequence_i=[(['laser','aom'],laser),([],wait)]
		for t in tau:
			sequence+=[(['red'], t)]
			sequence+=[(['mw_B'], t_piRF)]
			sequence+=[(['mw_A'], t_piMW), (['laser','aom'],laser),  ([],wait)]
		sequence += [ (['sequence'], 100)  ]
		sequence =sequence_i+sequence
        return sequence
		
	get_set_items = PulsedTau.get_set_items + ['laser', 'wait', 'MW_frequency','MW_power', 't_piMW','RF_frequency','RF_power','t_piRF']
	traits_view = View(VGroup(HGroup(Item('submit_button', show_label=False),
                                     Item('remove_button', show_label=False),
                                     Item('resubmit_button', show_label=False),
                                     Item('priority'),
                                     Item('state', style='readonly'),
                                     Item('run_time', style='readonly', format_str='%.f'),
                                     Item('stop_time'),
                                     ),
                              Tabbed(VGroup(HGroup(Item('MW_frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('MW_power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_piMW', width= -80, enabled_when='state != "run"'),
                                                   ),
											HGroup(Item('RF_frequency', width= -80, enabled_when='state != "run"'),
                                                   Item('RF_power', width= -80, enabled_when='state != "run"'),
                                                   Item('t_piRF', width= -80, enabled_when='state != "run"'),
                                                   ),
                                            label='parameter'),
                                     VGroup(HGroup(Item('laser', width= -80, enabled_when='state != "run"'),
                                                   Item('record_length', width= -80, enabled_when='state != "run"'),
                                                   Item('bin_width', width= -80, enabled_when='state != "run"'),),
                                            label='settings'),
                              ),
                       ),
                       title='Ionization with 637nm laser',
                       )