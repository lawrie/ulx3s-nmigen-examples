#!/usr/bin/env python3

import argparse

from nmigen import *
from nmigen.build import *
from nmigen.back import pysim
from nmigen_boards.ulx3s import *

rotary_encoder_pmod = [
    Resource("rotary_encoder", 0,
             Subsignal("quadrature", Pins("2-", dir="i", conn=("gpio", 0)),
                       Attrs(IO_TYPE="LVCMOS33", PULLMODE="NONE")),
             Subsignal("in_phase", Pins("3-", dir="i", conn=("gpio", 0)),
                       Attrs(IO_TYPE="LVCMOS33", PULLMODE="NONE")))
]

class Top(Elaboratable):
    def __init__(self):
        self.iq_to_step_dir = IQToStepDir()
        self.state = Signal(unsigned(6), reset=0b000001)

    def elaborate(self, platform):
        encoder_pins = platform.request("rotary_encoder")
        red = platform.request("led", 0)
        yellow = platform.request("led", 1)
        leds = Cat([platform.request("led", i+2) for i in range(6)])

        m = Module()

        m.submodules.iq_to_step_dir = self.iq_to_step_dir

        # only change state when step happened
        with m.If(self.iq_to_step_dir.step):
            m.d.sync += [
                # on = cw, off = ccw
                red.eq(self.iq_to_step_dir.direction),
                # toggle led
                yellow.eq(1-yellow),
            ]
            # shift with wrap around
            with m.If(self.iq_to_step_dir.direction == 0):
                m.d.sync += self.state.eq(Cat(self.state[-1:], self.state[:-1]))
            with m.Else():
                m.d.sync += self.state.eq(Cat(self.state[1:], self.state[:1]))

        m.d.comb += [
            self.iq_to_step_dir.iq.eq(Cat(encoder_pins.in_phase, encoder_pins.quadrature)),
            leds.eq(self.state),
        ]

        return m

class IQToStepDir(Elaboratable):
    def __init__(self):
        # two incoming bits for in-phase and quadrature (A and B) inputs
        self.iq = Signal(2)
        # create storage for inputs
        self.iq_history = Array(Signal(2) for _ in range(2))
        # outgoing signals
        self.step = Signal(1)
        self.direction = Signal(1)

    def elaborate(self, _platform):
        m = Module()

        m.d.comb += [
            # a step is only taken when either I or Q flip.
            # if none flip, no step is taken
            # if both flip, an error happend
            self.step.eq(Cat(self.iq_history).xor()),
            # if the former value of I is the current value of Q, we move counter clockwise
            self.direction.eq(Cat(self.iq_history[1][0], self.iq_history[0][1]).xor()),
        ]

        m.d.sync += [
            # store the current and former state
            self.iq_history[1].eq(self.iq_history[0]),
            self.iq_history[0].eq(self.iq),
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
    parser.add_argument("-s", action="store_true", help="Simulate Rotary Encoder (for debugging).")
    args = parser.parse_args()

    if args.s:
        iq_to_step_dir = IQToStepDir()
        sim = pysim.Simulator(iq_to_step_dir)
        sim.add_clock(1.0 / 12e6)

        def out_proc():
            seq = (0b00, 0b01, 0b11, 0b10)
            yield iq_to_step_dir.iq.eq(0b00)
            for _ in range(16):
                for _ in range(4):
                    for iq in seq:
                        yield iq_to_step_dir.iq.eq(iq)
                        yield
                        yield
                        yield
                        yield
                for _ in range(4):
                    for iq in seq[::-1]:
                        yield iq_to_step_dir.iq.eq(iq)
                        yield
                        yield
                        yield
                        yield

        sim.add_sync_process(out_proc)
        with sim.write_vcd("rotary_encoder.vcd", "rotary_encoder.gtkw",
                           traces=[iq_to_step_dir.iq,
                                   iq_to_step_dir.step,
                                   iq_to_step_dir.direction]):
            sim.run()
    else:
        plat = variants[args.variant]()
        plat.add_resources(rotary_encoder_pmod)
        plat.build(Top(), do_program=True)
