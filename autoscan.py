scannr	= an.pulsed.PulseAnalyzer()
nr1		= NuclearRabi()
scannr.measurement	= nr1
scannr.fit	= an.pulsed.RabiFit()
scannr.edit_traits()

mwpower = -24
mwfreq  = 2.87652e9
mwpi	= 1350

rffreq 	= range(2.7610e6, 2.7615e6, 2.e3)
rfpower	= range(3,3)
rfsource= 'rf_1'  # HP _1, SMIQ _2
rf		= {'rf_1': 'HP','rf_2': 'SMIQ'}

scannr.measurement.mw_power		= mwpower
scannr.measurement.mw_frequency	= mwfreq
scannr.measurement.mw_pi		= mwpi
scannr.measurement.tau_begin	= 30
scannr.measurement.tau_ende		= 550000
scannr.measurement.tau_delta	= 500
scannr.measurement.stop_time	= 300
scannr.measurement.switch		= rfsource

os.chdir('d:/Data/temp/')
os.mkdir('1303')
os.chdir('1303')

for (rff,rfp) in (rffreq,rfpower):
	scannr.measurement.rf_power 	= rfp
	scannr.measurement.rf_frequency	= rff
	scannr.measurement.submit()
	while scannr.state == 'run':
		pass
	filename	= str(int(rff/e6)) + rf
	scannr.save(filename + '.pys')
	scannr.save_line_plot(filename + '.png')