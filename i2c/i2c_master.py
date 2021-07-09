from nmigen import *
from nmigen.utils import bits_for

class I2cMaster(Elaboratable):
    AW = 7 # i2c address width
    DW = 8 # data width

    def __init__(self):
        # inputs
        self.valid     = Signal()         # Strobe to start new transaction
        self.read      = Signal()         # Set for reads
        self.rep_start = Signal()         # Set for repeated starts (not tested)
        self.read_only = Signal()         # Set for reads without write cycle
        self.short_wr  = Signal()         # Set for short write
        self.addr      = Signal(self.AW)  # The 7-bit i2c address
        self.reg       = Signal(self.DW)  # The register of sub-address
        self.din       = Signal(self.DW)  # First data byte
        self.din2      = Signal(self.DW)  # Second data byte

        # outputs
        self.rdy       = Signal()         # Set when not busy
        self.dout      = Signal(self.DW)  # The data read
        self.init      = Signal(reset=1)  # Set during initialsation
        self.addr_nack = Signal()         # Low if address is acked
        self.data_nack = Signal()         # Low if data is acked
        self.diag      = Signal(8)        # Diagnostic output

    def elaborate(self, platform):
        # Get i2c pins in direct mode
        dir_dict = { "scl":"-", "sda":"-"}
        i2c_pins = platform.request("i2c", dir=dir_dict)

        m = Module()

        # Set direction of i2c pins
        scl_dir = Signal()
        scl_out = Signal()
        scl_in  = Signal()

        scl_io = Instance("SB_IO",
            p_PIN_TYPE=C(0b1010_01, 6),
            p_PULLUP=C(1),
            io_PACKAGE_PIN=i2c_pins.scl,
            i_OUTPUT_ENABLE=scl_dir,
            i_D_OUT_0=scl_out,
            o_D_IN_0=scl_in)

        m.submodules += scl_io

        sda_dir = Signal()
        sda_out = Signal()
        sda_in = Signal()

        sda_io = Instance("SB_IO",
            p_PIN_TYPE=C(0b1010_01, 6),
            p_PULLUP=C(1),
            io_PACKAGE_PIN=i2c_pins.sda,
            i_OUTPUT_ENABLE=sda_dir,
            i_D_OUT_0=sda_out,
            o_D_IN_0=sda_in)

        m.submodules += sda_io

        # Data is driven low when pins are in output mode
        m.d.comb += [
            scl_out.eq(~scl_dir),
            sda_out.eq(~sda_dir)
        ]

        # De-glitch i2c pins
        sda_sr = Signal(4, reset=0b1111)
        scl_sr = Signal(4, reset=0b1111)
        sda    = Signal(reset=1)
        scl    = Signal(reset=1)

        m.d.sync += [
            sda_sr.eq(Cat(sda_in, sda_sr[:3])),
            scl_sr.eq(Cat(scl_in, scl_sr[:3]))
        ]

        with m.If(sda_sr == C(0b0000,4)):
            m.d.sync += sda.eq(0)
        with m.Elif(sda_sr == C(0b1111,4)):
            m.d.sync += sda.eq(1)

        with m.If(scl_sr == C(0b0000,4)):
            m.d.sync += scl.eq(0)
        with m.Elif(scl_sr == C(0b1111,4)):
            m.d.sync += scl.eq(1)

        # State machine states
        PRE_START_UP = 0
        START_UP     = 1
        IDLE         = 2
        START        = 3
        CLOCK_LOW    = 4
        SHIFT_DATA   = 5
        CLOCK_HIGH   = 6
        STOP         = 7
        SPIN         = 15

        state     = Signal(4, reset=PRE_START_UP)
        rtn_state = Signal(4)

        # Function to delay and then go to next state
        def delay(t, s):
            m.d.sync += [
                timer.eq(t),
                rtn_state.eq(s),
                state.eq(SPIN)
            ]

        # Diagnostics
        m.d.comb += self.diag.eq(Cat(state, rtn_state))

        # i2c timings
        FREQ       = int(platform.default_clk_frequency // 1000000)
        #FREQ       = 22 # This gets closer to 100KHz
        T_HD_STA   = 4 * FREQ
        T_LOW      = 5 * FREQ
        T_HIGH     = 5 * FREQ
        T_SU_STA   = 5 * FREQ
        T_SU_DAT   = (FREQ >> 2) + 1
        T_HOLD     = (FREQ >> 1) + 1
        T_SU_STO   = 4 * FREQ

        # Timers and other signals
        timer             = Signal(bits_for(T_LOW + 1), reset=T_LOW)
        bit_count         = Signal(6)
        scl_startup_count = Signal(4)
        wr_cyc            = Signal()
        shift_reg         = Signal(self.AW + self.DW * 3 + 5)
        read_data         = Signal(self.DW)

        # State machine
        with m.Switch(state):
            with m.Case(PRE_START_UP):
                with m.If(timer == 0):
                    with m.If(~scl_dir):
                        with m.If(sda & (scl_startup_count == 12)):
                            m.d.sync += [
                                scl_startup_count.eq(0),
                                state.eq(START_UP)
                            ]
                        with m.Else():
                            m.d.sync += [
                                scl_dir.eq(1),
                                scl_startup_count.eq(scl_startup_count + 1),
                                timer.eq(T_LOW)
                            ]
                    with m.Else():
                        m.d.sync += [
                            scl_dir.eq(0),
                            timer.eq(T_LOW)
                        ]
                with m.Elif(scl | scl_dir):
                    m.d.sync += timer.eq(timer - 1)
            with m.Case(START_UP):
                with m.If(timer == 0):
                    m.d.sync += [
                        timer.eq(T_LOW),
                        scl_startup_count.eq(scl_startup_count + 1)
                    ]
                    with m.If(scl_startup_count == 2):
                        m.d.sync += sda_dir.eq(1)
                    with m.If(scl_startup_count == 12):
                        m.d.sync += sda_dir.eq(0)
                    with m.If(scl_startup_count == 15):
                        m.d.sync += state.eq(IDLE)
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)
            # Ready to accept transactions
            with m.Case(IDLE):
                m.d.sync += [
                    sda_dir.eq(0),
                    scl_dir.eq(0),
                    self.rdy.eq(1),
                    self.init.eq(0)
                ]
                with m.If(self.valid):
                    m.d.sync += [
                        self.rdy.eq(0),
                        state.eq(START),
                        wr_cyc.eq(~self.read_only)
                    ]
            # Start a transaction and set up the shift register
            with m.Case(START):
                m.d.sync += [
                    sda_dir.eq(1),
                    scl_dir.eq(0)
                ]
                with m.If(~sda):
                    with m.If(self.read):
                        with m.If(wr_cyc):
                            m.d.sync += shift_reg.eq(Cat([C(0,self.DW * 2 + 1), self.rep_start, C(1,1), self.reg, C(1,0), C(0,0), self.addr]))
                        with m.Else():
                            m.d.sync += shift_reg.eq(Cat([C(0,self.DW * 2 + 2), C(1,1), C(0xff,self.DW),C(1,1),C(1,1),self.addr]))
                    with m.Else():
                        m.d.sync += shift_reg.eq(Cat([C(1,1), self.din2, C(1,1), self.din, C(1,1), self.reg, C(1,1), C(0,1), self.addr]))
                    m.d.sync += bit_count.eq(0)
                    delay(T_HD_STA, CLOCK_LOW)
            # Set SCL low
            with m.Case(CLOCK_LOW):
                m.d.sync += scl_dir.eq(1)
                with m.If(~scl):
                    delay(T_HOLD, SHIFT_DATA)
            # Shift the data out
            with m.Case(SHIFT_DATA):
                m.d.sync += [
                    sda_dir.eq(~shift_reg[-1]),
                    shift_reg.eq(Cat(C(0,1), shift_reg[:-1]))
                ]
                delay(T_LOW, CLOCK_HIGH)
            # Set SCL high
            with m.Case(CLOCK_HIGH):
                m.d.sync += scl_dir.eq(0)
                with m.If(scl):
                    m.d.sync += bit_count.eq(bit_count + 1)
                    with m.If(bit_count == self.AW + 1):
                        m.d.sync += self.addr_nack.eq(sda)
                    with m.Elif(((bit_count == self.AW + self.DW + 2) & wr_cyc) | (bit_count == self.AW + self.DW * 2 + 3) | (bit_count == self.AW + self.DW * 3 + 4)):
                        m.d.sync += self.data_nack.eq(sda)
                    with m.If(((bit_count == self.AW + self.DW + 3) & self.read) | (bit_count == self.AW + self.DW * 3 + 5) | (self.short_wr & (bit_count == self.AW + self.DW * 2 + 4))):
                        delay(T_SU_STO, STOP)
                    with m.Else():
                        with m.If(bit_count != self.AW + self.DW + 2):
                            m.d.sync += read_data.eq(Cat(sda,read_data[:self.DW-1]))
                        delay(T_HIGH, CLOCK_LOW)
            # Stop bit
            with m.Case(STOP):
                m.d.sync += sda_dir.eq(0)
                with m.If(sda):
                    with m.If(self.read):
                        m.d.sync += wr_cyc.eq(0)
                        with m.If(wr_cyc):
                            delay(Mux(self.rep_start, T_SU_STA - T_SU_STO, T_SU_STA), START)
                        with m.Else():
                            m.d.sync += self.dout.eq(read_data)
                            delay(T_SU_STA, IDLE)
                    with m.Else():
                        delay(T_SU_STA, IDLE)
            # Wait state
            with m.Case(SPIN):
                with m.If(timer > 0):
                    m.d.sync += timer.eq(timer - 1)
                with m.Else():
                    m.d.sync += state.eq(rtn_state)

        return m

