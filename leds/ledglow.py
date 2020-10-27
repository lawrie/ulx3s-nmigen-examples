import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

class LedGlow(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(8)]
        cnt = Signal(26)
        pwm_input = Signal(4)
        pwm = Signal(5)

        m = Module()

        m.d.sync += [
            cnt.eq(cnt + 1),
            pwm.eq(pwm[0:-1] + pwm_input)
        ]

        with m.If(cnt[-1]):
            m.d.sync += pwm_input.eq(cnt[-5:])
        with m.Else():
            m.d.sync += pwm_input.eq(~cnt[-5:])

        for l in led:
            m.d.comb += l.eq(pwm[-1])

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
    platform.build(LedGlow(), do_program=True)
