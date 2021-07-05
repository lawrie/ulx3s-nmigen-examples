import argparse

from nmigen import *
from nmigen_stdio.serial import AsyncSerial
from nmigen.build import *
from nmigen_boards.ulx3s import *

stereo = [
    Resource("stereo", 0,
        Subsignal("l", Pins("E4 D3 C3 B3", dir="o")),
        Subsignal("r", Pins("A3 B5 D5 C5", dir="o")),
    )
]

class Stream(Elaboratable):
    def elaborate(self, platform):
        stereo  = platform.request("stereo")
        uart    = platform.request("uart")
        divisor = int(platform.default_clk_frequency // 115200)

        m = Module()

        # Create the uart
        m.submodules.serial = serial = AsyncSerial(divisor=divisor, pins=uart)

        pwm_acc = Signal(9)
        dat_r   = Signal(8)

        m.d.comb += [
            serial.rx.ack.eq(1),
            stereo.l.o.eq(Mux(pwm_acc[-1], 0x7, 0x0)), # Not too loud
            stereo.r.o.eq(stereo.l.o)
        ]

        with m.If(serial.rx.rdy):
            m.d.sync += dat_r.eq(serial.rx.data)

        m.d.sync += pwm_acc.eq(pwm_acc[:8] + dat_r)

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
    platform.build(Stream(), do_program=True)

