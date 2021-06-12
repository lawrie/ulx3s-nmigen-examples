from nmigen import *

from spimem import SpiMem

class SpiRamBtn(Elaboratable):
    def __init__(self, addr_btn=0xfb, addr_irq=0xf1, debounce_bits=20, addr_bits=32, data_bits=8):
        #parameters
        self.addr_btn      = addr_btn
        self.addr_irq      = addr_irq
        self.debounce_bits = debounce_bits
        self.addr_bits     = addr_bits # Must be 32

        # inputs
        self.copi    = Signal()
        self.din     = Signal(data_bits)
        self.csn     = Signal()
        self.sclk    = Signal()
        self.btn     = Signal(7)
 
        # outputs
        self.irq     = Signal()
        self.addr    = Signal(addr_bits)
        self.cipo    = Signal()
        self.dout    = Signal(data_bits)
        self.rd      = Signal()
        self.wr      = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.spimem = spimem = SpiMem(addr_bits=self.addr_bits)

        r_btn_irq      = Signal()
        r_btn_latch    = Signal(7)
        r_btn          = Signal(7)
        r_spi_rd       = Signal()
        r_btn_debounce = Signal(self.debounce_bits)
        mux_data_in    = Signal(8)

        m.d.comb += [
            self.irq.eq(r_btn_irq),
            mux_data_in.eq(Mux(self.addr[-8:] == self.addr_irq, Cat(C(0,7), r_btn_irq),
                           Mux(self.addr[-8:] == self.addr_btn, Cat(r_btn,C(0,1)), self.din))),
            spimem.csn.eq(self.csn),
            spimem.sclk.eq(self.sclk),
            spimem.copi.eq(self.copi),
            spimem.din.eq(mux_data_in),
            self.cipo.eq(spimem.cipo),
            self.addr.eq(spimem.addr),
            self.dout.eq(spimem.dout),
            self.wr.eq(spimem.wr),
            self.rd.eq(spimem.rd)
        ]

        m.d.sync += r_spi_rd.eq(self.rd)

        with m.If(~self.rd & r_spi_rd & (self.addr[-8:] == self.addr_irq)):
            m.d.sync += r_btn_irq.eq(0)
        with m.Else():
            m.d.sync += r_btn_latch.eq(self.btn)
            with m.If((r_btn != r_btn_latch) & r_btn_debounce[-1] & ~r_btn_irq):
                m.d.sync += [
                    r_btn_irq.eq(1),
                    r_btn_debounce.eq(0),
                    r_btn.eq(r_btn_latch)
                ]
            with m.Elif(~r_btn_debounce[-1]):
                m.d.sync += r_btn_debounce.eq(r_btn_debounce + 1)

        return m

