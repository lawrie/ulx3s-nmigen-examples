from nmigen import *

class OSD(Elaboratable):
    def __init__(self, x_start=608, y_start=288, width=16, height=192):
        # parameters
        self.x_start = x_start
        self.y_start = y_start
        self.width   = width
        self.height  = height

        # inputs
        self.on      = Signal()
        self.osd_val = Signal(4)
        self.i_r     = Signal(8)
        self.i_g     = Signal(8)
        self.i_b     = Signal(8)
        self.x       = Signal(10)
        self.y       = Signal(10)
        self.sel     = Signal()
        self.grid    = Signal()
        self.border  = Signal()

        # outputs
        self.o_r     = Signal(8)
        self.o_g     = Signal(8)
        self.o_b     = Signal(8)

    def elaborate(self, platform):
        m = Module()

        # Copy color by default
        m.d.sync += [
            self.o_r.eq(self.i_r),
            self.o_g.eq(Mux(self.grid & (self.x[:6].all() | self.y[:6].all()), 0xff, self.i_g)),
            self.o_b.eq(Mux(self.border & ((self.x < 2) | (self.x >= 638) | 
                                            (self.y < 2) | (self.y >= 478)), 0xff, self.i_b))
        ]

        y_offset = Signal(10)
        xb = Signal(4)
        yb = Signal(4)

        m.d.comb += [
            y_offset.eq(self.y - self.y_start),
            xb.eq(self.x[:4]),
            yb.eq(self.y[:4])
        ]

        with m.If(self.on): # If OSD is on
            # Are we in OSD area?
            with m.If((self.x >= self.x_start) & (self.x < self.x_start + self.width) &
                      (self.y >= self.y_start) & (self.y < self.y_start + self.height)):
                # Set pixels black by default
                m.d.sync += [
                    self.o_r.eq(0),
                    self.o_g.eq(0),
                    self.o_b.eq(0)
                ]

                # Check for current option
                with m.If(y_offset[4:] == self.osd_val):
                    # set gray by default
                    m.d.sync += [
                        self.o_r.eq(0x3F),
                        self.o_g.eq(0x3F),
                        self.o_b.eq(0x3F)
                    ]

                    # If selected, set border red
                    with m.If(self.sel & ((xb == 0) | (xb == 15) |
                                          (yb == 0) | (yb == 15))):
                        m.d.sync += [
                            self.o_r.eq(0xFF),
                            self.o_g.eq(0),
                            self.o_b.eq(0)
                        ]

                    # Set the current icon
                    with m.Switch(self.osd_val):
                        with m.Case(0): # brightness
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(0xFF),
                                    self.o_g.eq(0xFF),
                                    self.o_b.eq(0xFF)
                                ]
                        with m.Case(1): # red
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(0xFF),
                                    self.o_g.eq(0),
                                    self.o_b.eq(0)
                                ]
                        with m.Case(2): # green
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(0),
                                    self.o_g.eq(0xFF),
                                    self.o_b.eq(0)
                                ]
                        with m.Case(3): # blue
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(0),
                                    self.o_g.eq(0),
                                    self.o_b.eq(0xFF)
                                ]
                        with m.Case(4): # monochrome
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(0x7F),
                                    self.o_g.eq(0x7F),
                                    self.o_b.eq(0x7F)
                                ]
                        with m.Case(5): # X flip
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(Mux((xb == yb) | (xb == (15 - yb)), 0xFF, 0)),
                                    self.o_g.eq(Mux((xb == yb) | (xb == (15 - yb)), 0xFF, 0)),
                                    self.o_b.eq(Mux((xb == yb) | (xb == (15 - yb)), 0xFF, 0))
                                ]
                        with m.Case(6): # Y flip
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                m.d.sync += [
                                    self.o_r.eq(Mux((((yb == 10) & ((xb == 6) |( xb == 8)))) | ((yb != 10) & ((xb == yb) | (xb == (15 - yb)))), 0xFF, 0)),
                                    self.o_g.eq(Mux((((yb == 10) & ((xb == 6) |( xb == 8)))) | ((yb != 10) & ((xb == yb) | (xb == (15 - yb)))), 0xFF, 0)),
                                    self.o_b.eq(Mux((((yb == 10) & ((xb == 6) |( xb == 8)))) | ((yb != 10) & ((xb == yb) | (xb == (15 - yb)))), 0xFF, 0))
                                ]
                        with m.Case(7): # Border
                            with m.If((xb == 2) | (xb == 14) |
                                      (yb == 2) | (yb == 14)):
                                m.d.sync += [
                                    self.o_r.eq(0),
                                    self.o_g.eq(0),
                                    self.o_b.eq(0xFF)
                                ]
                        with m.Case(8): # Edge detection
                            with m.If((yb == 8) & (xb > 4) & (xb < 6)):
                                m.d.sync += [
                                    self.o_r.eq(0xFF),
                                    self.o_g.eq(0),
                                    self.o_b.eq(0)
                                ]
                        with m.Case(9): # Invert
                            with m.If((xb > 2) & (xb < 14) &
                                      (yb > 2) & (yb < 14)):
                                with m.If(yb < 4):
                                    m.d.sync += [
                                        self.o_r.eq(0xFF),
                                        self.o_g.eq(0xFF),
                                        self.o_b.eq(0xFF)
                                    ]
                                with m.Else():
                                    m.d.sync += [
                                        self.o_r.eq(0),
                                        self.o_g.eq(0),
                                        self.o_b.eq(0)
                                    ]
                        with m.Case(10): # Gamma
                            with m.If((yb == 8) & (xb > 4) & (xb < 12)):
                                m.d.sync += [
                                    self.o_r.eq(0),
                                    self.o_g.eq(0xFF),
                                    self.o_b.eq(0)
                                ]
                        with m.Case(11): # Filter
                            with m.If((yb == 8) & (xb == 8)):
                                m.d.sync += [
                                    self.o_r.eq(0xFF),
                                    self.o_g.eq(0),
                                    self.o_b.eq(0)
                                ]

        return m

