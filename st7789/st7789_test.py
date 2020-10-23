import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from  st7789 import *

# The OLED pins are not defined in the ULX3S platform in nmigen_boards.
oled_resource = [
    Resource("oled_clk",  0, Pins("P4", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_mosi", 0, Pins("P3", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_dc",   0, Pins("P1", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_resn", 0, Pins("P2", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_csn",  0, Pins("N2", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
]

class ST7789Test(Elaboratable):
    def elaborate(self, platform):
        led = [platform.request("led", i) for i in range(8)]

        # OLED
        oled_clk  = platform.request("oled_clk")
        oled_mosi = platform.request("oled_mosi")
        oled_dc   = platform.request("oled_dc")
        oled_resn = platform.request("oled_resn")
        oled_csn  = platform.request("oled_csn")

        st7789 = ST7789(150000)
        m = Module()
        m.submodules.st7789 = st7789
       
        x = Signal(8)
        y = Signal(8)
        next_pixel = Signal()
 
        m.d.comb += [
            oled_clk .eq(st7789.spi_clk),
            oled_mosi.eq(st7789.spi_mosi),
            oled_dc  .eq(st7789.spi_dc),
            oled_resn.eq(st7789.spi_resn),
            oled_csn .eq(1),
            next_pixel.eq(st7789.next_pixel),
            x.eq(st7789.x),
            y.eq(st7789.y),
        ]

        with m.If(x[4] ^ y[4]):
            m.d.comb += st7789.color.eq(x[3:8] << 6)
        with m.Else():
            m.d.comb += st7789.color.eq(y[3:8] << 11)


        m.d.comb += [
            Cat([i.o for i in led]).eq(st7789.x)
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
    
    # Add the OLED resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(oled_resource)

    platform.build(ST7789Test(), do_program=True)
