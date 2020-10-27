import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

from uart import *
from ps2 import *

ps2_pullup = [
    Resource("ps2_pullup", 0, Pins("C12", dir="o") , Attrs(IO_TYPE="LVCMOS33", DRIVE="16"))
]

class ByteToHex(Elaboratable):
    def __init__(self):
        self.b = Signal(4)
        self.h = Signal(8)

    def elaborate(self, platform):
        
        m = Module()

        with m.If(self.b < 10):
            m.d.comb += self.h.eq(ord('0') + self.b)
        with m.Else():
            m.d.comb += self.h.eq(ord('a') + self.b - 10)

        return m
        
class Ps2Test(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(8)]
        leds  = Cat([led[i].o for i in range(8)])
        serial = platform.request("uart")
        usb = platform.request("usb")
        ps2_pullup = platform.request("ps2_pullup")

        m = Module()

        uart = UART(serial, int(platform.default_clk_frequency), 115200)
        m.submodules.uart = uart

        ps2 = PS2()
        m.submodules.ps2 = ps2

        bytetohex = ByteToHex()
        m.submodules.bytetohex = bytetohex

        tx_ready = Signal(1, reset=0)
        tx_state = Signal(2, reset=0)

        m.d.comb += [
            usb.pullup.eq(1),
            ps2_pullup.eq(1),
            ps2.ps2_clk.eq(usb.d_p),
            ps2.ps2_data.eq(usb.d_n),
            leds.eq(ps2.data),
            uart.tx_ready.eq(tx_ready),
            uart.tx_data.eq(bytetohex.h)
        ]

        with m.Switch(tx_state):
            with m.Case(0):
                with m.If(ps2.valid):
                    m.d.sync += [
                        tx_state.eq(1),
                        bytetohex.b.eq(ps2.data[4:]),
                        tx_ready.eq(1)
                    ]
            with m.Case(1):
                with m.If(uart.tx_ack):
                    m.d.sync += [
                         tx_state.eq(2),
                         bytetohex.b.eq(ps2.data[:4])
                    ]
            with m.Case(2):
                with m.If(uart.tx_ack):
                    m.d.sync += [
                        tx_state.eq(0),
                        tx_ready.eq(0)
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
    platform.add_resources(ps2_pullup)
    platform.build(Ps2Test(), do_program=True)
