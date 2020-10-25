from nmigen import *

from readhex import *

class ST7789(Elaboratable):
    COLOR_BITS   = 16
    X_SIZE       = 240
    Y_SIZE       = 240
    X_BITS       = X_SIZE.bit_length()
    Y_BITS       = Y_SIZE.bit_length()
    CLK_PHASE    = 0
    CLK_POLARITY = 1
    NOP          = 0
    INIT_FILE    = "st7789_linit.mem"

    def __init__(self, reset_delay):
        self.color          = Signal(self.COLOR_BITS)
        self.x              = Signal(self.X_BITS)
        self.y              = Signal(self.Y_BITS)
        self.next_pixel     = Signal()
        self.spi_csn        = Signal()
        self.spi_clk        = Signal()
        self.spi_mosi       = Signal()
        self.spi_dc         = Signal()
        self.spi_resn       = Signal()
        self.reset_delay    = reset_delay

    # Used for simulation
    def ports(self):
        return [self.color, self.x, self.y, self.next_pixel,
                self.spi_csn, self.spi_clk, self.spi_mosi, self.spi_dc, self.spi_resn]
        
    def elaborate(self, platform):
        m = Module()

        clk_mhz = int(platform.default_clk_frequency / 1000000)

        index        = Signal(11, reset = 0)
        data         = Signal(8,  reset = self.NOP)
        dc           = Signal(1,  reset = 1)
        byte_toggle  = Signal(1,  reset = 0)
        init         = Signal(1,  reset = 1)
        num_args     = Signal(5,  reset = 0)
        delay_cnt    = Signal(28, reset = self.reset_delay * clk_mhz)
        arg          = Signal(6,  reset = 1)
        delay_set    = Signal(1,  reset = 0)
        last_cmd     = Signal(8,  reset = 0)
        resn         = Signal(1,  reset = 0)
        clken        = Signal(1,  reset = 0)
        next_byte    = Signal(8)

        init_data = readhex(self.INIT_FILE)
        oled_init = Memory(width=8, depth=len(init_data), init = init_data)
        
        m.d.comb += [
             self.spi_resn.eq(resn),
             self.spi_csn.eq(~clken),
             self.spi_dc.eq(dc),
             self.spi_clk.eq(((index[0] ^ ~self.CLK_PHASE) | ~clken) ^ ~self.CLK_POLARITY),
             self.spi_mosi.eq(data[7]),
             next_byte.eq(oled_init[index[4:]])
        ]

        with m.If(delay_cnt[-1] == 0): # Delay
            m.d.sync += [
                delay_cnt.eq(delay_cnt - 1),
                resn.eq(1)
            ]
        with m.If(index[4:] != len(init_data)):
            m.d.sync += index.eq(index+1)
            with m.If(index[0:4] == 0): # Start of byte
                with m.If(init): # Still initialization
                    m.d.sync += [
                        dc.eq(0),
                        arg.eq(arg + 1)
                    ]
                    with m.If(arg == 0):
                        m.d.sync += [
                            data.eq(self.NOP),
                            clken.eq(0),
                            last_cmd.eq(next_byte)
                        ]
                    with m.Elif(arg == 1):
                        m.d.sync += [
                            num_args.eq(next_byte[0:5]),
                            delay_set.eq(next_byte[7]),
                            data.eq(last_cmd),
                            clken.eq(1)
                        ]
                        with m.If(next_byte == 0):
                            m.d.sync += arg.eq(0)
                    with m.Elif(arg <= num_args + 1):
                        m.d.sync += [
                            data.eq(next_byte),
                            clken.eq(1),
                            dc.eq(1)
                        ]
                        with m.If((arg == num_args + 1) & ~delay_set):
                            m.d.sync += arg.eq(0)
                    with m.Elif(delay_set):
                        m.d.sync += [
                            delay_cnt.eq(clk_mhz << next_byte[0:5]), # 2^n us delay
                            data.eq(self.NOP),
                            clken.eq(0),
                            delay_set.eq(0),
                            arg.eq(0)
                        ]
                with m.Else(): # Send pixels and set x, y and next_pixel
                    m.d.sync += [
                        dc.eq(1),
                        byte_toggle.eq(~byte_toggle),
                        clken.eq(1)
                    ]
                    with m.If(byte_toggle):
                        m.d.sync += [
                            data.eq(self.color[0:8]),
                            self.next_pixel.eq(1)
                        ]
                        with m.If(self.x == self.X_SIZE - 1):
                            m.d.sync += self.x.eq(0)
                            with m.If(self.y == self.Y_SIZE -1):
                                m.d.sync += self.y.eq(0)
                            with m.Else():
                               m.d.sync += self.y.eq(self.y + 1)
                        with m.Else():
                            m.d.sync += self.x.eq(self.x + 1)
                    with m.Else():
                        m.d.sync += data.eq(self.color[8:])
            with m.Else(): # Shift out byte
                m.d.sync += self.next_pixel.eq(0)
                with m.If(index[0] == 0):
                    m.d.sync += data.eq(Cat(0b0,data[0:7]))
        with m.Else(): # Initialization done, start sending pixels
            m.d.sync += [
                init.eq(0),
                index[4:].eq(0)
            ]        
        
        return m

