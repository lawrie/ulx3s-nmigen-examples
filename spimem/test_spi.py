import argparse

from nmigen.build import *
from nmigen import *
from nmigen_boards.ulx3s import *

from spimem import SpiMem

# Spi pins from ESP32 re-use two of the sd card pins
esp32_spi = [
    Resource("esp32_spi", 0,
        Subsignal("csn", Pins("N4", dir="i")),
        Subsignal("copi", Pins("H1", dir="i")),
        Subsignal("cipo", Pins("K1", dir="o")),
        Subsignal("sclk", Pins("L1", dir="i")),
        Attrs(PULLMODE="NONE", DRIVE="4", IO_TYPE="LVCMOS33"))
]

# Test of spi memory reads and writes from the ESP32
class Top(Elaboratable):
    def elaborate(self, platform):
        leds = Cat([platform.request("led", i) for i in range(8)])
        esp32 = platform.request("esp32_spi")
        csn = esp32.csn
        sclk = esp32.sclk
        copi = esp32.copi
        cipo = esp32.cipo

        m = Module()

        rd   = Signal()    # Set when read requested
        wr   = Signal()    # Set when write requested
        addr = Signal(32)  # The requested address
        din  = Signal(8)   # The data to be sent back
        dout = Signal(8)   # The data to be written

        m.submodules.spimem = spimem = SpiMem(addr_bits=32)

        # Use 4Kb of BRAM
        mem = Memory(width=8, depth=4096)
        m.submodules.r = r = mem.read_port()
        m.submodules.w = w = mem.write_port()

        m.d.comb += [
            # Connect spimem
            spimem.csn.eq(~csn),
            spimem.sclk.eq(sclk),
            spimem.copi.eq(copi),
            spimem.din.eq(din),
            cipo.eq(spimem.cipo),
            addr.eq(spimem.addr),
            dout.eq(spimem.dout),
            rd.eq(spimem.rd),            
            wr.eq(spimem.wr & (addr[24:] == 0)),
            # Connect memory
            r.addr.eq(addr),
            din.eq(r.data),
            w.data.eq(dout),
            w.addr.eq(addr),
            w.en.eq(wr),
            # led diagnostics
            leds.eq(Cat([csn,sclk,copi,cipo,rd,wr]))
        ]

        return m

if __name__ == "__main__":
    variants = {
        '12F': ULX3S_12F_Platform,
        '25F': ULX3S_25F_Platform,
        '45F': ULX3S_45F_Platform,
        '85F': ULX3S_85F_Platform
    }

    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    args = parser.parse_args()

    platform = variants[args.variant]()
    platform.add_resources(esp32_spi)
    platform.build(Top(), do_program=True)

