from nmigen import *

from readhex import readhex
from readbin import readbin
from spimem import SpiMem
from osd import Osd

class SpiOsd(Elaboratable):
    def __init__(self, addr_enable=0xfe, addr_display=0xFd,
                       start_x=64, start_y=48, chars_x=64, chars_y=24,
                       init_on=1, inverse=1, char_file="osd.mem",
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

    def elaborate(self, platform):
        m = Module()

        # Read in the tilemap
        tile_map = readhex(self.char_file)

        tile_data = Memory(width=8 + self.inverse, depth = len(tile_map))

        tile_data.init = tile_map

        m.submodules.tr = tr = tile_data.read_port()
        m.submodules.tw = tw = tile_data.write_port()

        # Read in the font
        font = readbin(self.font_file)

        font_data = Memory(width=8, depth=4096)

        font_data.init = font

        m.submodules.fr = fr = font_data.read_port()

        ram_wr     = Signal()
        ram_addr   = Signal(32)
        ram_di     = Signal(8)
        ram_do     = Signal(8)
        osd_en     = Signal(reset=self.init_on)
        osd_x      = Signal(10)
        osd_y      = Signal(10)
        dout       = Signal(8)
        tile_addr  = Signal(12)
        dout_align = Signal()
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
            spimem.din.eq(ram_di),
            self.o_cipo.eq(spimem.cipo),
            ram_do.eq(spimem.dout),
            ram_addr.eq(spimem.addr),
            ram_wr.eq(spimem.wr),
            # Connect tilemap
            tw.addr.eq(ram_addr),
            tw.en.eq(ram_wr & ram_addr[24:] == self.addr_display),
            tw.data.eq(Mux(self.inverse,Cat(ram_di, ram_addr[16]), ram_di)),
        ]

        with m.If(ram_wr & ram_addr[24:] == self.addr_enable):
            m.d.pixel += osd_en.eq(ram_di[0])

        m.d.comb += [
            tile_addr.eq((osd_y >> 4) * self.chars_y + (osd_x >> 3)),
            fr.data.eq(dout)
        ]

        if (self.inverse):
            m.d.comb += fr.addr.eq(Cat(osd_y[4], tr.data) ^ Repl(tr.data[8],8))
        else:
            m.d.comb += fr.addr.eq(Cat(osd_y[:4], tr.data))

        m.submodules.osd = osd = Osd(x_start=self.start_x, x_stop=self.start_x + (8 * self.chars_x) - 1,
                                     y_start=self.start_y, y_stop=self.start_y + (8 * self.chars_y) - 1)

        m.d.comb += [
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
            osd_r.eq(osd.o_r),
            osd_g.eq(osd.o_g),
            osd_b.eq(osd.o_b),
            self.o_hsync.eq(osd.o_hsync),
            self.o_vsync.eq(osd.o_vsync),
            self.o_blank.eq(osd.o_blank)
        ]

        return m

