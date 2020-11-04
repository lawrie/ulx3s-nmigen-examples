from nmigen import *
from nmigen.back.pysim import Simulator, Delay, Settle

from opc6 import *
from readhex import *

class TestCPU(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        m.submodules.opc6 = self.opc6 = OPC6()
        code = readhex("test.hex")
        print(code)
        mem = Memory(width=16, depth = 1024, init=code)

        din = Signal(16)

        m.d.comb += din.eq(mem[self.opc6.address])
        
        with m.If(self.opc6.rnw == 0):
            m.d.sync += mem[self.opc6.address].eq(self.opc6.dout)

        m.d.comb += [
            self.opc6.int_b.eq(3),
            self.opc6.reset_b.eq(1),
            self.opc6.clken.eq(1),
            self.opc6.din.eq(din)
        ]

        return m

if __name__ == "__main__":
    m = Module()
    m.submodules.test = test = TestCPU()

    sim = Simulator(m)
    sim.add_clock(1e-6)

    def process():
        while(True):
            yield
            halted = ((yield test.opc6.halted))
            if halted:
                print("Halted")
                break
        addr = ((yield test.opc6.address))
        print("Address: " + str(addr))

    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd", "test.gtkw", traces=test.opc6.ports()):
        sim.run()
