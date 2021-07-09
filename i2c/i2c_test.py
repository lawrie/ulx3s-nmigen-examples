from nmigen import *
from nmigen.build import *
from nmigen_boards.blackice_mx import *

from i2c_master import I2cMaster

i2c_pmod = [
    Resource("i2c", 0,
            Subsignal("sda", Pins("7", conn=("pmod",5)), Attrs(IO_STANDARD="SB_LVCMOS")),
            Subsignal("scl", Pins("8", conn=("pmod",5)), Attrs(IO_STANDARD="SB_LVCMOS")))
]

leds8_1_pmod = [
    Resource("leds8_1", 0,
            Subsignal("leds", Pins("7 8 9 10 1 2 3 4", dir="o", conn=("pmod",2)), Attrs(IO_STANDARD="SB_LVCMOS")))
]

leds8_2_pmod = [
    Resource("leds8_2", 0,
            Subsignal("leds", Pins("7 8 9 10 1 2 3 4", dir="o", conn=("pmod",3)), Attrs(IO_STANDARD="SB_LVCMOS")))
]

class Top(Elaboratable):
    def elaborate(self, platform):
        leds  = Cat([platform.request("led", i) for i in range(4)])
        leds8_1 = Cat(l for l in platform.request("leds8_1"))
        leds8_2 = Cat(l for l in platform.request("leds8_2"))

        m = Module()

        timer = Signal(28)

        m.submodules.i2c = i2c = I2cMaster()

        ack = Signal()

        # Scan for i2c addresses
        with m.If(~i2c.addr_nack & ~i2c.addr[0]):
            m.d.sync += leds8_2.eq(i2c.addr)

        m.d.sync += timer.eq(timer + 1)

        m.d.comb += [
            i2c.addr.eq(timer[-8:]),
            #i2c.addr.eq(0x52),
            i2c.valid.eq(timer[:-8].all()),
            i2c.read.eq(0),
            i2c.rep_start.eq(0),
            i2c.short_wr.eq(1),
            i2c.reg.eq(0x40),
            i2c.din.eq(0x00),
            i2c.din2.eq(0x00),
            leds[0].eq(i2c.rdy),
            leds[1].eq(i2c.addr_nack),
            leds[2].eq(i2c.data_nack),
            leds[3].eq(i2c.init),
            leds8_1.eq(i2c.diag),
            #leds8_2.eq(i2c.addr)
        ]

        return m

if __name__ == "__main__":
    platform = BlackIceMXPlatform()
    platform.add_resources(i2c_pmod)
    platform.add_resources(leds8_1_pmod)
    platform.add_resources(leds8_2_pmod)
    platform.build(Top(), do_program=True)
