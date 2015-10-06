import sys
import tkinter as tk
from skardas import tkplot
from skardas.skardas import execute_delayed
import threading
from queue import Queue, Empty
import serial
import struct
from collections import namedtuple
from time import sleep


class Status(namedtuple('Status', ['time', 'power', 'temp_outside', 'temp_inside'])):
    @property
    def delta_temp(self):
        return self.temp_inside - self.temp_outside


class Arduino:
    def __init__(self, filename):
        self.filename = filename
        self.status = Queue()
        self.command = Queue()
        self.thread = threading.Thread(target=self.interact, daemon=True)
        self.started = threading.Event()
        self.last_status = None
        self._power = None

    def line_status(self, line):
        t_ms, pwm, temp_outside, temp_inside = line.strip().split(b',')
        t = float(t_ms) / 1000.0
        p = float(pwm) / 255.0
        temp_outside = float(temp_outside)
        temp_inside = float(temp_inside)
        return Status(t, p, temp_outside, temp_inside)

    def interact(self):
        with open(self.filename, 'wb') as f:
            self.serial = serial.Serial('/dev/ttyACM0', 115200)
            try:
                self.started.set()
                while True:
                    try:
                        while True:
                            self.serial.write(self.command.get_nowait())
                    except Empty:
                        pass

                    line = self.serial.readline()
                    try:
                        status = self.line_status(line)
                    except ValueError:
                        continue
                    self.status.put_nowait(status)
                    self.last_status = status
                    self._power = status.power
                    f.write(line)
            finally:
                self.started.clear()

    def iter_status(self):
        assert(self.started.is_set())
        try:
            while True:
                status = self.status.get_nowait()
                yield status
        except Empty:
            pass

    def __str__(self):
        return "<{} {}>".format(self.__class__.__name__, self.last_status if self.started.is_set() else '(stopped)')


    @property
    def power(self):
        assert(self.started.is_set())
        return self._power

    @power.setter
    def power(self, power):
        assert(self.started.is_set())
        assert(0 <= power <= 1)
        pwm = int(power * 255)
        command = struct.pack('cB', b'P', pwm)
        self.command.put(command)

    def start(self):
        self.thread.start()
        self.started.wait()


class HeatPlot(tkplot.TkPlot):
    def __init__(self, root):
        tkplot.TkPlot.__init__(self, root, (9, 6))
        self.time = []
        self.temperature = []
        self.power = []

        self.plot = self.figure.add_subplot(111)
        self.plot.set_xlabel("Time (s)")
        self.plot.set_ylabel("Temperature (red, °C) / power (blue, %)")
        self.plot.set_xlim(0, 1)
        self.plot.set_ylim(0, 110)
        self.temp_line, = self.plot.plot(self.time, self.temperature)
        self.power_line, = self.plot.plot(self.time, self.power)
        self.figure.tight_layout()

    def add(self, status):
        self.time.append(status.time)
        self.temperature.append(status.temp_inside)
        self.power.append(status.power * 100)

        self.plot.set_xlim(min(self.time), max(self.time))
        self.plot.set_ylim(0, max(110, round(max(self.temperature) / 50.0 + 0.5) * 50 + 10))
        self.temp_line.set_xdata(self.time)
        self.temp_line.set_ydata(self.temperature)
        self.power_line.set_xdata(self.time)
        self.power_line.set_ydata(self.power)
        self.figure.canvas.draw()


class Krosnis:
    def __init__(self, root, experiment):
        self.root = root
        self.root.title("krosnis - {}".format(experiment))

        self.plot = HeatPlot(self.root)
        self.plot.pack(fill=tk.BOTH, expand=1)

        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(fill=tk.X)
        self.label = tk.Label(self.toolbar)
        self.label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)

        self.power_val = tk.StringVar()
        self.power_val.set('0.0')
        self.power = tk.Entry(self.toolbar, textvariable=self.power_val)
        self.power.bind('<Return>', self.set_power)
        self.power.pack(side=tk.LEFT)
        self.power.focus_set()
        self.set_power = tk.Button(self.toolbar, text='Set power', command=self.set_power)
        self.set_power.pack(side=tk.LEFT)

        self.arduino = Arduino("experiments/{}.csv".format(experiment))

    def set_status(self, status):
        self.label.config(text=status)

    def set_power(self, event=None):
        self.arduino.power = float(self.power_val.get())

    def start(self):
        _self = self
        def shell():
            self = _self
            import IPython
            IPython.embed()
        threading.Thread(target=shell, daemon=True).start()
        execute_delayed(self.root, self.sample())

    def sample(self):
        self.arduino.start()
        while True:
            for s in self.arduino.iter_status():
                self.plot.add(s)
                self.set_status(str(s))
            yield 0.1


def run(experiment):
    root = tk.Tk()
    root.geometry("1000x700")
    win = Krosnis(root, experiment)
    win.start()
    tk.mainloop()

if __name__ == "__main__":
    run(sys.argv[1])