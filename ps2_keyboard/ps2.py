from nmigen import *

class PS2(Elaboratable):
    def __init__(self):
        self.ps2_clk  = Signal(1)
        self.ps2_data = Signal(1)
        self.data     = Signal(8, reset=0)
        self.valid    = Signal(1, reset=0)
        self.error    = Signal(1, reset=0)

    def elaborate(self, platform):
        clk_filter  = Signal(8, reset=0xff)
        ps2_clk_in  = Signal(1, reset=1)
        ps2_data_in = Signal(1, reset=1)
        clk_edge    = Signal(1, reset=0)
        bit_count   = Signal(4, reset=0)
        shift_reg   = Signal(9, reset=0)
        parity      = Signal(1, reset=0)

        m = Module()

        m.d.sync += [
            ps2_data_in.eq(self.ps2_data),
            clk_filter.eq(Cat(clk_filter[1:], self.ps2_clk)),
            clk_edge.eq(0)
        ]     

        with m.If(clk_filter.all()):
            m.d.sync += ps2_clk_in.eq(1)
        with m.Elif(clk_filter == 0):
            with m.If(ps2_clk_in):
                m.d.sync += clk_edge.eq(1)
            m.d.sync += ps2_clk_in.eq(0)

        m.d.sync += [
            self.valid.eq(0),
            self.error.eq(0)
        ]

        with m.If(clk_edge):
           with m.If(bit_count == 0):
               m.d.sync += parity.eq(0)
               with m.If(~ps2_data_in):
                   m.d.sync += bit_count.eq(bit_count + 1)
           with m.Else():
               with m.If(bit_count < 10):
                   m.d.sync += [
                       bit_count.eq(bit_count + 1),
                       shift_reg.eq(Cat([shift_reg[1:],ps2_data_in])),
                       parity.eq(parity ^ ps2_data_in)
                   ]
               with m.Elif(ps2_data_in):
                   m.d.sync += bit_count.eq(0)
                   with m.If(parity):
                       m.d.sync += [
                           self.data.eq(shift_reg[:8]),
                           self.valid.eq(1)
                       ]
                   with m.Else():
                       m.d.sync += self.error.eq(1)
               with m.Else():
                    m.d.sync += [
                        bit_count.eq(0),
                        self.error.eq(1)
                    ]

        return m

