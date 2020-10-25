import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

stereo = [
    Resource("stereo", 0,
        Subsignal("l", Pins("E4 D3 C3 B3", dir="o")),
        Subsignal("r", Pins("A3 B5 D5 C5", dir="o")),
    )
]

class Music2a(Elaboratable):
    def elaborate(self, platform):
        stereo  = platform.request("stereo", 0)

        m = Module()

        left = stereo.l.o
        counter = Signal(15)
        clkdivider = Signal(15)
        tone = Signal(28)
        fastsweep = Signal(7)
        slowsweep = Signal(7)

        m.d.sync += tone.eq(tone + 1)

        with m.If(tone[22]):
            m.d.comb += fastsweep.eq(tone[15:22])
        with m.Else():
            m.d.comb += fastsweep.eq(~tone[15:22])

        with m.If(tone[25]):
            m.d.comb += slowsweep.eq(tone[18:25])
        with m.Else():
            m.d.comb += slowsweep.eq(~tone[18:25])

        with m.If(tone[27]):
            m.d.comb += clkdivider.eq(Cat([Const(0,6),slowsweep,Const(1,2)]))
        with m.Else():
            m.d.comb += clkdivider.eq(Cat([Const(0,6),fastsweep,Const(1,2)]))

        
        with m.If(counter == 0):
            m.d.sync += [
                left.eq(15 - left),
                counter.eq(clkdivider)
            ]
        with m.Else():
           m.d.sync += counter.eq(counter - 1)
          
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
    platform.add_resources(stereo)
    platform.build(Music2a(), do_program=True)
