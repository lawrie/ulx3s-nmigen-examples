import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

from ecp5pll import ECP5PLL
from sdram_controller16 import sdram_controller

# Diagnostic led Pmods
pmod_led8_0 = [
    Resource("led8_0", 0,
        Subsignal("leds", Pins("0+ 1+ 2+ 3+ 0- 1- 2- 3-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

pmod_led8_1 = [
    Resource("led8_1", 0,
        Subsignal("leds", Pins("7+ 8+ 9+ 10+ 7- 8- 9- 10-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

pmod_led8_2 = [
    Resource("led8_2", 0,
        Subsignal("leds", Pins("21+ 22+ 23+ 24+ 21- 22- 23- 24-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

pmod_led8_3 = [
    Resource("led8_3", 0,
        Subsignal("leds", Pins("14+ 15+ 16+ 17+ 14- 15- 16- 17-", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

# Test of 16-bit SDRAM controller
class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        # Get pins
        led = [platform.request("led",count) for count in range(8)]
        leds = Cat([i.o for i in led])
        led8_0 = platform.request("led8_0")
        led8_1 = platform.request("led8_1")
        led8_2 = platform.request("led8_2")
        led8_3 = platform.request("led8_3")
        led16 =  [i for i in led8_0] + [i for i in led8_1]
        leds16 = Cat([i for i in led16])
        led16_2 =  [i for i in led8_3] + [i for i in led8_2]
        leds16_2 = Cat([i for i in led16_2])
        clk_in = platform.request(platform.default_clk, dir='-')[0]

        # Clock generation
        # PLL - 64MHz for sdram
        sdram_freq = 100000000
        m.domains.sdram = cd_sdram = ClockDomain("sdram")
        m.domains.sdram_clk = cd_sdram_clk = ClockDomain("sdram_clk")

        m.submodules.ecp5pll = pll = ECP5PLL()
        pll.register_clkin(clk_in,  platform.default_clk_frequency)
        pll.create_clkout(cd_sdram, sdram_freq)
        pll.create_clkout(cd_sdram_clk, sdram_freq, phase=180)

        # Divide clock by 8
        div = Signal(3)
        m.d.sdram += div.eq(div+1)

        # Make sync domain 8MHz
        m.domains.sync = cd_sync = ClockDomain("sync")
        m.d.comb += ClockSignal().eq(div[2])

        # Power-on reset, used to setup SDRAM as using pll.locked does not work
        reset_cnt = Signal(5, reset=0)
        with m.If(~reset_cnt.all()):
            m.d.sync += reset_cnt.eq(reset_cnt+1)

        # Add the SDRAM controller
        m.submodules.mem = mem = sdram_controller()

        # RAM test
        addr   = Signal(24, reset=0) # word address
        count  = Signal(5,  reset=0) # width control speed of read back
        we     = Signal(1,  reset=0) # request write
        oe     = Signal(1,  reset=0) # request read
        read   = Signal(1,  reset=0) # Set for read back phase
        err    = Signal(1,  reset=0) # Set when error is detected
        passed = Signal(1,  reset=0) # Set if test passed

        m.d.comb += [
            mem.init.eq(reset_cnt == 0), # Initialize SDRAM
            mem.sync.eq(div[2]),         # Sync with sync domain clock
            mem.address.eq(addr),
            mem.req_read.eq(oe),
            mem.req_write.eq(we),
            mem.data_in.eq(addr[:16]),   # Write least significant 16 bits of address
            leds16_2.eq(addr[:16]),      # Show the address on leds
            leds16.eq(mem.data_out)      # Put the data read on the debug leds
        ]

        # Set the error flag if read gives the wrong value
        with m.If((count > 0) & read & (mem.data_out != addr[:16])):
            m.d.sync += err.eq(1)

        # Increment count and do transfer when count is 0
        m.d.sync += [
            count.eq(count+1),
            we.eq((count == 0) & ~read),
            oe.eq((count == 0) & read)
        ]

        # Increment address every other cycle for write or when
        # count is exhausted for reads
        with m.If(reset_cnt.all() & ((~read & (count == 1)) | count.all())):
            with m.If(~read & (count == 1)):
                m.d.sync += count.eq(0)

            m.d.sync += addr.eq(addr+1)

            with m.If(addr.all()):
                # Switch to read when all data is written
                m.d.sync += read.eq(1)

                # Set passed flag when all data has been read without an error
                with m.If(read & ~err):
                    m.d.sync += passed.eq(1)

        # Show flags on the leds
        # Blue led on during write phase, green led means passed, red means error
        m.d.comb += leds.eq(Cat([err, C(0,1), passed, ~read]))

        return m

if __name__ == "__main__":
    variants = {
        '12F': ULX3S_12F_Platform,
        '25F': ULX3S_25F_Platform,
        '45F': ULX3S_45F_Platform,
        '85F': ULX3S_85F_Platform
    }

    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    args = parser.parse_args()

    platform = variants[args.variant]()
    platform.add_resources(pmod_led8_0)
    platform.add_resources(pmod_led8_1)
    platform.add_resources(pmod_led8_2)
    platform.add_resources(pmod_led8_3)


    platform.build(Top(), do_program=True)

