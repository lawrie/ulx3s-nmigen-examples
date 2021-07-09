from enum import IntEnum

from nmigen import *

class OV7670ConfigState(IntEnum):
    IDLE     = 0
    SEND_CMD = 1
    DONE     = 2
    TIMER    = 3

class OV7670Config(Elaboratable):
    def __init__(self):
        self.sccb_ready = Signal()
        self.rom_data   = Signal(16)
        self.start      = Signal()
        self.rom_addr   = Signal(8, reset=0)
        self.done       = Signal(reset=0)
        self.sccb_addr  = Signal(8, reset=0)
        self.sccb_data  = Signal(8, reset=0)
        self.sccb_start = Signal(reset=0)
       
    def elaborate(self, platform):
        fsm_state        = Signal(3, reset=OV7670ConfigState.IDLE)
        fsm_return_state = Signal(3)
        timer            = Signal(32, reset=0)

        m = Module()

        with m.Switch(fsm_state):
            with m.Case(OV7670ConfigState.IDLE):
                m.d.sync += self.rom_addr.eq(0)
                with m.If(self.start):
                    m.d.sync += [
                        fsm_state.eq(OV7670ConfigState.SEND_CMD),
                        self.done.eq(0)
                    ]
            with m.Case(OV7670ConfigState.SEND_CMD):
                with m.Switch(self.rom_data):
                    with m.Case(0xffff):
                        m.d.sync += fsm_state.eq(OV7670ConfigState.DONE)
                    with m.Case(0xfff0):
                        m.d.sync += [
                            timer.eq(int(platform.default_clk_frequency / 100)),
                            fsm_state.eq(OV7670ConfigState.TIMER),
                            fsm_return_state.eq(OV7670ConfigState.SEND_CMD),
                            self.rom_addr.eq(self.rom_addr + 1)
                        ]
                    with m.Default():
                        with m.If(self.sccb_ready):
                            m.d.sync += [
                                fsm_state.eq(OV7670ConfigState.TIMER),
                                fsm_return_state.eq(OV7670ConfigState.SEND_CMD),
                                timer.eq(0), # one cycle delay
                                self.rom_addr.eq(self.rom_addr + 1),
                                self.sccb_addr.eq(self.rom_data[8:]),
                                self.sccb_data.eq(self.rom_data[0:8]),
                                self.sccb_start.eq(1)
                            ]
            with m.Case(OV7670ConfigState.DONE):
                m.d.sync += [
                    fsm_state.eq(OV7670ConfigState.IDLE),
                    self.done.eq(1)
                ]
            with m.Case(OV7670ConfigState.TIMER):
                m.d.sync += self.sccb_start.eq(0)
                with m.If(timer == 0):
                    m.d.sync += fsm_state.eq(fsm_return_state)
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)

        return m

