import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

class Leds(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(8)]
        timer = Signal(30)

        m = Module()
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += Cat([i.o for i in led]).eq(timer[-9:-1])
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
    platform.build(Leds(), do_program=True)
