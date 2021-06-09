from nmigen import *
from nmigen.sim import Simulator

from spimem import SpiMem

class TestSPI(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        timer = Signal(8)
        
        m.d.sync += timer.eq(timer + 1)

        m.submodules.spimem = spimem = self.spimem = SpiMem(addr_bits=16)

        m.d.comb += [
            spimem.sclk.eq(timer[0]),
            #spimem.copi.eq((timer == 0x30) | (timer == 0x10)), # read address 1
            spimem.copi.eq((timer == 0x30) | (timer == 0x40)), # write address 1, dout = 1
            spimem.csn.eq(timer == 0),
            spimem.din.eq(0x55)
        ]

        return m

if __name__ == "__main__":
    m = Module()
    m.submodules.test = test = TestSPI()

    sim = Simulator(m)
    sim.add_clock(1e-6)

    def process():

        for i in range(67):
            yield

        addr = yield test.spimem.addr
        print("addr:", addr)
        dout = yield test.spimem.dout
        print("dout:", dout)

    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd", "test.gtkw"):
        sim.run()

