from nmigen import *

# SDRAM controller with 16-bit reads and writes
class Sdram(Elaboratable):
    def __init__(self):

        # Chip interface
        self.sd_data_in  = Signal(16)
        self.sd_data_out = Signal(16)
        self.sd_data_dir = Signal()
        self.sd_addr     = Signal(13)
        self.sd_dqm      = Signal(2)
        self.sd_ba       = Signal(2)
        self.sd_cs       = Signal()
        self.sd_we       = Signal()
        self.sd_ras      = Signal()
        self.sd_cas      = Signal()

        # Control
        self.init        = Signal()
        self.sync        = Signal()

        # Port
        self.din         = Signal(16)
        self.dout        = Signal(16)
        self.addr        = Signal(24) # Word address
        self.ds          = Signal(2)
        self.oe          = Signal()
        self.we          = Signal()

    def elaborate(self, platform):

        m = Module()

        # Configure SDRAM access
        RASCAS_DELAY   = C(2,3)
        BURST_LENGTH   = C(0,3)
        ACCESS_TYPE    = C(0,1)
        CAS_LATENCY    = C(2,3)
        OP_MODE        = C(0,2)
        NO_WRITE_BURST = C(1,1)

        MODE = Cat([BURST_LENGTH, ACCESS_TYPE, CAS_LATENCY, OP_MODE, NO_WRITE_BURST, C(0,1)])

        # States
        STATE_FIRST     = C(0,3)
        STATE_CMD_START = C(1,3)
        STATE_CMD_CONT  = STATE_CMD_START + RASCAS_DELAY
        STATE_READ      = STATE_CMD_CONT + CAS_LATENCY + C(1,3)
        STATE_HIGHZ     = STATE_READ - C(1,3)

        # Reset counts down after init set
        reset = Signal(5)
        stage = Signal(3)

        with m.If(self.init):
            m.d.sdram += reset.eq(C(0x1f,5))
        with m.Elif((stage == STATE_FIRST) & (reset != 0)):
            m.d.sdram += reset.eq(reset-1)

        # SDRAM commands
        CMD_INHIBIT          = C(0b1111,4)
        CMD_NOP              = C(0b0111,4)
        CMD_ACTIVE           = C(0b0011,4)
        CMD_READ             = C(0b0101,4)
        CMD_WRITE            = C(0b0100,4)
        CMD_BURST_TERMINATE  = C(0b0110,4)
        CMD_PRECHARGE        = C(0b0010,4)
        CMD_AUTO_REFRESH     = C(0b0001,4)
        CMD_LOAD_MODE        = C(0b0000,4)

        # Drive control signals from current command
        sd_cmd   = Signal(4)

        m.d.comb += [
            self.sd_cs.eq(sd_cmd[3]),
            self.sd_ras.eq(sd_cmd[2]),
            self.sd_cas.eq(sd_cmd[1]),
            self.sd_we.eq(sd_cmd[0])
        ]

        mode     = Signal(2)
        din_r    = Signal(16)

        m.d.comb += [
            self.sd_data_out.eq(din_r),
            self.sd_data_dir.eq(mode[1]),
        ]

        addr_r   = Signal(13)
        ds_r     = Signal(2)
        old_sync = Signal()

        with m.If(stage.any()):
            m.d.sdram += stage.eq(stage+1)

        m.d.sdram += [
            old_sync.eq(self.sync),
            sd_cmd.eq(CMD_INHIBIT)
        ]

        with m.If(~old_sync & self.sync):
            m.d.sdram += stage.eq(1)

        with m.If(reset != 0):
            with m.If(stage == STATE_CMD_START):
                with m.If(reset == 13):
                    m.d.sdram += [
                        sd_cmd.eq(CMD_PRECHARGE),
                        self.sd_addr[10].eq(1) # pre-charge all banks
                    ]
                with m.If(reset == 2):
                    m.d.sdram += [
                        sd_cmd.eq(CMD_LOAD_MODE),
                        self.sd_addr.eq(MODE)
                    ]
            m.d.sdram += [
                mode.eq(0),
                self.sd_dqm.eq(C(0b11,2))
            ]
        with m.Else():
            # Normal operation
            with m.If(stage == STATE_CMD_START):
                with m.If(self.we | self.oe):
                    # RAS phase
                    m.d.sdram += [
                        mode.eq(Cat(self.oe, self.we)),
                        sd_cmd.eq(CMD_ACTIVE),
                        self.sd_addr.eq(self.addr[8:21]),
                        self.sd_ba.eq(self.addr[21:23]),
                        ds_r.eq(self.ds),
                        din_r.eq(self.din),
                        addr_r.eq(Cat([self.addr[:8],self.addr[23],C(0b0010,4)]))
                    ]
                with m.Else():
                    m.d.sdram += [
                        sd_cmd.eq(CMD_AUTO_REFRESH),
                        mode.eq(0)
                    ]

            # CAS phase
            with m.If((stage == STATE_CMD_CONT) & (mode != 0)):
                m.d.sdram += [
                    sd_cmd.eq(Mux(mode[1], CMD_WRITE, CMD_READ)),
                    self.sd_addr.eq(addr_r)
                ]

                with m.If(mode[1]):
                    m.d.sdram += self.sd_dqm.eq(~ds_r)
                with m.Else():
                    m.d.sdram += self.sd_dqm.eq(C(0b00,2))

            with m.If(stage == STATE_HIGHZ):
                m.d.sdram += [
                    self.sd_dqm.eq(C(0b11,2)),
                    mode[1].eq(0)
                ]

            with m.If((stage == STATE_READ) & (mode != 0)):
                m.d.sdram += self.dout.eq(self.sd_data_in)

        return m

