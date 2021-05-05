from nmigen import *
from nmigen.build import Platform

class ImageStream(Elaboratable):
    def __init__(self, res_x = 320, res_y = 480):
        self.res_x       = res_x
        self.res_y       = res_y
        self.valid       = Signal()
        self.i_x         = Signal(10)
        self.i_y         = Signal(10)
        self.i_r         = Signal(5)
        self.i_g         = Signal(6)
        self.i_b         = Signal(5)
        self.ready       = Signal(16)
        self.o_x         = Signal(10)
        self.o_y         = Signal(9)
        self.o_r         = Signal(5)
        self.o_g         = Signal(6)
        self.o_b         = Signal(5)
        self.val         = Signal(signed(7))
        self.edge        = Signal()
        self.x_flip      = Signal()
        self.y_flip     = Signal()
        self.bright      = Signal()
        self.red         = Signal()
        self.green       = Signal()
        self.blue        = Signal()
        self.mono        = Signal()
        self.invert      = Signal()
        self.threshold   = Signal()
        self.gamma       = Signal()
        self.filter      = Signal()
        self.border      = Signal()
        self.p_x         = Signal(10)
        self.p_y         = Signal(10)

    def elaborate(self, platform):
        m = Module()

        gamma32 = [0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 7,
                   8, 9, 10, 12, 13, 14, 16, 17, 19, 20, 22, 24, 25, 27, 29, 31]

        gamma64 = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 4,
                   4, 5, 5, 6, 6, 7, 8, 8, 9, 10, 11, 12, 12, 13, 14, 15,
                   16, 17, 18, 19, 21, 22, 23, 24, 25, 27, 28, 29, 31, 32, 34, 35,
                   37, 38, 40, 41, 43, 45, 46, 48, 50, 52, 53, 55, 57, 59, 61, 63]

        gr_tab = Memory(width=5, depth=32,init=gamma32)
        m.submodules.gr = gr = gr_tab.read_port()

        gg_tab = Memory(width=6, depth=64,init=gamma64)
        m.submodules.gg = gg = gg_tab.read_port()

        gb_tab = Memory(width=5, depth=32,init=gamma32)
        m.submodules.gb = gb = gb_tab.read_port()

        # Apply x_flip and yflip
        c_x = Signal(10)
        c_y = Signal(10)

        m.d.comb += [
            c_x.eq(Mux(self.x_flip, self.res_x - 1 - self.i_x, self.i_x)),
            c_y.eq(Mux(self.y_flip, self.res_y - 1 - self.i_y, self.i_y))
        ]

        # Line buffer
        buffer = Memory(width=16, depth=self.res_x * 3)
        m.submodules.r = r = buffer.read_port()
        m.submodules.w = w = buffer.write_port()

        cl = Signal(2, reset=0)
        pl = Signal(2, reset=2)
        ppl = Signal(2, reset=1)

        above = Signal(16)

        # Save current pixel
        p_r = Signal(5)
        p_g = Signal(6)
        p_r = Signal(5)

        # Sum of colors and previous sum
        s = Signal(7)
        p_s = Signal(7)

        m.d.comb += [
            s.eq(self.i_r + self.i_g + self.i_b)
        ]

        m.d.sync += [
            # Default ready to false
            self.ready.eq(0),
            p_s.eq(s)
        ]

        # When at end of line, update line pointers
        with m.If((c_x == self.res_x - 1) & (self.valid)):
            m.d.sync += [
                ppl.eq(pl),
                pl.eq(cl),
                cl.eq(Mux(cl == 2, 0, cl + 1))
            ]

        # Current pixel with optional convert to monochrome and optional invert
        c_r = Signal(5)
        c_g = Signal(6)
        c_b = Signal(5)

        with m.If(self.mono):
            m.d.comb += [
                c_r.eq(Mux(self.invert, 0x1f - s[2:], s[2:])),
                c_g.eq(Mux(self.invert, 0x3f - s[1:], s[1:])),
                c_b.eq(Mux(self.invert, 0x1f - s[2:], s[2:]))
            ]
        with m.Elif(self.filter):
            with m.If((self.i_r > self.val)):
                m.d.comb += [
                    c_r.eq(0x1f),
                    c_g.eq(0),
                    c_b.eq(0)
                ]
            with m.Else():
                m.d.comb += [
                    c_r.eq(0),
                    c_g.eq(0),
                    c_b.eq(0)
                ]
        with m.Else():
            m.d.comb += [
                c_r.eq(self.i_r),
                c_g.eq(self.i_g),
                c_b.eq(self.i_b)
            ]

        # Calculate laser mouse pointer
        min_x = Signal(10)
        max_x = Signal(10)
        min_y = Signal(10)
        max_y = Signal(10)

        with m.If((self.i_x == 0) & (self.i_y == 0)):
            m.d.sync += [
                min_x.eq(0),
                min_y.eq(0),
                max_x.eq(0),
                max_y.eq(0)
            ]

        with m.If(self.i_r > self.val):
            with m.If ((min_x == 0) | (c_x < min_x)):
                m.d.sync += min_x.eq(c_x)
            with m.If((max_x == 0) | (c_x > max_x)):
                m.d.sync += max_x.eq(c_x)
            with m.If((min_y == 0) | (c_y < min_y)):
                m.d.sync += min_y.eq(c_y)
            with m.If((max_y == 0) | (c_y > max_y)):
                m.d.sync += max_y.eq(c_y)

        m.d.comb += [
            self.p_x.eq(min_x + ((max_x - min_x) >> 1)),
            self.p_y.eq(min_y + ((max_y - min_y) >> 1))
        ]

        # Apply optional gamma correction
        g_r = Signal(5)
        g_g = Signal(6)
        g_b = Signal(5)

        m.d.comb += [
            gr.addr.eq(c_r),
            gg.addr.eq(c_g),
            gb.addr.eq(c_b),
        ]

        with m.If(self.gamma):
            m.d.comb += [
                g_r.eq(gr.data),
                g_g.eq(gg.data),
                g_b.eq(gb.data)
            ]
        with m.Else():
            m.d.comb += [
                g_r.eq(c_r),
                g_g.eq(c_g),
                g_b.eq(c_b)
            ]

        # New values with val added or subtracted
        n_r = Signal(signed(6))
        n_g = Signal(signed(7))
        n_b = Signal(signed(6))

        m.d.comb += [
            n_r.eq(g_r + self.val),
            n_g.eq(g_g + self.val),
            n_b.eq(g_b + self.val)
        ]

        # Process pixel when valid set, and set ready
        with m.If(self.valid):
            m.d.sync += [
                self.ready.eq(1),
                # Set output x and y with horizontal and vertical flip
                self.o_x.eq(c_x),
                self.o_y.eq(c_y),
                # Copy input pixel by default
                self.o_r.eq(g_r),
                self.o_g.eq(g_g),
                self.o_b.eq(g_b),
                # Write pixel to current line
                w.addr.eq(cl * self.res_x + c_x),
                w.data.eq(Cat(self.i_b, self.i_g, self.i_r)),
                # Get the pixel above the current one
                r.addr.eq(pl * self.res_x + c_x),
                above.eq(r.data)
            ]

            # Simple edge detection
            with m.If(self.edge):
                with m.If(((p_s > s) & ((p_s - s) > self.val)) | ((p_s < s) & ((s - p_s) > self.val))):
                    m.d.sync += [
                        self.o_r.eq(0x1f),
                        self.o_g.eq(0),
                        self.o_b.eq(0)
                    ]
                with m.Else():
                    m.d.sync += [
                        self.o_r.eq(0),
                        self.o_g.eq(0),
                        self.o_b.eq(0)
                    ]
            with m.Else():
            # Increase colors or total brightness
                with m.If(self.red | self.bright):
                    m.d.sync += [
                        self.o_r.eq(Mux(n_r > 0x1f, 0x1f, Mux(n_r < 0, 0, n_r)))
                    ]
                with m.If(self.green | self.bright):
                    m.d.sync += [
                        self.o_g.eq(Mux(n_g > 0x3f, 0x3f, Mux(n_g < 0, 0, n_g)))
                    ]
                with m.If(self.blue | self.bright):
                    m.d.sync += [
                        self.o_b.eq(Mux(n_b > 0x1f, 0x1f, Mux(n_b < 0, 0, n_b)))
                    ]

            # Draw a border
            with m.If(self.border & ((c_x == 0) | (c_x == self.res_x - 1) | (c_y == 0) | (c_y == self.res_y - 1))):
                m.d.sync += [
                    self.o_r.eq(0),
                    self.o_g.eq(0),
                    self.o_b.eq(0x1f)
                ]

        return m

