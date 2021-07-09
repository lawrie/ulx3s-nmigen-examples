from nmigen import *

from nmigen.utils import bits_for

# Apply a convolution kernel to a stream of monochrome pixels or an RGB channel
class Conv3(Elaboratable):
    def __init__(self, k, sh=0, w=320, h=240, dw=8):
        # Parameters
        self.w         = w
        self.h         = h
        self.k         = k
        self.sh        = sh
        self.dw        = dw

        # Inputs
        self.i_p       = Signal(dw)
        self.i_valid   = Signal()

        # Outputs
        self.o_p       = Signal(dw)
        self.o_valid   = Signal()
        self.o_stall   = Signal()
        self.o_x       = Signal(bits_for(w), reset=self.w - 1)
        self.o_y       = Signal(bits_for(h), reset=self.h - 1)

    def elaborate(self, platform):
        m = Module()

        # x and y co-ordinates of latest received pixel
        x = Signal(bits_for(self.w), reset=0)
        y = Signal(bits_for(self.h + 3), reset=0)

        # x2 is two columns ahead of x with wraparound
        x2 = Signal(bits_for(self.h))
        m.d.comb += x2.eq(Mux(x >= self.w - 2, x + 2 - self.w, x + 2))

        # Indicates if pixel generation has started
        started = Signal(reset=0)

        # Current pixel window
        p00 = Signal(self.dw)
        p01 = Signal(self.dw)
        p02 = Signal(self.dw)
        p10 = Signal(self.dw)
        p11 = Signal(self.dw)
        p12 = Signal(self.dw)
        p20 = Signal(self.dw)
        p21 = Signal(self.dw)
        p22 = Signal(self.dw)

        # p22 is combinatorial
        m.d.comb += p22.eq(Mux(x == 0, p21, Mux(y == self.h, p12, self.i_p)))

        pd0 = Signal(self.dw)
        pd1 = Signal(self.dw)

        # Line buffers
        pl0 = Memory(width=self.dw, depth=self.w)
        m.submodules.r0 = r0 = pl0.read_port()
        m.submodules.w0 = w0 = pl0.write_port()
        pl1 = Memory(width=self.dw, depth=self.w)
        m.submodules.r1 = r1 = pl1.read_port()
        m.submodules.w1 = w1 = pl1.write_port()

        # For simulation
        if platform is None:
            l0 = Signal(self.w * self.dw)
            m.d.comb += l0.eq(Cat([pl0[self.w - 1 - i] for i in range(self.w)]))
            l1 = Signal(self.w * 8)
            m.d.comb += l1.eq(Cat([pl1[self.w - 1 - i] for i in range(self.w)]))

        # Connect line buffers
        m.d.comb += [
            w0.addr.eq(x),
            w0.en.eq(self.i_valid & (y != 1) & (y != self.h)),
            w0.data.eq(Mux(y >= 2, pd1, self.i_p)),
            w1.addr.eq(x),
            w1.en.eq(self.i_valid & (y != self.h)),
            w1.data.eq(self.i_p),
            r0.addr.eq(x2),
            r1.addr.eq(x2)
        ]

        # Pixel not valid by default
        m.d.sync += self.o_valid.eq(0)

        # Process pixel
        with m.If(self.i_valid | self.o_stall):
            # Save last values read for wraparound
            m.d.sync += [
                pd0.eq(r0.data),
                pd1.eq(r1.data)
            ]

            # Increment x and y
            m.d.sync += x.eq(x+1)
            with m.If(x == self.w - 1):
                m.d.sync += [
                    x.eq(0),
                    y.eq(y+1)
                ]

            # Test for frame done
            with m.If((y == self.h + 1)):
                m.d.sync += [
                    x.eq(0),
                    y.eq(0),
                    self.o_stall.eq(0),
                    started.eq(0),
                    self.o_x.eq(self.w - 1),
                    self.o_y.eq(self.h - 1)
                ]

            # Pixel generation starts on row 1, column 1
            with m.If((y == 1) & (x == 0)):
                m.d.sync += started.eq(1)

            # Stall for the last row plus 1 pixel, while last pixels flushed
            with m.If((y == self.h - 1) & (x == self.w - 1)):
                m.d.sync += self.o_stall.eq(1)

            # Calculate pixel
            with m.If((x == 0) & (y == 0)):
                # Top left corner
                # Extend edges with closest pixel
                m.d.sync += [
                    p00.eq(self.i_p),
                    p01.eq(self.i_p),
                    p10.eq(self.i_p),
                    p11.eq(self.i_p)
                ]
            with m.Elif((x == 1) & (y == 0)):
                # Second column of top row
                m.d.sync += [
                    p02.eq(self.i_p),
                    p12.eq(self.i_p),
                ]
            with m.Elif((x == 0) & (y == 1)):
                # First column of second row
                m.d.sync += [
                    p20.eq(self.i_p),
                    p21.eq(self.i_p)
                ]
            with m.Elif(started):
                # Start generating pixels
                m.d.sync += [
                    # Move the window
                    p00.eq(Mux(x == 0, pd0, p01)),
                    p01.eq(Mux(x == 0, pd0, p02)),
                    p02.eq(Mux(x == self.w - 1, p02, r0.data)),
                    p10.eq(Mux(x == 0, pd1, p11)),
                    p11.eq(Mux(x == 0, pd1, p12)),
                    p12.eq(Mux(x == self.w - 1, p12, r1.data)),
                    p20.eq(Mux(y == self.h, Mux(x == 0, pd1, p11), Mux(x == 0, self.i_p, p21))),
                    p21.eq(Mux(y == self.h, Mux(x == 0, pd1, p12), self.i_p)),
                    # Generate the pixel
                    self.o_valid.eq(1),
                    self.o_x.eq(self.o_x+1),
                    self.o_p.eq((p00 * self.k[0] +
                                 p01 * self.k[1] +
                                 p02 * self.k[2] +
                                 p10 * self.k[3] +
                                 p11 * self.k[4] +
                                 p12 * self.k[5] +
                                 p20 * self.k[6] +
                                 p21 * self.k[7] +
                                 p22 * self.k[8]) >> self.sh)
                ]
                with m.If(self.o_x == self.w - 1):
                    m.d.sync += [
                        self.o_y.eq(self.o_y + 1),
                        self.o_x.eq(0)
                    ]
                    with m.If(self.o_y == self.h - 1):
                        m.d.sync += self.o_y.eq(0)

        return m
 
