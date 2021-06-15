from nmigen import *

class Video(Elaboratable):
    BORDER_X = 64
    BORDER_Y = 48

    DARK        = 0x07ff00
    YELLOW      = 0xffff00
    BLUE        = 0x3b08ff
    RED         = 0xcc003b
    WHITE       = 0xffffff
    CYAN        = 0x07e399
    MAGENTA     = 0xff1cff
    ORANGE      = 0xff8100
    BLACK       = 0x000000
    DARK_GREEN  = 0x007c00
    DRAK_ORANGE = 0x910000

    def __init__(self):
        # inputs
        self.x       = Signal(10)
        self.y       = Signal(10)
        self.din     = Signal(8)

        # outputs
        self.c_addr = Signal(9)
        self.r      = Signal(8)
        self.g      = Signal(8)
        self.b      = Signal(8)

    def elaborate(self, platform):

        m = Module()

        xa  = Signal(10)
        row = Signal(4)
        col = Signal(5)
        lin = Signal(4)

        m.d.comb += [
            xa.eq(self.x - self.BORDER_X),
            col.eq(xa[4:]),
            self.c_addr.eq(Cat(col,row))
        ]

        with m.If((self.y == self.BORDER_Y) & (self.x == 0)):
            m.d.pixel += [
                row.eq(0),
                lin.eq(0)
            ]
        with m.Elif(self.x == 639):
            m.d.pixel += lin.eq(lin + 1)
            with m.If(lin == 11):
                m.d.pixel += [
                    row.eq(row + 1),
                    lin.eq(0)
                ]

        return m

