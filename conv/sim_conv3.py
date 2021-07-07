from nmigen import *
from nmigen.sim import *
from conv3 import Conv3
 
if __name__ == "__main__":
    def process():
        for i in range(34):
            yield dut.i_p.eq(i+1)
            yield dut.i_valid.eq(1)
            yield

    m = Module()
    k = Array([0,0,0, 0,1,0, 0,0,0])

    dut = Conv3(k, 0, w=6, h=4)
    m.submodules.dut = dut

    sim = Simulator(m) 
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd", "test.gtkw"):
        sim.run()

