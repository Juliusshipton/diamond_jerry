import numpy as np
import time
from nidaq import DOTask

class FlipMirror():

    def __init__(self, trigger_channels):
        #super(self).__init__()
        self._trigger_task = DOTask(trigger_channels)

    def flip(self):
        self._trigger_task.Write(np.array((1,), dtype=np.uint8) )
        time.sleep(0.01)
        self._trigger_task.Write(np.array((0,), dtype=np.uint8) )
        time.sleep(0.01)


"""
in custom_api
def FlipMirror():
    import mirror
    return mirror.FlipMirror('/Dev0/port0/line0')

in measurements
    ha.FlipMirror().flip()
    time.sleep(0.1)       # wait until mirror has fully flipped

"""
