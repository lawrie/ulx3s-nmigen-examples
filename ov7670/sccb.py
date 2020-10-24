from nmigen import *

CAMERA_ADDR = 0x42
FSM_IDLE = 0
FSM_START_SIGNAL = 1
FSM_LOAD_BYTE = 2
FSM_TX_BYTE_1 = 3
FSM_TX_BYTE_2 = 4
FSM_TX_BYTE_3 = 5
FSM_TX_BYTE_4 = 6
FSM_END_SIGNAL_1 = 7
FSM_END_SIGNAL_2 = 8
FSM_END_SIGNAL_3 = 9
FSM_END_SIGNAL_4 = 10
FSM_DONE = 11
FSM_TIMER = 12

CLK_FREQ = 25000000
SCCB_FREQ = 100000

class SCCB(Elaboratable):
    def __init__(self):
        self.start = Signal()
        self.address = Signal(8)
        self.data = Signal(8)
        self.ready = Signal(reset=1)
        self.sioc_oe = Signal(reset=0)
        self.siod_oe = Signal(reset=0)

    def elaborate(self, platform):
        m = Module()
        
        fsm_state = Signal(4, reset=0)
        fsm_return_state = Signal(4, reset=0)
        timer = Signal(32, reset=0)
        latched_address = Signal(8)
        latched_data = Signal(8)
        byte_counter = Signal(2, reset=0)
        tx_byte = Signal(8, reset=0)
        byte_index = Signal(4, reset=0)

        with m.Switch(fsm_state):
            with m.Case(FSM_IDLE):
                m.d.sync += [
                    byte_index.eq(0),
                    byte_counter.eq(0),
                    self.sioc_oe.eq(0),
                    self.siod_oe.eq(0)
                ]
                with m.If(self.start):
                    m.d.sync += [
                        fsm_state.eq(FSM_START_SIGNAL),
                        latched_address.eq(self.address),
                        latched_data.eq(self.data),
                        self.ready.eq(0)
                    ]
                with m.Else():
                    m.d.sync += self.ready.eq(1)
            with m.Case(FSM_START_SIGNAL):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_LOAD_BYTE),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.sioc_oe.eq(0),
                    self.siod_oe.eq(1)
                ]
            with m.Case(FSM_LOAD_BYTE):
                m.d.sync += [
                    byte_counter.eq(byte_counter + 1),
                    byte_index.eq(0)
                ]
                with m.If(byte_counter == 3):
                    m.d.sync += fsm_state.eq(FSM_END_SIGNAL_1)
                with m.Else():
                    m.d.sync += fsm_state.eq(FSM_TX_BYTE_1)
                with m.Switch(byte_counter):
                    with m.Case(0):
                        m.d.sync += tx_byte.eq(CAMERA_ADDR)
                    with m.Case(1):
                        m.d.sync += tx_byte.eq(latched_address)
                    with m.Case(2):
                        m.d.sync += tx_byte.eq(latched_data)
                    with m.Default():
                        m.d.sync += tx_byte.eq(latched_data)
            with m.Case(FSM_TX_BYTE_1):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_TX_BYTE_2),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.sioc_oe.eq(1)
                ]
            with m.Case(FSM_TX_BYTE_2):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_TX_BYTE_3),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ)))
                ]
                with m.If(byte_index == 8):
                    m.d.sync += self.siod_oe.eq(0)
                with m.Else():
                    m.d.sync += self.siod_oe.eq(~tx_byte[7])
            with m.Case(FSM_TX_BYTE_3):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_TX_BYTE_4),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.sioc_oe.eq(0)
                ]
            with m.Case(FSM_TX_BYTE_4):
                m.d.sync += [
                    tx_byte.eq(tx_byte << 1),
                    byte_index.eq(byte_index + 1)
                ]
                with m.If(byte_index == 8):
                    m.d.sync += fsm_state.eq(FSM_LOAD_BYTE)
                with m.Else():
                    m.d.sync += fsm_state.eq(FSM_TX_BYTE_1)
            with m.Case(FSM_END_SIGNAL_1):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_END_SIGNAL_2),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.sioc_oe.eq(1)
                ]
            with m.Case(FSM_END_SIGNAL_2):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_END_SIGNAL_3),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.siod_oe.eq(1)
                ]
            with m.Case(FSM_END_SIGNAL_3):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_END_SIGNAL_4),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.sioc_oe.eq(0)
                ]
            with m.Case(FSM_END_SIGNAL_4):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_DONE),
                    timer.eq(int(CLK_FREQ / (4 * SCCB_FREQ))),
                    self.siod_oe.eq(0)
                ]
            with m.Case(FSM_DONE):
                m.d.sync += [
                    fsm_state.eq(FSM_TIMER),
                    fsm_return_state.eq(FSM_IDLE),
                    timer.eq(int((2 * CLK_FREQ) / SCCB_FREQ)),
                    byte_counter.eq(0)                    
                ]
            with m.Case(FSM_TIMER):
                with m.If(timer == 0):
                    m.d.sync += [
                        fsm_state.eq(fsm_return_state),
                        timer.eq(0)
                    ]
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)

        return m

