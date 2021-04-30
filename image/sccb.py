from enum import IntEnum

from nmigen import *

class SCCBState(IntEnum):
    IDLE         = 0
    START_SIGNAL = 1
    LOAD_BYTE    = 2
    TX_BYTE_1    = 3
    TX_BYTE_2    = 4
    TX_BYTE_3    = 5
    TX_BYTE_4    = 6
    END_SIGNAL_1 = 7
    END_SIGNAL_2 = 8
    END_SIGNAL_3 = 9
    END_SIGNAL_4 = 10
    DONE         = 11
    TIMER        = 12

class SCCB(Elaboratable):
    def __init__(self):
        self.start   = Signal()
        self.address = Signal(8)
        self.data    = Signal(8)
        self.ready   = Signal(reset=1)
        self.sioc_oe = Signal(reset=0)
        self.siod_oe = Signal(reset=0)

    def elaborate(self, platform):
        m = Module()
        
        camera_addr = 0x42
        sccb_freq   = 100000

        fsm_state        = Signal(4, reset=0)
        fsm_return_state = Signal(4, reset=0)
        timer            = Signal(32, reset=0)
        latched_address  = Signal(8)
        latched_data     = Signal(8)
        byte_counter     = Signal(2, reset=0)
        tx_byte          = Signal(8, reset=0)
        byte_index       = Signal(4, reset=0)

        delay1 = int(platform.default_clk_frequency / (4 * sccb_freq))
        delay2 = int((2 * platform.default_clk_frequency) / sccb_freq)

        with m.Switch(fsm_state):
            with m.Case(SCCBState.IDLE):
                m.d.sync += [
                    byte_index.eq(0),
                    byte_counter.eq(0),
                    self.sioc_oe.eq(0),
                    self.siod_oe.eq(0)
                ]
                with m.If(self.start):
                    m.d.sync += [
                        fsm_state.eq(SCCBState.START_SIGNAL),
                        latched_address.eq(self.address),
                        latched_data.eq(self.data),
                        self.ready.eq(0)
                    ]
                with m.Else():
                    m.d.sync += self.ready.eq(1)
            with m.Case(SCCBState.START_SIGNAL):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.LOAD_BYTE),
                    timer.eq(delay1),
                    self.sioc_oe.eq(0),
                    self.siod_oe.eq(1)
                ]
            with m.Case(SCCBState.LOAD_BYTE):
                m.d.sync += [
                    byte_counter.eq(byte_counter + 1),
                    byte_index.eq(0)
                ]
                with m.If(byte_counter == 3):
                    m.d.sync += fsm_state.eq(SCCBState.END_SIGNAL_1)
                with m.Else():
                    m.d.sync += fsm_state.eq(SCCBState.TX_BYTE_1)
                with m.Switch(byte_counter):
                    with m.Case(0):
                        m.d.sync += tx_byte.eq(camera_addr)
                    with m.Case(1):
                        m.d.sync += tx_byte.eq(latched_address)
                    with m.Case(2):
                        m.d.sync += tx_byte.eq(latched_data)
                    with m.Default():
                        m.d.sync += tx_byte.eq(latched_data)
            with m.Case(SCCBState.TX_BYTE_1):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.TX_BYTE_2),
                    timer.eq(delay1),
                    self.sioc_oe.eq(1)
                ]
            with m.Case(SCCBState.TX_BYTE_2):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.TX_BYTE_3),
                    timer.eq(delay1)
                ]
                with m.If(byte_index == 8):
                    m.d.sync += self.siod_oe.eq(0)
                with m.Else():
                    m.d.sync += self.siod_oe.eq(~tx_byte[7])
            with m.Case(SCCBState.TX_BYTE_3):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.TX_BYTE_4),
                    timer.eq(delay1),
                    self.sioc_oe.eq(0)
                ]
            with m.Case(SCCBState.TX_BYTE_4):
                m.d.sync += [
                    tx_byte.eq(tx_byte << 1),
                    byte_index.eq(byte_index + 1)
                ]
                with m.If(byte_index == 8):
                    m.d.sync += fsm_state.eq(SCCBState.LOAD_BYTE)
                with m.Else():
                    m.d.sync += fsm_state.eq(SCCBState.TX_BYTE_1)
            with m.Case(SCCBState.END_SIGNAL_1):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.END_SIGNAL_2),
                    timer.eq(delay1),
                    self.sioc_oe.eq(1)
                ]
            with m.Case(SCCBState.END_SIGNAL_2):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.END_SIGNAL_3),
                    timer.eq(delay1),
                    self.siod_oe.eq(1)
                ]
            with m.Case(SCCBState.END_SIGNAL_3):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.END_SIGNAL_4),
                    timer.eq(delay1),
                    self.sioc_oe.eq(0)
                ]
            with m.Case(SCCBState.END_SIGNAL_4):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.DONE),
                    timer.eq(delay1),
                    self.siod_oe.eq(0)
                ]
            with m.Case(SCCBState.DONE):
                m.d.sync += [
                    fsm_state.eq(SCCBState.TIMER),
                    fsm_return_state.eq(SCCBState.IDLE),
                    timer.eq(delay2),
                    byte_counter.eq(0)                    
                ]
            with m.Case(SCCBState.TIMER):
                with m.If(timer == 0):
                    m.d.sync += [
                        fsm_state.eq(fsm_return_state),
                        timer.eq(0)
                    ]
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)

        return m

