
"""pi3diamond startup script"""

import logging, logging.handlers
import os
import inspect

path = os.path.dirname(inspect.getfile(inspect.currentframe()))

# First thing we do is start the logger
logging_handler = logging.handlers.TimedRotatingFileHandler(path+'/log/diamond_log.txt', 'W6') # start new file every sunday, keeping all the old ones 
logging_handler.setFormatter(logging.Formatter("%(asctime)s - %(module)s.%(funcName)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(logging_handler)
stream_handler=logging.StreamHandler()
stream_handler.setLevel(logging.INFO) # we don't want the console to be swamped with debug messages
logging.getLogger().addHandler(stream_handler) # also log to stderr
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().info('Starting logger.')


# start the JobManager
from tools import emod
emod.JobManager().start()

# start the CronDaemon
from tools import cron
cron.CronDaemon().start()

# define a shutdown function
from tools.utility import StoppableThread
import threading

"""    
def startExperiment:
    ha.AWG().set_vpp(2.0, 0b01)
    ha.AWG().set_vpp(2.0, 0b10)
    ha.AWG().set_sampling(1.e9)
"""
    
# That's it for now! We pass over control to custom startup script if present. 
if os.access(path+'/diamond_custom.py', os.F_OK):
    execfile(path+'/diamond_custom.py')
