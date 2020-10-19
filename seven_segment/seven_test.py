import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *
from seven_seg import SevenSegController

seven_seg_pmod = [
    Resource("seven_seg", 0,
             Subsignal("aa", Pins("24-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ab", Pins("23-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ac", Pins("22-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ad", Pins("21-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ae", Pins("17-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("af", Pins("16-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ag", Pins("15-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ca", Pins("14-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")))
]

class SevenTest(Elaboratable):
    def elaborate(self, platform):
        led = [platform.request("led", i) for i in range(8)]
        sw = [platform.request("switch", i) for i in range(4)]
        btn = [platform.request("button_pwr"),
               platform.request("button_fire", 0),
               platform.request("button_fire", 1),
               platform.request("button_up"),
               platform.request("button_down"),
               platform.request("button_left"),
               platform.request("button_right")]
        seg_pins = platform.request("seven_seg")

        timer = Signal(26)
        seven = SevenSegController()

        m = Module()
        m.submodules.seven = seven
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += [
            Cat([i.o for i in led]).eq(timer[-9:-1]),
            Cat([seg_pins.aa, seg_pins.ab, seg_pins.ac, seg_pins.ad,
                 seg_pins.ae, seg_pins.af, seg_pins.ag]).eq(seven.leds),
            seg_pins.ca.eq(timer[-1])
        ]
        with m.If(btn[1]):
             m.d.comb += seven.val.eq(Cat([i.i for i in sw]))
        with m.Else():
             m.d.comb += seven.val.eq(timer[-5:-1])

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
    platform.add_resources(seven_seg_pmod)
    platform.build(SevenTest(), do_program=True)
