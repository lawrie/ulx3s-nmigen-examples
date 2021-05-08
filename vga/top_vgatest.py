import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from blink import Blink
from vga import VGA
from vga_timings import *
from ecp5pll import ECP5PLL

vga_pmod = [
    Resource("vga", 0,
             Subsignal("red", Pins("24- 23- 22- 21-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("green", Pins("17- 16- 15- 14-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("blue", Pins("24+ 23+ 22+ 21+", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("hs", Pins("17+", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("vs", Pins("16+", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")))
]

#  Modes tested on an ASUS monitor:
#
#  640x350  @70Hz
#  640x350  @85Hz (out of range, but works)
#  640x400  @70Hz
#  640x400  @85Hz (out of range)
#  640x480  @60Hz
#  720x400  @85Hz (out of range)
#  720x576  @60Hz
#  720x576  @72Hz
#  720x576  @75Hz
#  800x600  @60Hz
#  848x480  @60Hz
# 1024x768  @60Hz
# 1152x864  @60Hz (does not synthesize)
# 1280x720  @60Hz
# 1280x768  @60Hz (requires slight overclock)
# 1280x768  @60Hz CVT-RB
# 1280x800  @60Hz (does not synthesize)
# 1280x800  @60Hz CVT
# 1366x768  @60Hz (does not synthesize)
# 1280x1024 @60Hz (does not synthesize)
# 1920x1080 @30Hz (monitor says 50Hz, but works)
# 1920x1080 @30Hz CVT-RB (syncs, but black screen)
# 1920x1080 @30Hz CVT-RB2 (syncs, but black screen)
# 1920x1080 @60Hz (does not synthesize)
class TopVGATest(Elaboratable):
    def __init__(self,
                 timing: VGATiming, # VGATiming class
                 xadjustf=0, # adjust -3..3 if no picture
                 yadjustf=0): # or to fine-tune f
        self.o_led = Signal(8)
        self.o_gpdi_dp = Signal(4)
        self.o_user_programn = Signal()
        self.o_wifi_gpio0 = Signal()
        # Configuration
        self.timing = timing
        self.x = timing.x
        self.y = timing.y
        self.f = timing.pixel_freq
        self.xadjustf = xadjustf
        self.yadjustf = yadjustf

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        if platform:
            clk_in = platform.request(platform.default_clk, dir='-')[0]

            # Constants
            pixel_f     = self.timing.pixel_freq
            hsync_front_porch = self.timing.h_front_porch
            hsync_pulse_width = self.timing.h_sync_pulse
            hsync_back_porch  = self.timing.h_back_porch
            vsync_front_porch = self.timing.v_front_porch
            vsync_pulse_width = self.timing.v_sync_pulse
            vsync_back_porch  = self.timing.v_back_porch

            # Clock generator.
            m.domains.sync  = cd_sync  = ClockDomain("sync")
            m.domains.pixel = cd_pixel = ClockDomain("pixel")

            m.submodules.ecp5pll = pll = ECP5PLL()
            pll.register_clkin(clk_in,  platform.default_clk_frequency)
            pll.create_clkout(cd_sync,  platform.default_clk_frequency)
            pll.create_clkout(cd_pixel, pixel_f)

            platform.add_clock_constraint(cd_sync.clk,  platform.default_clk_frequency)
            platform.add_clock_constraint(cd_pixel.clk, pixel_f)

            # VGA signal generator.
            vga_r = Signal(8)
            vga_g = Signal(8)
            vga_b = Signal(8)
            vga_hsync = Signal()
            vga_vsync = Signal()
            vga_blank = Signal()

            m.submodules.vga = vga = VGA(
                resolution_x      = self.timing.x,
                hsync_front_porch = hsync_front_porch,
                hsync_pulse       = hsync_pulse_width,
                hsync_back_porch  = hsync_back_porch,
                resolution_y      = self.timing.y,
                vsync_front_porch = vsync_front_porch,
                vsync_pulse       = vsync_pulse_width,
                vsync_back_porch  = vsync_back_porch,
                bits_x            = 16, # Play around with the sizes because sometimes
                bits_y            = 16  # a smaller/larger value will make it pass timing.
            )
            with m.If(vga.o_beam_y < 240):
                m.d.comb += [
                    vga.i_r.eq(0xff),
                    vga.i_g.eq(0),
                    vga.i_b.eq(0)
                ]
            with m.Else():
                m.d.comb += [
                    vga.i_r.eq(0),
                    vga.i_g.eq(0xff),
                    vga.i_b.eq(0)
                ]
            m.d.comb += [
                vga.i_clk_en.eq(1),
                vga.i_test_picture.eq(0),
                vga_r.eq(vga.o_vga_r),
                vga_g.eq(vga.o_vga_g),
                vga_b.eq(vga.o_vga_b),
                vga_hsync.eq(vga.o_vga_hsync),
                vga_vsync.eq(vga.o_vga_vsync),
                vga_blank.eq(vga.o_vga_blank),
            ]

            vga_out = platform.request("vga")

            m.d.comb += [
                vga_out.red.eq(vga_r[4:]),
                vga_out.green.eq(vga_g[4:]),
                vga_out.blue.eq(vga_b[4:]),
                vga_out.hs.eq(vga_hsync),
                vga_out.vs.eq(vga_vsync)
            ]

            # LED blinky
            counter_width = 28
            countblink = Signal(8)
            m.submodules.blink = blink = Blink(counter_width)
            m.d.comb += [
                countblink.eq(blink.o_led),
                self.o_led[3:5].eq(countblink[6:8]),
                self.o_led[0].eq(vga_vsync),
                self.o_led[1].eq(vga_hsync),
                self.o_led[2].eq(vga_blank),
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
    platform.add_resources(vga_pmod)

    m = Module()
    m.submodules.top = top = TopVGATest(timing=vga_timings['640x480@60Hz'])

    leds = [platform.request("led", i) for i in range(5)]

    for i in range(len(leds)):
        m.d.comb += leds[i].eq(top.o_led[i])

    platform.build(m, do_program=True, nextpnr_opts="--timing-allow-fail")

