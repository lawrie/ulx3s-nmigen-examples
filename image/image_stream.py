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
        self.border      = Signal()

    def elaborate(self, platform):
        m = Module()

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

        c_r = Signal(5)
        c_g = Signal(6)
        c_b = Signal(5)

        # Convert to monochrome
        with m.If(self.mono):
            m.d.comb += [
                c_r.eq(Mux(self.invert, 0x1f - s[2:], s[2:])),
                c_g.eq(Mux(self.invert, 0x3f - s[1:], s[1:])),
                c_b.eq(Mux(self.invert, 0x1f - s[2:], s[2:]))
            ]
        with m.Else():
            m.d.comb += [
                c_r.eq(self.i_r),
                c_g.eq(self.i_g),
                c_r.eq(self.i_r)
            ]

        # Process pixel when valid set, and set ready
        with m.If(self.valid):
            m.d.sync += [
                self.ready.eq(1),
                # Set output x and y with horizontal and vertical flip
                self.o_x.eq(c_x),
                self.o_y.eq(c_y),
                # Copy input pixel by default
                self.o_r.eq(c_r),
                self.o_g.eq(c_g),
                self.o_b.eq(c_b),
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
                        self.o_r.eq(Mux(c_r + self.val > 0x1f, 0x1f, Mux(c_r + self.val < 0, 0, c_r + self.val)))
                    ]
                with m.If(self.green | self.bright):
                    m.d.sync += [
                        self.o_g.eq(Mux(c_g + self.val > 0x3f, 0x3f, Mux(c_g + self.val < 0, 0, c_g + self.val)))
                    ]
                with m.If(self.blue | self.bright):
                    m.d.sync += [
                        self.o_b.eq(Mux(c_b + self.val > 0x1f, 0x1f, Mux(c_b + self.val < 0, 0, c_b + self.val)))
                    ]

            # Draw a border
            with m.If(self.border & ((c_x == 0) | (c_x == self.res_x - 1) | (c_y == 0) | (c_y == self.res_y - 1))):
                m.d.sync += [
                    self.o_r.eq(0),
                    self.o_g.eq(0),
                    self.o_b.eq(0x1f)
                ]

        return m

