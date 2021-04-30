from nmigen import *

class ImageStream(Elaboratable):
    def __init__(self):
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

    def elaborate(self,platform):
        m = Module()

        m.d.comb += [
            self.ready.eq(self.valid),
            self.o_x.eq(self.i_x),
            self.o_y.eq(self.i_y),
            self.o_r.eq(self.i_r),
            self.o_g.eq(self.i_g),
            self.o_b.eq(self.i_b),
        ]

        return m

