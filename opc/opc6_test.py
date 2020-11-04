import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *
from opc6 import *

class OPC6Test(Elaboratable):
    def elaborate(self, platform):
        led = [platform.request("led", i) for i in range(8)]
        leds = Cat([led[i].o for i in range(8)])

        opc6 = OPC6()

        m = Module()
        m.submodules.opc6 = opc6

        m.d.comb += [
            opc6.int_b.eq(3),
            opc6.reset_b.eq(1),
            opc6.clken.eq(1),
            opc6.din.eq(0x3000),
            leds.eq(opc6.dout)
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
    platform.build(OPC6Test(), do_program=True)

