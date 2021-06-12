from nmigen import *

from readhex import readhex
from readbin import readbin
from spimem import SpiMem
from osd import Osd

class SpiOsd(Elaboratable):
    def __init__(self, addr_enable=0xfe, addr_display=0xFd,
                       start_x=64, start_y=48, chars_x=64, chars_y=24,
                       init_on=0, inverse=0, char_file="osd.mem",
                       font_file="font_bizcat8x16.mem"):
        #parameters
        self.addr_enable  = addr_enable
        self.addr_display = addr_display
        self.start_x      = start_x
        self.chars_x      = chars_x
        self.start_y      = start_y
        self.chars_y      = chars_y
        self.init_on      = init_on
        self.inverse      = inverse
        self.char_file    = char_file
        self.font_file    = font_file

        # inputs
        self.clk_ena   = Signal()
        self.i_r       = Signal(8)
        self.i_g       = Signal(8)
        self.i_b       = Signal(8)
        self.i_vsync   = Signal()
        self.i_hsync   = Signal()
        self.i_blank   = Signal()

        self.i_csn     = Signal()
        self.i_sclk    = Signal()
        self.i_copi    = Signal()

        # outputs
        self.o_cipo    = Signal()
        self.o_r       = Signal(8)
        self.o_g       = Signal(8)
        self.o_b       = Signal(8)
        self.o_vsync   = Signal()
        self.o_hsync   = Signal()
        self.o_blank   = Signal()

        # Diagnostics
        self.diag      = Signal(8)

    def elaborate(self, platform):
        m = Module()

        # Read in the tilemap
        tile_map = readhex(self.char_file)

        tile_data = Memory(width=8 + self.inverse, depth=self.chars_x * self.chars_y, init=tile_map)

        m.submodules.tr = tr = tile_data.read_port(domain="pixel")
        m.submodules.tw = tw = tile_data.write_port(domain="pixel")

        # Read in the font
        font = readbin(self.font_file)

        font_data = Memory(width=8, depth=4096, init=font)

        m.submodules.fr = fr = font_data.read_port(domain="pixel")

        ram_wr     = Signal()
        ram_addr   = Signal(32)
        ram_di     = Signal(8)
        osd_en     = Signal(reset=self.init_on)
        osd_x      = Signal(10)
        osd_y      = Signal(10)
        dout       = Signal(8)
        tile_addr  = Signal(12)
        dout_align = Signal(8)
        osd_pixel  = Signal()
        osd_r      = Signal(8)
        osd_g      = Signal(8)
        osd_b      = Signal(8)

        m.submodules.spimem = spimem = SpiMem(addr_bits=32)

        m.d.comb += [
            # Connect spimem
            spimem.csn.eq(self.i_csn),
            spimem.sclk.eq(self.i_sclk),
            spimem.copi.eq(self.i_copi),
            #spimem.din.eq(ram_do),
            self.o_cipo.eq(spimem.cipo),
            ram_di.eq(spimem.dout),
            self.diag.eq(fr.addr),
            ram_addr.eq(spimem.addr),
            ram_wr.eq(spimem.wr),
            # Connect tilemap
            tw.addr.eq(ram_addr),
            tw.en.eq(ram_wr & (ram_addr[24:] == self.addr_display)),
            tw.data.eq(Mux(self.inverse,Cat(ram_di, ram_addr[16]), ram_di)),
            tr.addr.eq(tile_addr),
            tile_addr.eq((osd_y >> 4) * self.chars_x + ((osd_x + 1) >> 3)),
            dout.eq(fr.data)
        ]

        with m.If(ram_wr & (ram_addr[24:] == self.addr_enable)):
            m.d.pixel += osd_en.eq(ram_di[0])

        if (self.inverse):
            m.d.comb += fr.addr.eq(Cat(osd_y[4], tr.data) ^ Repl(tr.data[8],8))
        else:
            m.d.comb += fr.addr.eq(Cat(osd_y[:4], tr.data))

        m.submodules.osd = osd = Osd(x_start=self.start_x, x_stop=self.start_x + (8 * self.chars_x) - 1,
                                     y_start=self.start_y, y_stop=self.start_y + (16 * self.chars_y) - 1)

        m.d.comb += [
            dout_align.eq(Cat(dout[1:],dout[0])),
            osd_pixel.eq(dout_align.bit_select(7-osd_x[:3], 1)),
            osd_r.eq(Mux(osd_pixel, C(0xff,8), C(0x50,8))),
            osd_g.eq(Mux(osd_pixel, C(0xff,8), C(0x30,8))),
            osd_b.eq(Mux(osd_pixel, C(0xff,8), C(0x20,8))),
            osd.clk_ena.eq(1),
            osd.i_r.eq(self.i_r),
            osd.i_g.eq(self.i_g),
            osd.i_b.eq(self.i_b),
            osd.i_hsync.eq(self.i_hsync),
            osd.i_vsync.eq(self.i_vsync),
            osd.i_blank.eq(self.i_blank),
            osd.i_osd_ena.eq(osd_en),
            osd.i_osd_r.eq(osd_r),
            osd.i_osd_g.eq(osd_g),
            osd.i_osd_b.eq(osd_b),
            osd_x.eq(osd.o_osd_x),
            osd_y.eq(osd.o_osd_y),
            self.o_r.eq(osd.o_r),
            self.o_g.eq(osd.o_g),
            self.o_b.eq(osd.o_b),
            self.o_hsync.eq(osd.o_hsync),
            self.o_vsync.eq(osd.o_vsync),
            self.o_blank.eq(osd.o_blank)
        ]

        return m

