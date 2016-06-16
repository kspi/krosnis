import numpy
from scipy.optimize import minimize, minimize_scalar
from scipy import signal

import pyximport; pyximport.install()
from sim import sim_loop

sampling_period = 1


class TemperatureModel:
    def __init__(self, dt, th_max, heating_rc, cooling_rc, p_rc):
        self.dt = dt
        self.set_parameters(th_max, heating_rc, cooling_rc, p_rc)

    def show(self):
        print('TemperatureModel(')
        for v in ['dt', 'th_max', 'heating_rc', 'cooling_rc', 'p_rc']:
            print('    {}={},'.format(v, getattr(self, v)))
        print(')')

    def set_parameters(self, th_max, heating_rc, cooling_rc, p_rc):
        self.th_max = th_max
        self.heating_rc = heating_rc
        self.cooling_rc = cooling_rc
        self.p_rc = p_rc
        self.update_filter()

    def update_filter(self):
        self.b, self.a = signal.butter(1, (0.5 / self.p_rc) / (0.5 / self.dt))

    def predict(self, steps, th0, power):
        assert(isinstance(power, numpy.ndarray))
        power[power > 1] = 1
        ths = numpy.zeros(steps)
        ths[0] = th0
        sim_loop(ths, self.dt, power,
                 self.b[0], self.b[1], self.a[1],
                 self.th_max, self.heating_rc, self.cooling_rc)
        return ths

    def reference_predict(self, reference):
        return self.predict(len(reference), reference.temperature[0], numpy.array(reference.power))

    def reference_error(self, reference):
        e = self.reference_predict(reference) - reference.temperature
        e *= 1 + (e > 0)
        e *= 1 + numpy.exp(-numpy.arange(0, len(e)) * self.dt / 30)
        return numpy.mean(numpy.power(e, 2))

    def optimize(self, reference, fields, initial, bounds):
        fieldname = 'optimization_' + '_'.join(fields)
        def error(vals):
            for field, val in zip(fields, vals):
                setattr(self, field, val)
            return self.reference_error(reference)
        try:
            r = minimize(error, initial, bounds=bounds)
            if r.success and (not hasattr(self, fieldname) or r.fun < getattr(self, fieldname).fun):
                print("optimize[{}]: Better fitness achieved: {} {}".format(fieldname, r.fun, r.x))
                setattr(self, fieldname, r)
        finally:
            if hasattr(self, fieldname):
                for field, val in zip(fields, getattr(self, fieldname).x):
                    setattr(self, field, val)
        return r

    def approximate_heating(self, th0, th1):
        delta = th1 - th0
        if delta > 0:
            full_time = self.heating_rc * delta / self.th_max
            full_val = 1
        elif delta == 0:
            full_time = 0
            full_val = 0
        else:
            full_time = self.cooling_rc * -delta / th0
            full_val = 0
        return full_time, full_val

    def heating_predict(self, steps, th0, th1, p0, support_power, full_time, full_val):
        p = numpy.zeros(steps)
        transition_idx = max(2, int(full_time / self.dt))
        p[0] = p0
        p[1:transition_idx] = full_val
        p[transition_idx:] = support_power
        return self.predict(steps, th0, p)

    def optimize_heating(self, th0, th1, p0=0):
        total_rc = max(60, self.heating_rc, self.cooling_rc)
        steps = int(total_rc * 20 / self.dt)
        full_time, full_val = self.approximate_heating(th0, th1)

        t = numpy.arange(0, steps) * self.dt
        overshoot_penalty = self.cooling_rc / self.heating_rc

        def errorp(p):
            e = self.heating_predict(steps, th1, th1, p, p, 0, 0) - th1
            return numpy.sum(numpy.abs(e))
        rp = minimize_scalar(errorp, bounds=(0, 1), method='bounded')
        print("optimize_heating:p: {} {}".format(rp.fun, rp.x))
        p = rp.x

        def errortf(time_factor):
            e = self.heating_predict(steps, th0, th1, p0, p, full_time * time_factor, full_val) - th1
            e *= 1 + (overshoot_penalty - 1) * (e < 0)
            return numpy.sum(t * numpy.abs(e) / total_rc)
        rtf = minimize_scalar(errortf, bounds=(0, 2.5), method='bounded')
        print("optimize_heating:tf: {} {}".format(rtf.fun, rtf.x))
        tf = rtf.x

        return p, full_time * tf, full_val

