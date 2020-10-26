from nmigen import *

class DivideBy12(Elaboratable):
    def __init__(self):
        self.numer  = Signal(6)
        self.quotient = Signal(3)
        self.remain = Signal(4)
    
    def elaborate(self, platform):
        q = Signal(3)
        r = Signal(2)

        m = Module()

        m.d.comb += self.remain.eq(Cat([self.numer[0:2], r]))
        m.d.comb += self.quotient.eq(q)

        with m.Switch(self.numer[2:]):
            with m.Case(0):
                m.d.comb += [
                    q.eq(0),
                    r.eq(0)
                ]
            with m.Case(1): 
                m.d.comb += [
                    q.eq(0),
                    r.eq(1)
                ]
            with m.Case(2): 
                m.d.comb += [
                    q.eq(0),
                    r.eq(2)
                ]
            with m.Case(3): 
                m.d.comb += [
                    q.eq(1),
                    r.eq(0)
                ]
            with m.Case(4): 
                m.d.comb += [
                    q.eq(1),
                    r.eq(1)
                ]
            with m.Case(5): 
                m.d.comb += [
                    q.eq(1),
                    r.eq(2)
                ]
            with m.Case(6): 
                m.d.comb += [
                    q.eq(2),
                    r.eq(0)
                ]
            with m.Case(7): 
                m.d.comb += [
                    q.eq(2),
                    r.eq(1)
                ]
            with m.Case(8): 
                m.d.comb += [
                    q.eq(2),
                    r.eq(2)
                ]
            with m.Case(9): 
                m.d.comb += [
                    q.eq(3),
                    r.eq(0)
                ]
            with m.Case(10): 
                m.d.comb += [
                    q.eq(3),
                    r.eq(1)
                ]
            with m.Case(11): 
                m.d.comb += [
                    q.eq(3),
                    r.eq(2)
                ]
            with m.Case(12): 
                m.d.comb += [
                    q.eq(4),
                    r.eq(0)
                ]
            with m.Case(13): 
                m.d.comb += [
                    q.eq(4),
                    r.eq(1)
                ]
            with m.Case(14): 
                m.d.comb += [
                    q.eq(4),
                    r.eq(2)
                ]
            with m.Case(15): 
                m.d.comb += [
                    q.eq(5),
                    r.eq(0)
                ]

        return m

