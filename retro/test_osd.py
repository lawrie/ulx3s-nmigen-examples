import argparse

from nmigen.build import *
from nmigen import *
from nmigen_boards.ulx3s import *

from spi_osd import SpiOsd

# Spi pins from ESP32 re-use two of the sd card pins
esp32_spi = [
    Resource("esp32_spi", 0,
        Subsignal("irq", Pins("L2", dir="o")),
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
        btn = Cat([platform.request("button",i) for i in range(6)])
        pwr = platform.request("button_pwr")
        esp32 = platform.request("esp32_spi")
        csn = esp32.csn
        sclk = esp32.sclk
        copi = esp32.copi
        cipo = esp32.cipo
        irq  = esp32.irq

        m = Module()

        m.domains.pixel = pixel = ClockDomain("pixel")

        m.d.comb += ClockSignal("pixel").eq(ClockSignal())

        m.submodules.osd = osd = SpiOsd()

        m.d.comb += [
            # Connect osd
            osd.i_csn.eq(~csn),
            osd.i_sclk.eq(sclk),
            osd.i_copi.eq(copi),
            # led diagnostics
            leds.eq(Cat([csn,sclk,copi,cipo]))
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

