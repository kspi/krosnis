import math
cimport numpy as np
from scipy import signal
import cython

cdef double th(double t, double p, double th0, double th_max, double rc_h, double rc_c):
    cdef double heating = p * th_max * (1 - math.exp(-t / rc_h))
    cdef double cooling = th0 * math.exp(-t / rc_c)
    return heating + cooling

@cython.boundscheck(False)
def sim_loop(np.ndarray[double] ths,           # output temperature array
             double dt,                        # sampling period
             np.ndarray[double] ps,            # power proportion array
             double b0, double b1, double a1,  # filter coefficients
             double th_max, double rc_h, double rc_c):
    
    cdef double y1 = ps[0]
    cdef unsigned int i
    for i in range(1, ths.shape[0]):
        # lowpass filter p
        p = b0 * ps[i] + b1 * ps[i - 1] - a1 * y1
        y1 = p
        
        ths[i] = th(dt, p, ths[i - 1], th_max, rc_h, rc_c)
