from nmigen import *

class Osd(Elaboratable):
    def __init__(self, x_start=128, x_stop=383, y_start=128, y_stop=383):
        #parameters
        self.x_start = x_start
        self.x_stop  = x_stop
        self.y_start = y_start
        self.y_stop  = y_stop

        # inputs
        self.clk_ena   = Signal()
        self.i_r       = Signal(8)
        self.i_g       = Signal(8)
        self.i_b       = Signal(8)
        self.i_vsync   = Signal()
        self.i_hsync   = Signal()
        self.i_blank   = Signal()
        self.i_osd_ena = Signal()
        self.i_osd_r   = Signal(8)
        self.i_osd_g   = Signal(8)
        self.i_osd_b   = Signal(8)

        # outputs
        self.o_r       = Signal(8)
        self.o_g       = Signal(8)
        self.o_b       = Signal(8)
        self.o_osd_x   = Signal(10)
        self.o_osd_y   = Signal(10)
        self.o_vsync   = Signal()
        self.o_hsync   = Signal()
        self.o_blank   = Signal()

    def elaborate(self, platform):
        m = Module()

        r_osd_x      = Signal(10)
        r_osd_y      = Signal(10)
        r_x_count    = Signal(10)
        r_y_count    = Signal(10)
        r_x_en       = Signal()
        r_y_en       = Signal()
        r_hsync_prev = Signal()
        osd_en       = Signal()
        osd_x_en     = Signal()
        osd_y_en     = Signal()

        m.d.comb += [
            self.o_osd_x.eq(r_osd_x),
            self.o_osd_y.eq(r_osd_y)
        ]

        with m.If(self.clk_ena):
            with m.If(self.i_vsync):
                m.d.pixel += [
                    r_y_count.eq(0),
                    r_y_en.eq(0)
                ]
            with m.Else():
                with m.If(~self.i_blank):
                    m.d.pixel += r_y_en.eq(1)
                with m.If(~r_hsync_prev & self.i_hsync):
                    m.d.pixel += [
                        r_x_count.eq(0),
                        r_y_count.eq(0)
                    ]
                    with m.If(r_y_en):
                        m.d.pixel += r_y_count.eq(r_y_count + 1)
                    with m.If(r_y_count == self.y_start):
                        m.d.pixel += [
                            osd_y_en.eq(1),
                            r_osd_y.eq(0)
                        ]
                    with m.If(osd_y_en):
                        m.d.pixel += r_osd_y.eq(r_osd_y + 1)
                    with m.If(r_y_count == self.y_stop):
                        m.d.pixel += osd_y_en.eq(0)
                with m.Else():
                    with m.If(~self.i_blank):
                        m.d.pixel += r_x_en.eq(1)
                    with m.If(r_x_en):
                        m.d.pixel += r_x_count.eq(r_x_count + 1)
                    with m.If(r_x_count == self.x_start):
                        m.d.pixel += [
                            osd_x_en.eq(1),
                            r_osd_x.eq(0)
                        ]
                    with m.If(osd_x_en):
                        m.d.pixel += r_osd_x.eq(r_osd_x + 1)
                    with m.If(r_x_count == self.x_stop):
                        m.d.pixel += osd_x_en.eq(0)
                m.d.pixel += r_hsync_prev.eq(self.i_hsync)
            m.d.pixel += osd_en.eq(osd_x_en & osd_y_en)

        r_vga_r = Signal(8)
        r_vga_g = Signal(8)
        r_vga_b = Signal(8)

        r_hsync = Signal()
        r_vsync = Signal()
        r_blank = Signal()

        m.d.comb += [
            self.o_r.eq(r_vga_r),
            self.o_g.eq(r_vga_g),
            self.o_b.eq(r_vga_b),
            self.o_hsync.eq(r_hsync),
            self.o_vsync.eq(r_vsync),
            self.o_blank.eq(r_blank)
        ]

        with m.If(self.clk_ena):
            with m.If(osd_en & self.i_osd_ena):
                m.d.pixel += [
                    r_vga_r.eq(self.i_osd_r),
                    r_vga_g.eq(self.i_osd_g),
                    r_vga_r.eq(self.i_osd_b),
                ]
            with m.Else():
                m.d.pixel += [
                    r_vga_r.eq(self.i_r),
                    r_vga_g.eq(self.i_g),
                    r_vga_r.eq(self.i_b),
                ]
            m.d.pixel += [
                r_hsync.eq(self.i_hsync),
                r_vsync.eq(self.i_vsync),
                r_blank.eq(self.i_blank),
            ]

        return m

