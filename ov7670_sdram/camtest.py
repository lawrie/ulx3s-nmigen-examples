import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from camread import *
from st7789 import *
from camconfig import *
from ecp5pll import ECP5PLL

from sdram_controller16 import sdram_controller

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
             Subsignal("cam_SIOD", Pins("0+", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_SIOC", Pins("0-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_HREF", Pins("1+", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_VSYNC", Pins("1-", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_PCLK", Pins("2+", dir="i", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("cam_XCLK", Pins("2-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33",DRIVE="4")),
             Subsignal("cam_PWON", Pins("3+", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33",DRIVE="4")),
             Subsignal("cam_RESET", Pins("3-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33",DRIVE="4")))
]

pmod_led8_2 = [
    Resource("led8_2", 0,
        Subsignal("leds", Pins("21+ 22+ 23+ 24+ 21- 22- 23- 24-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

pmod_led8_3 = [
    Resource("led8_3", 0,
        Subsignal("leds", Pins("14+ 15+ 16+ 17+ 14- 15- 16- 17-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

class CamTest(Elaboratable):
    def elaborate(self, platform):
        leds = Cat([platform.request("led", i) for i in range(8)])
        ov7670 = platform.request("ov7670")
        btn1 = platform.request("button_fire", 0)
        pwr = platform.request("button_pwr", 0)
        led8_2 = platform.request("led8_2")
        led8_3 = platform.request("led8_3")
        led16 =  [i for i in led8_2] + [i for i in led8_3]
        leds16 = Cat([i for i in led16])

        clk_in = platform.request(platform.default_clk, dir='-')[0]

        m = Module()
        
        # Clock generation
        # PLL - 100MHz for sdram
        sdram_freq = 100000000
        m.domains.sdram = cd_sdram = ClockDomain("sdram")
        m.domains.sdram_clk = cd_sdram_clk = ClockDomain("sdram_clk")

        m.submodules.ecp5pll = pll = ECP5PLL()
        pll.register_clkin(clk_in,  platform.default_clk_frequency)
        pll.create_clkout(cd_sdram, sdram_freq)
        pll.create_clkout(cd_sdram_clk, sdram_freq, phase=180)

        # Divide clock by 4
        div = Signal(3)
        m.d.sdram += div.eq(div+1)

        # Power-on reset
        reset_cnt = Signal(5, reset=0)
        with m.If(~reset_cnt.all()):
            m.d.sdram += reset_cnt.eq(reset_cnt+1)

        # Make sync domain 25MHz
        m.domains.sync = cd_sync = ClockDomain("sync")
        #m.d.comb += ResetSignal().eq(~reset.all() | pwr)
        m.d.comb += ClockSignal().eq(div[1])

        # Add the SDRAM controller
        m.submodules.mem = mem = sdram_controller()

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

        cnt = Signal(26)
        m.d.sync += cnt.eq(cnt + 1)

        # Camera config
        camconfig = CamConfig()
        m.submodules.camconfig = camconfig

        m.d.comb += [
            oled_clk .eq(st7789.spi_clk),
            oled_mosi.eq(st7789.spi_mosi),
            oled_dc  .eq(st7789.spi_dc),
            oled_resn.eq(st7789.spi_resn),
            oled_csn .eq(1),
            ov7670.cam_RESET.eq(1),
            ov7670.cam_PWON.eq(0),
            ov7670.cam_XCLK.eq(div[1]),
            camread.p_data.eq(Cat([ov7670.cam_data[i] for i in range(8)])),
            camread.href.eq(ov7670.cam_HREF),
            camread.vsync.eq(ov7670.cam_VSYNC),
            camread.p_clock.eq(ov7670.cam_PCLK),
            st7789.color.eq(mem.data_out),
            camconfig.start.eq(btn1),
            ov7670.cam_SIOC.eq(camconfig.sioc),
            ov7670.cam_SIOD.eq(camconfig.siod),
        ]

        pixel_valid2 = Signal()
        pixel_valid = Signal()

        m.d. sync += [
            pixel_valid2.eq(camread.pixel_valid)
        ]

        m.d.comb += pixel_valid.eq(camread.pixel_valid | pixel_valid2)

        raddr = Signal(24)
        waddr = Signal(24)
        sync  = Signal()

        # Write to SDRAM
        m.d.comb += [
            sync.eq(~div[2]),
            raddr.eq(((239 - st7789.x) * 320) + st7789.y),
            waddr.eq((camread.row[1:] * 320) + camread.col[1:]),
            mem.init.eq(reset_cnt == 0),
            mem.sync.eq(sync),      # Sync with 25MHz clock
            mem.address.eq(Mux(st7789.next_pixel, raddr, waddr)),
            mem.data_in.eq(camread.pixel_data),
            mem.req_read.eq(sync & st7789.next_pixel), # Always read when pixel requested
            mem.req_write.eq(sync & ~st7789.next_pixel & pixel_valid), # Delay write one cycle if needed
            leds16.eq(mem.data_out)
        ]

        with m.If(camread.frame_done):
            m.d.sync += leds.eq(leds + 1)

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
    platform.add_resources(pmod_led8_2)
    platform.add_resources(pmod_led8_3)

    platform.build(CamTest(), do_program=True)

