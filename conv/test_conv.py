import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

from conv3 import Conv3

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        leds = Cat([platform.request("led", i) for i in range(8)])

        k = Array([0, 0, 0, 0, 1, 0, 0, 0, 0])

        m.submodules.conv3 = conv3 = Conv3(k)

        cnt = Signal(8)
        m.d.sync += cnt.eq(cnt+1)

        m.d.comb += [
            conv3.i_valid.eq(1),
            conv3.i_p.eq(cnt),
            leds.eq(conv3.o_p)
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
    platform.build(Top(), do_program=True)
