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
from ps2 import PS2
from core import Core
from readhex import readhex
from video import Video

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

# Pullup resistor for setting USB to PS/2 mode
ps2_pullup = [
    Resource("ps2_pullup", 0, Pins("C12", dir="o") , Attrs(IO_TYPE="LVCMOS33", DRIVE="16"))
]

stereo = [
    Resource("stereo", 0,
        Subsignal("l", Pins("E4 D3 C3 B3", dir="o")),
        Subsignal("r", Pins("A3 B5 D5 C5", dir="o")),
    )
]

# Diagnostic led Pmods
pmod_led8_0 = [
    Resource("led8_0", 0, 
        Subsignal("leds", Pins("0+ 1+ 2+ 3+ 0- 1- 2- 3-", dir="o", conn=("gpio",0))), 
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

pmod_led8_1 = [
    Resource("led8_1", 0, 
        Subsignal("leds", Pins("7+ 8+ 9+ 10+ 7- 8- 9- 10-", dir="o", conn=("gpio",0))), 
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
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

# Implements the APF M1000 Games console
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
            usb = platform.request("usb")
            ps2_pullup = platform.request("ps2_pullup")
            stereo  = platform.request("stereo", 0)
            led8_0 = platform.request("led8_0")
            leds8_0 = Cat([led8_0.leds[i] for i in range(8)])
            led8_1 = platform.request("led8_1")
            leds8_1 = Cat([led8_1.leds[i] for i in range(8)])
            leds16 = Cat(leds8_0, leds8_1)
            led8_2 = platform.request("led8_2")
            leds8_2 = Cat([led8_2.leds[i] for i in range(8)])
            led8_3 = platform.request("led8_3")
            leds8_3 = Cat([led8_3.leds[i] for i in range(8)])
            leds16_2 = Cat(leds8_3, leds8_2)

            esp32 = platform.request("esp32_spi")
            csn = esp32.csn
            sclk = esp32.sclk
            copi = esp32.copi
            cipo = esp32.cipo
            irq  = esp32.irq

            # Constants
            pixel_f           = self.timing.pixel_freq
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

            m.domains.ph1 = ph1 = ClockDomain("ph1")
            m.domains.ph2 = ph2 = ClockDomain("ph2")

            # CPU clock domains
            clk_freq = platform.default_clk_frequency
            timer    = Signal(range(0, int(7)),
                           reset=int(7 - 1))
            tick     = Signal()
            sync     = ClockDomain()


            cpu_control = Signal(8)
            spi_load    = Signal()
            pia_cra     = Signal(8)
            pia_dra     = Signal(8)
            pia_crb     = Signal(8)
            pia_drb     = Signal(8)
            r_btn       = Signal(6)

            m.d.sync += r_btn.eq(btn)

            with m.If(timer == 0):
                m.d.sync += timer.eq(timer.reset)
                m.d.sync += tick.eq(~tick)
            with m.Else():
                m.d.sync += timer.eq(timer - 1)
            m.d.comb += [
                ph1.rst.eq(sync.rst),
                ph2.rst.eq(sync.rst),
                ph1.clk.eq(tick),
                ph2.clk.eq(~tick),
            ]

            # Add CPU
            cpu = Core()
            m.submodules += cpu

            # VGA signal generator.
            vga_r = Signal(8)
            vga_g = Signal(8)
            vga_b = Signal(8)
            vga_hsync = Signal()
            vga_vsync = Signal()
            vga_blank = Signal()
            r_vsync   = Signal()

            # Save previous value of vsync
            m.d.sync += r_vsync.eq(vga_vsync)

            # Vsync sets IRQ
            with m.If(vga_vsync & ~r_vsync):
                m.d.sync += cpu.IRQ.eq(1)

            # Reading PIA Data Register B clears the interrupt
            with m.If(cpu.RW & (cpu.Addr == 0x2002)):
                m.d.sync += cpu.IRQ.eq(0)

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

            # Use 1Kb of RAM
            ram = Memory(width=8, depth=1024)
            m.submodules.dr = dr = ram.read_port()
            m.submodules.vr = vr = ram.read_port()
            m.submodules.dw = dw = ram.write_port()

            # And 2kb of ROM
            rom_data = readhex("roms/apf_4000.mem")

            rom = Memory(width=8, depth=2048, init=rom_data)
            m.submodules.rr = rr = rom.read_port()

            # And 8kb of cartridge rom
            cart = Memory(width=8, depth=8192)
            m.submodules.cr = cr = rom.read_port()
            m.submodules.cw = cw = rom.write_port()

            # Add SpiRamBtn for OSD control
            m.submodules.rambtn = rambtn = SpiRamBtn()

            # Add PS/2 keyboard controller
            m.submodules.ps2 = ps2 = PS2()

            # Add character rom and video controller
            font = readhex("roms/charrom.mem")

            charrom = Memory(width=8,depth=512, init=font)
            m.submodules.fr = fr = charrom.read_port()

            m.submodules.video = video = Video()

            m.d.comb += [
                # Connect rambtn
                rambtn.csn.eq(~csn),
                rambtn.sclk.eq(sclk),
                rambtn.copi.eq(copi),
                rambtn.btn.eq(Cat(~pwr,btn)),
                cipo.eq(rambtn.cipo),
                irq.eq(~rambtn.irq),
                # Connect memory
                dr.addr.eq(cpu.Addr),
                rambtn.din.eq(vr.data),
                cw.data.eq(rambtn.dout),
                cw.addr.eq(rambtn.addr),
                cw.en.eq(rambtn.wr & (rambtn.addr[24:] == 0)),
                rr.addr.eq(cpu.Addr),
                cpu.Din.eq(Mux(cpu.Addr == 0xffff, 0x00, Mux(cpu.Addr == 0xfffe, 0x40, # reset vector
                           Mux(cpu.Addr == 0xfff9, 0xA4, Mux(cpu.Addr == 0xfff8, 0x42, # irq vector
                           Mux(cpu.Addr[13:] == 0, dr.data, Mux(cpu.Addr[13:] == 2, rr.data, # ram or system rom
                           Mux(cpu.Addr[14:] == 1, cr.data,
                           Mux(cpu.Addr == 0x2002, pia_drb,
                           Mux(cpu.Addr == 0x2000,  # PIA_DRA has keyboard row
                               Mux(pia_drb[:4] == C(0b1110, 4), Cat([~r_btn[0], Repl(1,7)]), 
                               Mux(pia_drb[:4] == C(0b1101, 4), Cat([Repl(1,1), ~r_btn[5], Repl(1,1), ~r_btn[4], Repl(1,1), ~r_btn[5], Repl(1,1), ~r_btn[4]]),
                               Mux(pia_drb[:4] == C(0b1011, 4), Cat([Repl(1,8)]),
                               Mux(pia_drb[:4] == C(0b0111, 4), Cat([Repl(1,1), ~r_btn[2], Repl(1,2), ~r_btn[1:3], Repl(1,2)]), 0xff)))), 
                            0xff)))))))))),
                dw.addr.eq(cpu.Addr),
                dw.data.eq(cpu.Dout),
                dw.en.eq(~cpu.RW & cpu.VMA & (cpu.Addr[13:] == 0)),
                vr.addr.eq(Mux(spi_load, rambtn.addr, video.c_addr)),
                # PS/2 keyboard
                usb.pullup.eq(1),
                ps2_pullup.eq(1),
                ps2.ps2_clk.eq(usb.d_p),
                ps2.ps2_data.eq(usb.d_n),
                spi_load.eq(cpu_control[1]),
                stereo.r.eq(stereo.l)
            ]

            # CPU control from ESP32
            with m.If(rambtn.wr & (rambtn.addr[24:] == 0xFF)):
                m.d.sync += cpu_control.eq(rambtn.dout)

            # PIA control and data registers
            with m.If(~cpu.RW & cpu.VMA & cpu.Addr[13]):
                with m.Switch(cpu.Addr[:2]):
                    with m.Case(0):
                         m.d.sync += pia_dra.eq(cpu.Dout)
                    with m.Case(1):
                         m.d.sync += pia_cra.eq(cpu.Dout)
                    with m.Case(2):
                         m.d.sync += pia_drb.eq(cpu.Dout)
                    with m.Case(3):
                         m.d.sync += pia_crb.eq(cpu.Dout)
                         m.d.sync += stereo.l.eq(Mux(cpu.Dout[3], 0x7, 0x0))

            mode = Signal(2)

            with m.If(~cpu.RW & (cpu.Addr == 0x1fc) & (cpu.Dout != 0)):
                m.d.sync += mode.eq(0b11)

            # OSD
            m.submodules.osd = osd = SpiOsd(start_x=62, start_y=80, chars_x=64, chars_y=20)

            m.d.comb += [
                # Connect video
                video.x.eq(vga.o_beam_x),
                video.y.eq(vga.o_beam_y),
                video.din.eq(vr.data),
                video.fin.eq(fr.data),
                video.mode.eq(mode),
                fr.addr.eq(video.f_addr),
                # Connect osd
                osd.i_csn.eq(~csn),
                osd.i_sclk.eq(sclk),
                osd.i_copi.eq(copi),
                osd.clk_ena.eq(1),
                osd.i_hsync.eq(vga.o_vga_hsync),
                osd.i_vsync.eq(vga.o_vga_vsync),
                osd.i_blank.eq(vga.o_vga_blank),
                osd.i_r.eq(video.r),
                osd.i_g.eq(video.g),
                osd.i_b.eq(video.b),
                # led diagnostics
                leds.eq(pia_drb),
                leds16_2.eq(cpu.sp),
                leds16.eq(cpu.Addr)
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
    platform.add_resources(ps2_pullup)
    platform.add_resources(stereo)
    platform.add_resources(pmod_led8_0)
    platform.add_resources(pmod_led8_1)
    platform.add_resources(pmod_led8_2)
    platform.add_resources(pmod_led8_3)

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

