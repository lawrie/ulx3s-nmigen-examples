from nmigen import *

FSM_IDLE = 0
FSM_SEND_CMD = 1
FSM_DONE = 2
FSM_TIMER = 3

CLK_FREQ = 25000000

class OV7670Config(Elaboratable):
    def __init__(self):
        self.sccb_ready = Signal()
        self.rom_data = Signal(16)
        self.start = Signal()
        self.rom_addr = Signal(8, reset=0)
        self.done = Signal(reset=0)
        self.sccb_addr = Signal(8, reset=0)
        self.sccb_data = Signal(8, reset=0)
        self.sccb_start = Signal(reset=0)
       
    def elaborate(self, platform):
        fsm_state = Signal(3, reset=FSM_IDLE)
        fsm_return_state = Signal(3)
        timer = Signal(32, reset=0)

        m = Module()

        with m.Switch(fsm_state):
            with m.Case(FSM_IDLE):
                m.d.sync += self.rom_addr.eq(0)
                with m.If(self.start):
                    m.d.sync += [
                        fsm_state.eq(FSM_SEND_CMD),
                        self.done.eq(0)
                    ]
            with m.Case(FSM_SEND_CMD):
                with m.Switch(self.rom_data):
                    with m.Case(0xffff):
                        m.d.sync += fsm_state.eq(FSM_DONE)
                    with m.Case(0xfff0):
                        m.d.sync += [
                            timer.eq(int(CLK_FREQ / 100)),
                            fsm_state.eq(FSM_TIMER),
                            fsm_return_state.eq(FSM_SEND_CMD),
                            self.rom_addr.eq(self.rom_addr + 1)
                        ]
                    with m.Default():
                        with m.If(self.sccb_ready):
                            m.d.sync += [
                                fsm_state.eq(FSM_TIMER),
                                fsm_return_state.eq(FSM_SEND_CMD),
                                timer.eq(0), # one cycle delay
                                self.rom_addr.eq(self.rom_addr + 1),
                                self.sccb_addr.eq(self.rom_data[8:]),
                                self.sccb_data.eq(self.rom_data[0:8]),
                                self.sccb_start.eq(1)
                            ]
            with m.Case(FSM_DONE):
                m.d.sync += [
                    fsm_state.eq(FSM_IDLE),
                    self.done.eq(1)
                ]
            with m.Case(FSM_TIMER):
                m.d.sync += self.sccb_start.eq(0)
                with m.If(timer == 0):
                    m.d.sync += fsm_state.eq(fsm_return_state)
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)

        return m

