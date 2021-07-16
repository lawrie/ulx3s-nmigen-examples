import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from nmigen.lib.fifo import SyncFIFOBuffered

from camread import *
from camconfig import *
from image_conv import ImageConv
from debouncer import *

from vga2dvid import VGA2DVID
from vga import VGA
from vga_timings import *
from ecp5pll import ECP5PLL
from osd import OSD

# The GPDI pins are not defined in the ULX3S platform in nmigen_boards. I've created a
# pull request, so until it is accepted and merged, we can define it here and add to
# the platform ourselves.
gpdi_resource = [
    # GPDI
    Resource("gpdi",     0, DiffPairs("A16", "B16"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi",     1, DiffPairs("A14", "C14"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi",     2, DiffPairs("A12", "A13"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi",     3, DiffPairs("A17", "B18"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi_eth", 0, DiffPairs("A19", "B20"), Attrs(IO_TYPE="LVCMOS33D", DRIVE="4")),
    Resource("gpdi_cec", 0, Pins("A18"),             Attrs(IO_TYPE="LVCMOS33",  DRIVE="4", PULLMODE="UP")),
    Resource("gpdi_sda", 0, Pins("B19"),             Attrs(IO_TYPE="LVCMOS33",  DRIVE="4", PULLMODE="UP")),
    Resource("gpdi_scl", 0, Pins("E12"),             Attrs(IO_TYPE="LVCMOS33",  DRIVE="4", PULLMODE="UP")),
]

# Ulx3s OV7670 extended Pmod
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

# Digilent 8LD Pmod
pmod_led8_2 = [
    Resource("led8_2", 0,
        Subsignal("leds", Pins("21+ 22+ 23+ 24+ 21- 22- 23- 24-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

# Digilent 8LD Pmod
pmod_led8_3 = [
    Resource("led8_3", 0,
        Subsignal("leds", Pins("14+ 15+ 16+ 17+ 14- 15- 16- 17-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

# Camera application with image processing
class Camera(Elaboratable):
    def __init__(self,
                 timing: VGATiming, # VGATiming class
                 xadjustf=0, # adjust -3..3 if no picture
                 yadjustf=0, # or to fine-tune f
                 ddr=True): # False: SDR, True: DDR
        self.o_gpdi_dp = Signal(4)
        # Configuration
        self.timing = timing
        self.x = timing.x
        self.y = timing.y
        self.f = timing.pixel_freq
        self.xadjustf = xadjustf
        self.yadjustf = yadjustf
        self.ddr = ddr

    def elaborate(self, platform):
        # Constants
        pixel_f           = self.timing.pixel_freq
        hsync_front_porch = self.timing.h_front_porch
        hsync_pulse_width = self.timing.h_sync_pulse
        hsync_back_porch  = self.timing.h_back_porch
        vsync_front_porch = self.timing.v_front_porch
        vsync_pulse_width = self.timing.v_sync_pulse
        vsync_back_porch  = self.timing.v_back_porch

        # Pins
        clk25   = platform.request("clk25")
        ov7670  = platform.request("ov7670")
        led     = [platform.request("led", i) for i in range(8)]
        leds    = Cat([i.o for i in led])
        led8_2  = platform.request("led8_2")
        leds8_2 = Cat([led8_2.leds[i] for i in range(8)])
        led8_3  = platform.request("led8_3")
        leds8_3 = Cat([led8_3.leds[i] for i in range(8)])
        leds16  = Cat(leds8_3, leds8_2)
        btn1    = platform.request("button_fire", 0)
        btn2    = platform.request("button_fire", 1)
        up      = platform.request("button_up", 0)
        down    = platform.request("button_down", 0)
        pwr     = platform.request("button_pwr", 0)
        left    = platform.request("button_left", 0)
        right   = platform.request("button_right", 0)
        sw      =  Cat([platform.request("switch",i) for i in range(4)])

        m = Module()
        
        # Clock generator.
        m.domains.sync  = cd_sync  = ClockDomain("sync")
        m.domains.pixel = cd_pixel = ClockDomain("pixel")
        m.domains.shift = cd_shift = ClockDomain("shift")

        m.submodules.ecp5pll = pll = ECP5PLL()
        pll.register_clkin(clk25,  platform.default_clk_frequency)
        pll.create_clkout(cd_sync,  platform.default_clk_frequency)
        pll.create_clkout(cd_pixel, pixel_f)
        pll.create_clkout(cd_shift, pixel_f * 5.0 * (1.0 if self.ddr else 2.0))

        # Add CamRead submodule
        camread = CamRead()
        m.submodules.camread = camread

        # Camera config
        camconfig = CamConfig()
        m.submodules.camconfig = camconfig

        # Configure and read the camera
        m.d.comb += [
            ov7670.cam_RESET.eq(1),
            ov7670.cam_PWON.eq(0),
            ov7670.cam_XCLK.eq(clk25.i),
            ov7670.cam_SIOC.eq(camconfig.sioc),
            ov7670.cam_SIOD.eq(camconfig.siod),
            camconfig.start.eq(btn1),
            camread.p_data.eq(Cat([ov7670.cam_data[i] for i in range(8)])),
            camread.href.eq(ov7670.cam_HREF),
            camread.vsync.eq(ov7670.cam_VSYNC),
            camread.p_clock.eq(ov7670.cam_PCLK)
        ]

        # Input fifo
        m.submodules.fifo = fifo = SyncFIFOBuffered(width=16,depth=1024)

        # Frame buffer
        buffer = Memory(width=16, depth=320 * 480)
        m.submodules.r = r = buffer.read_port()
        m.submodules.w = w = buffer.write_port()

        # Buttons 
        m.submodules.debup = debup = Debouncer()
        m.submodules.debdown = debdown = Debouncer()
        m.submodules.debres = debres = Debouncer()
        m.submodules.debosd = debosd = Debouncer()
        m.submodules.debsel = debsel = Debouncer()
        m.submodules.debsnap = debsnap = Debouncer()

        m.d.comb += [
            debup.btn.eq(up),
            debdown.btn.eq(down),
            debres.btn.eq(btn2),
            debosd.btn.eq(pwr),
            debsel.btn.eq(right),
            debsnap.btn.eq(left)
        ]

        # Image processing options
        x_flip   = Signal(reset=1)
        y_flip   = Signal(reset=0)
        mono     = Signal(reset=0)
        invert   = Signal(reset=0)
        gamma    = Signal(reset=0)
        border   = Signal(reset=1)
        grid     = Signal(reset=0)

        brightness  = Signal(signed(7), reset=0)
        redness     = Signal(unsigned(7), reset=18)
        greenness   = Signal(unsigned(7), reset=12)
        blueness    = Signal(unsigned(7), reset=16)
        sharpness   = Signal(unsigned(4), reset=0)

        osd_val = Signal(4)
        osd_on = Signal()
        osd_sel = Signal()
        snap    = Signal()
        frozen  = Signal()

        with m.If(debosd.btn_down):
            m.d.sync += osd_on.eq(~osd_on)
        with m.If(debsel.btn_down):
            m.d.sync += osd_sel.eq(~osd_sel)

        with m.If(debsnap.btn_down):
            m.d.sync += [
                snap.eq(~snap),
                frozen.eq(0)
            ]

        # OSD control
        with m.If(debup.btn_down):
            with m.If(osd_on & ~osd_sel):
                m.d.sync += osd_val.eq(Mux(osd_val == 0, 11, osd_val-1))
            with m.Elif(osd_sel):
                with m.Switch(osd_val):
                    with m.Case(0): # brightness
                        m.d.sync += brightness.eq(brightness+1)
                    with m.Case(1): # redness
                        m.d.sync += redness.eq(redness+1)
                    with m.Case(2): # greenness
                        m.d.sync += greenness.eq(greenness+1)
                    with m.Case(3): # blueness
                        m.d.sync += blueness.eq(blueness+1)
                    with m.Case(4): # mono
                        m.d.sync += mono.eq(1)
                    with m.Case(5): # x flip
                        m.d.sync += x_flip.eq(1)
                    with m.Case(6): # y flip
                        m.d.sync += y_flip.eq(1)
                    with m.Case(7): # border
                        m.d.sync += border.eq(1)
                    with m.Case(8): # sharpness
                        m.d.sync += sharpness.eq(sharpness+1)
                    with m.Case(9): # invert
                        m.d.sync += invert.eq(1)
                    with m.Case(10): # grid
                        m.d.sync += grid.eq(1)
                    with m.Case(11): # filter
                        m.d.sync += []

        with m.If(debdown.btn_down):
            with m.If(osd_on & ~osd_sel):
                m.d.sync += osd_val.eq(Mux(osd_val == 11, 0, osd_val+1))
            with m.Elif(osd_sel):
                with m.Switch(osd_val):
                    with m.Case(0): # brightness
                        m.d.sync += brightness.eq(brightness-1)
                    with m.Case(1): # redness
                        m.d.sync += redness.eq(redness-1)
                    with m.Case(2): # greenness
                        m.d.sync += greenness.eq(greenness-1)
                    with m.Case(3): # blueness
                        m.d.sync += blueness.eq(blueness-1)
                    with m.Case(4): # mono
                        m.d.sync += mono.eq(0)
                    with m.Case(5): # x flip
                        m.d.sync += x_flip.eq(0)
                    with m.Case(6): # y flip
                        m.d.sync += y_flip.eq(0)
                    with m.Case(7): # border
                        m.d.sync += border.eq(0)
                    with m.Case(8): # sharpness
                        m.d.sync += sharpness.eq(sharpness-1)
                    with m.Case(9): # invert
                        m.d.sync += invert.eq(0)
                    with m.Case(10): # grid
                        m.d.sync += grid.eq(0)
                    with m.Case(11): # filter
                        m.d.sync += []

        # Image global stats
        max_r = Signal(5)
        max_g = Signal(6)
        max_b = Signal(5)

        avg_r = Signal(21)
        avg_g = Signal(22)
        avg_b = Signal(21)

        a_r   = Signal(5)
        a_g   = Signal(6)
        a_b   = Signal(5)

        frames = Signal(6)

        # Image convolution
        m.submodules.ims = ims = ImageConv()

        p_r = Signal(9)
        p_g = Signal(10)
        p_b = Signal(9)
        
        # Sync the fifo with the camera
        sync_fifo = Signal(reset=0)
        with m.If((camread.col == 639) & (camread.row == 0)):
            m.d.sync += sync_fifo.eq(1)

        # Connect fifo and ims
        m.d.comb += [
            fifo.w_en.eq(camread.pixel_valid & camread.col[0] & sync_fifo), # Only write every other pixel
            fifo.w_data.eq(camread.pixel_data), 
            fifo.r_en.eq(fifo.r_rdy & ~ims.o_stall),
            ims.i_valid.eq(fifo.r_rdy),
            p_r.eq(fifo.r_data[11:] * (redness + brightness)),
            ims.i_r.eq(p_r[4:]),
            p_g.eq(fifo.r_data[5:11] * (greenness + brightness)),
            ims.i_g.eq(p_g[4:]),
            p_b.eq(fifo.r_data[0:5] * (blueness + brightness)),
            ims.i_b.eq(p_b[4:]),
            ims.sel.eq(sharpness),
            ims.x_flip.eq(x_flip),
            ims.y_flip.eq(y_flip),
            ims.mono.eq(mono),
            ims.invert.eq(invert),
            ims.avg_r.eq(a_r),
            ims.avg_g.eq(a_g),
            ims.avg_b.eq(a_b)
        ]

        # Take a snapshot
        with m.If(ims.frame_done & snap):
            m.d.sync += frozen.eq(1)

        # Calculate maximum for each color, each frame
        with m.If(ims.i_r > max_r):
            m.d.sync += max_r.eq(ims.i_r) 
        with m.If(ims.i_g > max_g):
            m.d.sync += max_g.eq(ims.i_g) 
        with m.If(ims.i_b > max_b):
            m.d.sync += max_b.eq(ims.i_b) 

        # Calculate average looking at middle 256 x 256 pixels
        with m.If(camread.col[0] & camread.pixel_valid):
            with m.If((camread.col[1:] >= 32) & (camread.col[1:] < 288) & 
                      (camread.row >= 112) & (camread.row < 368)):
                m.d.sync += [
                    avg_r.eq(avg_r + ims.i_r),
                    avg_g.eq(avg_g + ims.i_g),
                    avg_b.eq(avg_b + ims.i_b)
                ]

        with m.If(camread.frame_done):
            m.d.sync += [
                frames.eq(frames+1),
                max_r.eq(0),
                max_g.eq(0),
                max_b.eq(0),
                avg_r.eq(0),
                avg_g.eq(0),
                avg_b.eq(0),
                a_r.eq(avg_r[16:]),
                a_g.eq(avg_g[16:]),
                a_b.eq(avg_b[16:]),
            ]
            with m.If(frames == 0):
                m.d.sync += leds16.eq(Cat([avg_b[16:],avg_g[16:],avg_r[16:]]))

        # Show value on leds
        m.d.comb += leds.eq(osd_val)

        # VGA signal generator.
        vga_r = Signal(8)
        vga_g = Signal(8)
        vga_b = Signal(8)
        vga_hsync = Signal()
        vga_vsync = Signal()
        vga_blank = Signal()

        # Add VGA generator
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

        # Connect frame buffer
        m.d.comb += [
            w.en.eq(ims.o_valid & ~frozen),
            w.addr.eq(ims.o_y * 320 + ims.o_x),
            w.data.eq(Cat(ims.o_b, ims.o_g, ims.o_r)),
            r.addr.eq(vga.o_beam_y * 320 + vga.o_beam_x[1:])
        ]

        # OSD
        m.submodules.osd = osd = OSD()

        m.d.comb += [
            osd.x.eq(vga.o_beam_x),
            osd.y.eq(vga.o_beam_y),
            osd.i_r.eq(Cat(Const(0, unsigned(3)), r.data[11:16])),
            osd.i_g.eq(Cat(Const(0, unsigned(2)), r.data[5:11])),
            osd.i_b.eq(Cat(Const(0, unsigned(3)), r.data[0:5])),
            osd.on.eq(osd_on),
            osd.osd_val.eq(osd_val),
            osd.sel.eq(osd_sel),
            osd.grid.eq(grid),
            osd.border.eq(border)
        ]

        # Generate VGA signals
        m.d.comb += [
            vga.i_clk_en.eq(1),
            vga.i_test_picture.eq(0),
            vga.i_r.eq(osd.o_r), 
            vga.i_g.eq(osd.o_g), 
            vga.i_b.eq(osd.o_b), 
            vga_r.eq(vga.o_vga_r),
            vga_g.eq(vga.o_vga_g),
            vga_b.eq(vga.o_vga_b),
            vga_hsync.eq(vga.o_vga_hsync),
            vga_vsync.eq(vga.o_vga_vsync),
            vga_blank.eq(vga.o_vga_blank),
        ]

        # VGA to digital video converter.
        tmds = [Signal(2) for i in range(4)]
        m.submodules.vga2dvid = vga2dvid = VGA2DVID(ddr=self.ddr, shift_clock_synchronizer=False)
        m.d.comb += [
            vga2dvid.i_red.eq(vga_r),
            vga2dvid.i_green.eq(vga_g),
            vga2dvid.i_blue.eq(vga_b),
            vga2dvid.i_hsync.eq(vga_hsync),
            vga2dvid.i_vsync.eq(vga_vsync),
            vga2dvid.i_blank.eq(vga_blank),
            tmds[3].eq(vga2dvid.o_clk),
            tmds[2].eq(vga2dvid.o_red),
            tmds[1].eq(vga2dvid.o_green),
            tmds[0].eq(vga2dvid.o_blue),
        ]

        if (self.ddr):
            # Vendor specific DDR modules.
            # Convert SDR 2-bit input to DDR clocked 1-bit output (single-ended)
            # onboard GPDI.
            m.submodules.ddr0_clock = Instance("ODDRX1F",
                i_SCLK = ClockSignal("shift"),
                i_RST  = 0b0,
                i_D0   = tmds[3][0],
                i_D1   = tmds[3][1],
                o_Q    = self.o_gpdi_dp[3])
            m.submodules.ddr0_red   = Instance("ODDRX1F",
                i_SCLK = ClockSignal("shift"),
                i_RST  = 0b0,
                i_D0   = tmds[2][0],
                i_D1   = tmds[2][1],
                o_Q    = self.o_gpdi_dp[2])
            m.submodules.ddr0_green = Instance("ODDRX1F",
                i_SCLK = ClockSignal("shift"),
                i_RST  = 0b0,
                i_D0   = tmds[1][0],
                i_D1   = tmds[1][1],
                o_Q    = self.o_gpdi_dp[1])
            m.submodules.ddr0_blue  = Instance("ODDRX1F",
                i_SCLK = ClockSignal("shift"),
                i_RST  = 0b0,
                i_D0   = tmds[0][0],
                i_D1   = tmds[0][1],
                o_Q    = self.o_gpdi_dp[0])
        else:
            m.d.comb += [
                self.o_gpdi_dp[3].eq(tmds[3][0]),
                self.o_gpdi_dp[2].eq(tmds[2][0]),
                self.o_gpdi_dp[1].eq(tmds[1][0]),
                self.o_gpdi_dp[0].eq(tmds[0][0]),
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

    m = Module()

    # Add the top module
    m.submodules.top = top = Camera(timing=vga_timings['640x480@60Hz'])

    # Add OV7670 and LED Pmod resurces
    platform.add_resources(ov7670_pmod)
    platform.add_resources(pmod_led8_2)
    platform.add_resources(pmod_led8_3)

    # Add the GPDI resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(gpdi_resource)

    # The dir='-' is required because else nmigen will instantiate
    # differential pair buffers for us. Since we instantiate ODDRX1F
    # by hand, we do not want this, and dir='-' gives us access to the
    # _p signal.
    gpdi = [platform.request("gpdi", 0, dir='-'),
            platform.request("gpdi", 1, dir='-'),
            platform.request("gpdi", 2, dir='-'),
            platform.request("gpdi", 3, dir='-')]

    for i in range(len(gpdi)):
        m.d.comb += gpdi[i].p.eq(top.o_gpdi_dp[i])

    platform.build(m, do_program=True)
