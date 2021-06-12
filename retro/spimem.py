from nmigen import *
from nmigen.utils import bits_for

class SpiMem(Elaboratable):
    def __init__(self, addr_bits=32, data_bits=8):
        #parameters
        self.addr_bits = addr_bits # Must be power of 2
        self.data_bits = data_bits # currently must be 8

        # inputs
        self.copi    = Signal()
        self.din     = Signal(data_bits)
        self.csn     = Signal()
        self.sclk    = Signal()
 
        # outputs
        self.addr    = Signal(addr_bits)
        self.cipo    = Signal()
        self.dout    = Signal(data_bits)
        self.rd      = Signal()
        self.wr      = Signal()

    def elaborate(self, platform):
        m = Module()

        r_req_read   = Signal()
        r_req_write  = Signal()
        r_data       = Signal(self.data_bits)
        r_addr       = Signal(self.addr_bits + 1)

        r_bit_count  = Signal(bits_for(self.addr_bits + 8) + 1)

        r_copi       = Signal()
        r_sclk       = Signal(2)

        # Drive outputs
        m.d.comb += [
            self.rd.eq(r_req_read),
            self.wr.eq(r_req_write),
            self.cipo.eq(r_data[-1]),
            self.dout.eq(r_data),
            self.addr.eq(r_addr[:-1])
        ]

        # De-glitch and edge detection
        m.d.sync += [
            r_copi.eq(self.copi),
            r_sclk.eq(Cat(self.sclk,r_sclk[0]))
        ]

        # State machine
        with m.If(self.csn):
            m.d.sync += [
                r_req_read.eq(0),
                r_req_write.eq(0),
                r_bit_count.eq(self.addr_bits + 7)
            ]
        with m.Else(): # csn == 0
            with m.If(r_sclk == 0b01): # rising sclk
                # If writing shift in data
                m.d.sync += r_data.eq(Mux(r_req_read, self.din, Cat(r_copi, r_data[:-1])))
                with m.If(r_bit_count[-1] == 0): # Address bits
                    m.d.sync += [
                        r_bit_count.eq(r_bit_count - 1),
                        r_addr.eq(Cat(r_copi, r_addr[:-1])) # Shift in address
                    ]
                with m.Else(): # read or write
                    with m.If(r_bit_count[:4] == 7): # First bit in new byte, increment address
                        m.d.sync += r_addr[:-1].eq(r_addr[:-1] + 1)
                    m.d.sync += r_req_read.eq(Mux(r_bit_count[:3] == 1, r_addr[-1], 0))
                    with m.If(r_bit_count[:3] == 0): # Last bit in byte
                        with m.If(r_addr[-1] == 0):
                            m.d.sync += r_req_write.eq(1)
                        m.d.sync += r_bit_count[3].eq(0) # Allow increment of address
                    with m.Else():
                        m.d.sync += r_req_write.eq(0)
                    m.d.sync += r_bit_count[:3].eq(r_bit_count[:3] - 1)
        
        return m

