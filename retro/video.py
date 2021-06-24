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
    DARK_ORANGE = 0x910000

    def __init__(self):
        # inputs
        self.x       = Signal(10)
        self.y       = Signal(10)
        self.din     = Signal(8)
        self.fin     = Signal(8)
        self.mode    = Signal(2)

        # outputs
        self.c_addr = Signal(10)
        self.f_addr = Signal(9)
        self.r      = Signal(8)
        self.g      = Signal(8)
        self.b      = Signal(8)

    def elaborate(self, platform):

        m = Module()

        xb       = Signal(9)
        ya       = Signal(9)
        yb       = Signal(9)
        row      = Signal(4)
        col      = Signal(5)
        pixcol   = Signal(4)
        lin      = Signal(5)
        pixrow   = Signal(3)
        pixel    = Signal(24)
        border   = Signal()
        mode     = Signal(2)
        obj_lin  = Signal(8)
        invert   = Signal()
        text_col = Signal(24)
        back_col = Signal(24)
        col_set  = Signal()
        din      = Signal(8)

        colors = Array([self.GREEN, self.YELLOW, self.BLUE, self.RED,
                        self.WHITE, self.CYAN, self.MAGENTA, self.ORANGE])

        m.d.comb += [
            # Hack to set mode for Rocket Patrol
            mode.eq(Mux((self.mode == 3) & (ya >= 64), 3, 0)),
            # Adjusted x and y values
            xb.eq(self.x - self.BORDER_X + 16), # Set to next byte
            ya.eq(self.y - self.BORDER_Y),
            yb.eq(ya - 64),
            # Pixel column for graphics mode
            pixcol.eq(xb[:4]),
            # Pixel column for font address
            pixrow.eq(lin[1:] - 2),
            col.eq(xb[4:]),
            invert.eq(din[6]),
            text_col.eq(Mux(invert, Mux(self.mode[1], self.DARK_ORANGE, self.DARK_GREEN), Mux(self.mode[1], self.ORANGE,self.GREEN))),
            back_col.eq(Mux(invert, Mux(self.mode[1], self.ORANGE, self.GREEN), Mux(self.mode[1], self.DARK_ORANGE, self.DARK_GREEN))),
            # Set Address of byte to fetch from video memory
            self.c_addr.eq(Mux(mode[1], 
                               Mux(xb[:4] == 14, 
                                   0x200 + Cat(ya[1:5], self.din[:5]), Cat(xb[4:], yb[5:])), # graphics
                                   0x200 + Cat(col,row))),                                   # semi-graphics
            # Set color from border and pixel
            self.r.eq(Mux(border, 0x00, pixel[16:])),
            self.g.eq(Mux(border, 0x00, pixel[8:16])),
            self.b.eq(Mux(border, 0x00, pixel[:8])),
            # Set font address
            self.f_addr.eq(Cat(pixrow, din[:6])), # 64 characters 8X12
            # Set border
            border.eq((self.x < (self.BORDER_X + 1)) | (self.x >= 640 - (self.BORDER_X + 1)) |
                      (self.y < self.BORDER_Y) | (self.y >= 480 - self.BORDER_Y))
        ]

        # In graphics mode, set the line of an object on the cycle before the object starts
        with m.If(mode[1] & (xb[:4] == 15)):
            m.d.pixel += obj_lin.eq(self.din)
        with m.Else():
            m.d.pixel += col_set.eq(self.din[5])

        with m.If(~mode[1] & (xb[:4] == 15)):
            m.d.pixel += din.eq(self.din)

        # Calculate character row and line within row, for semigraphics mode
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

        # Set pixel according to mode
        with m.If (mode[1] == 0): # Semigraphics mode
            with m.If(din[7]): # Block graphics
                with m.If((pixcol < 8) & (lin < 12)):
                    m.d.pixel += pixel.eq(Mux(din[3], colors[din[4:7]], self.BLACK))
                with m.If((pixcol >= 8) & (lin < 12)):
                    m.d.pixel += pixel.eq(Mux(din[2], colors[din[4:7]], self.BLACK))
                with m.If((pixcol < 8) & (lin >= 12)):
                    m.d.pixel += pixel.eq(Mux(din[1], colors[din[4:7]], self.BLACK))
                with m.If((pixcol >= 8) & (lin >= 12)):
                    m.d.pixel += pixel.eq(Mux(din[0], colors[din[4:7]], self.BLACK))
            with m.Else(): # Text
                with m.If((lin >= 4) & (lin < 20)):  
                    m.d.pixel += [
                        pixel.eq(Mux(self.fin.bit_select(7 - pixcol[1:], 1), text_col, back_col))
                    ]
                with m.Else():
                    m.d.pixel += pixel.eq(back_col)
        with m.Else(): # High resolution graphics
            # TODO Multi-color mode
            m.d.pixel += pixel.eq(Mux(obj_lin.bit_select(7 - xb[1:4], 1), Mux(col_set, self.GREEN, self.WHITE), self.BLACK))

        return m

