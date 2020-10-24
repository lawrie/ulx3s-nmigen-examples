import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from  camread import *
from  st7789 import *

# The OLED pins are not defined in the ULX3S platform in nmigen_boards.
oled_resource = [
    Resource("oled_clk",  0, Pins("P4", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_mosi", 0, Pins("P3", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_dc",   0, Pins("P1", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_resn", 0, Pins("P2", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
    Resource("oled_csn",  0, Pins("N2", dir="o"), Attrs(IO_TYPE="LVCMOS33", DRIVE="4", PULLMODE="UP")),
]

ov7670_pmod = [
    Resource("ov7670", 0,
             Subsignal("cam_data", Pins("10+ 10- 9+ 9- 8+ 8- 7+ 7-", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_SIOD", Pins("0+", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_SIOC", Pins("0-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_HREF", Pins("1+", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_VSYNC", Pins("1-", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_PCLK", Pins("2+", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_XCLK", Pins("2-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33",DRIVE="4")),
             Subsignal("cam_PWON", Pins("3+", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33",DRIVE="4")),
             Subsignal("cam_RESET", Pins("3-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33",DRIVE="4")))
]

class CamTest(Elaboratable):
    def elaborate(self, platform):
        clk25 = platform.request("clk25")
        led = [platform.request("led", i) for i in range(8)]
        ov7670 = platform.request("ov7670")

        m = Module()
        
        # Create sync domain
        m.domains.sync = ClockDomain()
        m.d.comb += ClockSignal().eq(clk25.i)
        
        # Add CamRead submodule
        camread = CamRead()
        m.submodules.camread = camread

        # Add ST7789 submodule
        st7789 = ST7789(150000)
        m.submodules.st7789 = st7789

        # OLED
        oled_clk  = platform.request("oled_clk")
        oled_mosi = platform.request("oled_mosi")
        oled_dc   = platform.request("oled_dc")
        oled_resn = platform.request("oled_resn")
        oled_csn  = platform.request("oled_csn")

        buffer = Memory(width=16, depth=240 * 240)
        m.submodules.r = r = buffer.read_port()
        m.submodules.w = w = buffer.write_port()
        
        m.d.comb += [
            oled_clk .eq(st7789.spi_clk),
            oled_mosi.eq(st7789.spi_mosi),
            oled_dc  .eq(st7789.spi_dc),
            oled_resn.eq(st7789.spi_resn),
            oled_csn .eq(1),
            ov7670.cam_RESET.eq(1),
            ov7670.cam_PWON.eq(0),
            ov7670.cam_XCLK.eq(clk25.i),
            camread.p_data.eq(Cat([ov7670.cam_data[i] for i in range(8)])),
            camread.href.eq(ov7670.cam_HREF),
            camread.vsync.eq(ov7670.cam_VSYNC),
            camread.p_clock.eq(ov7670.cam_PCLK),
            w.en.eq(camread.pixel_valid & (camread.col[1:] >= 40) & (camread.col[1:] < 280)),
            w.addr.eq((camread.row[1:] * 240) + camread.col[1:] - 40),
            w.data.eq(camread.pixel_data),
            #r.en.eq(st7789.next_pixel),
            r.addr.eq((st7789.y[1:] * 240) + st7789.x[1:]),
            st7789.color.eq(r.data),
        ]

        with m.If(camread.frame_done):
            m.d.sync += Cat([led[i] for i in range(8)]).eq(Cat([led[i] for i in range(8)]) + 1)

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
    platform.add_resources(ov7670_pmod)    
    platform.add_resources(oled_resource)
    platform.build(CamTest(), do_program=True)
