from nmigen import *

class Sdram(Elaboratable):
    def __init__(self):
        self.sd_data_in  = Signal(16)
        self.sd_data_out = Signal(16)
        self.sd_addr     = Signal(13)
        self.sd_dqm      = Signal(2)
        self.sd_ba       = Signal(2)
        self.sd_cs       = Signal()
        self.sd_we       = Signal()
        self.sd_ras      = Signal()
        self.sd_cas      = Signal()

        self.init        = Signal()
        self.clk         = Signal()
        self.clkref      = Signal()
        self.we_out      = Signal()

        self.addrA       = Signal(25)
        self.weA         = Signal()
        self.dinA        = Signal(8)
        self.oeA         = Signal()
        self.doutA       = Signal(8)

        self.addrB       = Signal(25)
        self.weB         = Signal()
        self.dinB        = Signal(8)
        self.oeB         = Signal()
        self.doutB       = Signal(8)
        
    def elaborate(self, platform):

        m = Module()

        RASCAS_DELAT   = C(2,3)
        BURST_LENGTH   = C(0,3)
        ACCESS_TYPE    = C(0,1)
        CAS_LATENCY    = C(3,3)
        OP_MODE        = C(0,2)
        NO_WRITE_BURST = C(1,1)

        MODE = Cat([BURST_LENGTH, ACCESS_TYPE, CAS_LATENCY, OP_MODE, NO_WRITE_BURST, C(0,3)])

        STATE_FIRST     = C(0,3)
        STATE_CMD_START = C(1,3)
        STATE_CMD_CONT  = C(STATE_CMD_START + RASCAS_DELAY,3)
        STATE_CMD_READ  = C(STATE_CMD_CONT + CAS_LATENCY + 1,3)
        STATE_LAST      = C(7,3)

        clkref_last = Signal()
        q           = Signal(3)

        m.d.sync += [
            clkref_last.eq(self.clk_ref),
            q.eq(q+1)
        ]

        with m.If(q == STATE_LAST):
            m.d.sync += q.eq(STATE_FIRST)
        with m.If(~clkref_last & self.clkref):
            m.d.sync += q.eq(STATE_FIRST+1)

        reset = Signal(17)

        with m.If(self.init):
            m.d.sync += reset.eq(C(0x1f,17))
        with m.Elif((q == STATE_LAST) & (reset != 0)):
            m.d.sync += reset.eq(reset+1)

        CMD_INHIBIT          = C(0b1111,4)
        CMD_NOP              = C(0b0111,4)
        CMD_ACTIVE           = C(0b0011,4)
        CMD_READ             = C(0b0101,4)
        CMD_WRITE            = C(0b0100,4)
        CMD_BURST_TERMINATE  = C(0b0110,4)
        CMD_PRECHARGE        = C(0b0010,4)
        CMD_AUTO_REFRESH     = C(0b0001,4)
        CMD_LOAD_MODE        = C(0b0000,4)

        sd_cmd = Signal(4)
        oe = Signal()
        addr = Signal(25)
        din = Signal(8)

        with m.If(self.clkref):
            m.d.comb += [
                oe.eq(self.oeA),
                self.we_out.eq(self.weA),
                addr.eq(self.addrA),
                din.eq(self.dinA)
            ]
        with m.Else():
            m.d.comb += [
                oe.eq(self.oeB),
                self.we_out.eq(self.weB),
                addr.eq(self.addrB),
                din.eq(self.dinB)
            ]

        addr0 = Signal()

        with m.If((q == 1) & oe):
            md.d.sync += addr0.eq(addr[0])

        dout = Signal(8)

        m.d.comb += dout.eq(Mux(addr0, self.sd_data_in[0:8], self.sd_data_in[8:]))

        with m.If(q == STATE_CMD_READ):
            with m.If(self.oeA & self.clkref):
                m.d.sync += self.doutA.eq(dout)
            with m.If(self.oeB & ~self.clkref):
                m.d.sync += self.doutB.eq(dout)

        reset_cmd = Signal(4)
        run_cmd = Signal(4)

        m.d.comb += [
            reset.cmd.eq(Mux((q == STATE_CMD_START) & (reset == 13), CMD_RECHARGE,
                         Mux((q == STATE_CMD_START) & (reset == 2), CMD_LOAD_MODE, CMD_INHIBIT))),
            run_cmd.eq(Mux((we_out | oe) & (q == STATE_CMD_START), CMD_ACTIVE, 
                       Mux(we_out & (q == STATE_CMD_CONT), CMD_WRITE,
                       Mux(~we_out & oe & (q == STATE_CMD_CONT, CMD_READ,
                       Mux(~we_out & ~oe & (q == STATE_CMD_START), CMD_AUTO_REFRESH, CMD_INHIBIT)))))),
            sd_cmd.eq(Mux(reset != 0, reset_cmd, run_cmd))
        ]

        reset_addr = Signal(13)
        run_addr = Signal(13)

        m.d.comb += [
            reset_addr.eq(Mux(reset == 13, C(0b0010000000000,13), MODE)),
            run_addr.eq(Mux(q == STATE_CMD_START, add[9:22], Cat(addr[1:9], addr[24], C(0b0010,4)))),
            self.sd_data_out.eq(Mux(Cat(din, din), C(0,16))),
            self.sd_addr.eq(Mux(reset != 0, reset_addr, run_addr)),
            self.sd_ba.eq(Mux(reset != 0, C(0,2), addr[22,24])),
            self.sd_dqm.eq(Mux(we_out,Cat(~addr[0],addr[0]), C(0,2))),
            self.sd_cs.eq(sd_cmd[3]),
            self.sd_ras.eq(sd_cmd[2]),
            self.sd_cas.eq(sd_cmd[1]),
            self.sd_we.eq(sd_cmd[0])
        ]

