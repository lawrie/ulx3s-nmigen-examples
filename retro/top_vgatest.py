import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from vga2dvid import VGA2DVID
from vga import VGA
from vga_timings import *
from ecp5pll import ECP5PLL

from spi_osd import SpiOsd
from spi_ram_btn import SpiRamBtn

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

class Top(Elaboratable):
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

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        if platform:
            clk_in = platform.request(platform.default_clk, dir='-')[0]
            leds = Cat([platform.request("led", i) for i in range(8)])
            btn = Cat([platform.request("button",i) for i in range(6)])
            pwr = platform.request("button_pwr")
            esp32 = platform.request("esp32_spi")
            csn = esp32.csn
            sclk = esp32.sclk
            copi = esp32.copi
            cipo = esp32.cipo
            irq  = esp32.irq

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
            m.domains.shift = cd_shift = ClockDomain("shift")

            m.submodules.ecp5pll = pll = ECP5PLL()
            pll.register_clkin(clk_in,  platform.default_clk_frequency)
            pll.create_clkout(cd_sync,  platform.default_clk_frequency)
            pll.create_clkout(cd_pixel, pixel_f)
            pll.create_clkout(cd_shift, pixel_f * 5.0 * (1.0 if self.ddr else 2.0))

            platform.add_clock_constraint(cd_sync.clk,  platform.default_clk_frequency)
            platform.add_clock_constraint(cd_pixel.clk, pixel_f)
            platform.add_clock_constraint(cd_shift.clk, pixel_f * 5.0 * (1.0 if self.ddr else 2.0))

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

            #SpiRamBtn

            m.submodules.rambtn = rambtn = SpiRamBtn()

            m.d.comb += [
                # Connect rambtn
                rambtn.csn.eq(~csn),
                rambtn.sclk.eq(sclk),
                rambtn.copi.eq(copi),
                rambtn.btn.eq(Cat(~pwr,btn)),
                cipo.eq(rambtn.cipo),
                irq.eq(~rambtn.irq)
            ]

            # OSD
            m.submodules.osd = osd = SpiOsd(start_x=62, start_y=80, chars_x=64, chars_y=20)

            m.d.comb += [
                # Connect osd
                osd.i_csn.eq(~csn),
                osd.i_sclk.eq(sclk),
                osd.i_copi.eq(copi),
                osd.clk_ena.eq(1),
                osd.i_hsync.eq(vga.o_vga_hsync),
                osd.i_vsync.eq(vga.o_vga_vsync),
                osd.i_blank.eq(vga.o_vga_blank),
                # led diagnostics
                #leds.eq(Cat([csn, sclk, copi, cipo, irq, rambtn.rd, rambtn.wr, osd.o_osd_en]))
                leds.eq(osd.diag)
            ]
            
            with m.If(vga.o_beam_y < 240):
                m.d.comb += [
                    osd.i_r.eq(0xff),
                    osd.i_g.eq(0),
                    osd.i_b.eq(0)
                ]
            with m.Else():
                m.d.comb += [
                    osd.i_r.eq(0),
                    osd.i_g.eq(0xff),
                    osd.i_b.eq(0)
                ]

            m.d.comb += [
                vga.i_clk_en.eq(1),
                vga.i_test_picture.eq(0),
                vga_r.eq(osd.o_r),
                vga_g.eq(osd.o_g),
                vga_b.eq(osd.o_b),
                vga_hsync.eq(osd.o_hsync),
                vga_vsync.eq(osd.o_vsync),
                vga_blank.eq(osd.o_blank),
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

    # Add the GPDI resource defined above to the platform so we
    # can reference it below.
    platform.add_resources(gpdi_resource)
    platform.add_resources(esp32_spi)

    m = Module()
    m.submodules.top = top = Top(timing=vga_timings['640x480@60Hz'])

    # The dir='-' is required because else nmigen will instantiate
    # differential pair buffers for us. Since we instantiate ODDRX1F
    # by hand, we do not want this, and dir='-' gives us access to the
    # _p signal.
    gpdi = [platform.request("gpdi", i, dir='-') for i in range(4)]    

    for i in range(len(gpdi)):
        m.d.comb += gpdi[i].p.eq(top.o_gpdi_dp[i])

    platform.build(m, do_program=True, nextpnr_opts="--timing-allow-fail")
