from nmigen import *

class Debouncer(Elaboratable):
    def __init__(self):
        self.btn       = Signal()
        self.btn_state = Signal(reset=0)
        self.btn_down  = Signal()
        self.btn_up    = Signal()

    def elaborate(self, platform):
        cnt      = Signal(15, reset=0)
        btn_sync = Signal(2,  reset=0)
        idle     = Signal()
        cnt_max  = Signal()

        m = Module()

        m.d.comb += [
            idle.eq(self.btn_state == btn_sync[1]),
            cnt_max.eq(cnt.all()),
            self.btn_down.eq(~idle & cnt_max & ~self.btn_state),
            self.btn_up.eq(~idle & cnt_max & self.btn_state)
        ]

        m.d.sync += [
            btn_sync[0].eq(~self.btn),
            btn_sync[1].eq(btn_sync[0])
        ]

        with m.If(idle):
            m.d.sync += cnt.eq(0)
        with m.Else():
            m.d.sync += cnt.eq(cnt + 1);
            with m.If (cnt_max):
                m.d.sync += self.btn_state.eq(~self.btn_state)

        return m
        