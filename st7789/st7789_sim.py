from nmigen import *
from nmigen.sim import Simulator, Delay, Settle, Passive
from st7789 import *

if __name__ == "__main__":
    m = Module()
    m.submodules.st7789 = st7789 = ST7789(1)

    sim = Simulator(m)
    sim.add_clock(4e-8)

    def process():
        yield st7789.color.eq(0xf800)
        yield Passive()

    sim.add_process(process)
    with sim.write_vcd("test.vcd", "test.gtkw", traces=st7789.ports()):
        sim.run_until(30e-6, run_passive=True)
