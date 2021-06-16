from nmigen import *

class Video(Elaboratable):
    BORDER_X = 64
    BORDER_Y = 48

    GREEN       = 0x07ff00
    YELLOW      = 0xffff00
    BLUE        = 0x3b08ff
    RED         = 0xcc003b
    WHITE       = 0xffffff
    CYAN        = 0x07e399
    MAGENTA     = 0xff1cff
    ORANGE      = 0xff8100
    BLACK       = 0x000000
    DARK_GREEN  = 0x003c00
    DRAK_ORANGE = 0x910000

    def __init__(self):
        # inputs
        self.x       = Signal(10)
        self.y       = Signal(10)
        self.din     = Signal(8)
        self.fin     = Signal(8)
        self.mode    = Signal(2)

        # outputs
        self.c_addr = Signal(9)
        self.f_addr = Signal(9)
        self.r      = Signal(8)
        self.g      = Signal(8)
        self.b      = Signal(8)

    def elaborate(self, platform):

        m = Module()

        xa     = Signal(10)
        row    = Signal(4)
        col    = Signal(5)
        pixcol = Signal(4)
        lin    = Signal(5)
        pixrow = Signal(3)
        pixel  = Signal(24)
        border = Signal()

        colors = Array([self.GREEN, self.YELLOW, self.BLUE, self.RED,
                        self.WHITE, self.CYAN, self.MAGENTA, self.ORANGE])

        m.d.comb += [
            xa.eq(self.x - self.BORDER_X),
            pixcol.eq(xa[:4]),
            col.eq(xa[4:]),
            self.c_addr.eq(Cat(col,row)),
            self.r.eq(Mux(border, 0x00, pixel[16:])),
            self.g.eq(Mux(border, 0x00, pixel[8:16])),
            self.b.eq(Mux(border, 0x00, pixel[:8])),
            pixrow.eq(lin[1:] - 2),
            self.f_addr.eq(Cat(pixrow, self.din[:6])),
            border.eq((self.x < self.BORDER_X) | (self.x >= 640 - self.BORDER_X) |
                      (self.y < self.BORDER_Y) | (self.y >= 480 - self.BORDER_Y))
        ]

        m.d.pixel += pixel.eq(self.BLACK)

        with m.If((self.y == self.BORDER_Y) & (self.x == 0)):
            m.d.pixel += [
                row.eq(0),
                lin.eq(0)
            ]
        with m.Elif(self.x == 639):
            m.d.pixel += lin.eq(lin + 1)
            with m.If(lin == 23):
                m.d.pixel += [
                    row.eq(row + 1),
                    lin.eq(0)
                ]

        with m.If (self.mode[1] == 0):
            # Semigraphics mode
            with m.If(self.din[7]): # Block graphics
                m.d.pixel += pixel.eq(self.WHITE)
                with m.If((pixcol < 8) & (lin < 12)):
                    m.d.pixel += pixel.eq(Mux(self.din[3], colors[self.din[4:7]], self.BLACK))
                with m.If((pixcol >= 8) & (lin < 12)):
                    m.d.pixel += pixel.eq(Mux(self.din[2], colors[self.din[4:7]], self.BLACK))
                with m.If((pixcol < 8) & (lin >= 12)):
                    m.d.pixel += pixel.eq(Mux(self.din[1], colors[self.din[4:7]], self.BLACK))
                with m.If((pixcol >= 8) & (lin >= 12)):
                    m.d.pixel += pixel.eq(Mux(self.din[0], colors[self.din[4:7]], self.BLACK))
            with m.Else(): # Text
                with m.If((lin >= 4) & (lin < 20)):  
                    m.d.pixel += [
                        pixel.eq(Mux(self.fin.bit_select(7 - pixcol[1:], 1), self.GREEN, self.DARK_GREEN))
                    ]
                with m.Else():
                    m.d.pixel += pixel.eq(self.DARK_GREEN)
        with m.Else(): # High resolution graphics
            m.d.pixel += pixel.eq(self.YELLOW)

        return m

