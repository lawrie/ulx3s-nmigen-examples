# ULX3S nMigen examples
This repository contains [nMigen](https://github.com/nmigen/nmigen) examples for the [ULX3S FPGA board](https://ulx3s.github.io/). You need to have [Yosys](https://github.com/YosysHQ/yosys), [nextpnr](https://github.com/YosysHQ/nextpnr), [project Trellis](https://github.com/YosysHQ/prjtrellis), and [openFPGAloader](https://github.com/trabucayre/openFPGALoader) installed.

Each directory contains an example, which you can build and run by simply running:

```bash
python top_<example>.py <FPGA variant>
```

where `<FPGA variant>` is either `12F`, `25F`, `45F`, or `85F` depending on the size of the FPGA on your ULX3S board. I have an `85F` board so to build the `dvi` example, I run:

```bash
python top_vgatest.py 85F
```

in the `dvi` folder.

You will need nextpnr-ecp5 on your path.

The other examples are run in a siimilar way.

Some of the examples support simulation as well as running on the board.

The examples have been ported from a variety of sources.

## Examples

### blinky

blinky.py blinks  led 0. It demonstrates how to synthesise a simple nMigen module on the Ulx3s board.

```python
import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

class Blinky(Elaboratable):
    def elaborate(self, platform):
        led   = platform.request("led", 0)
        timer = Signal(24)

        m = Module()
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += led.o.eq(timer[-1])
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
    platform.build(Blinky(), do_program=True)
```

### leds

Running leds.py counts on the 8 leds. It uses a timer that wraps round into about every second, and sets the 8 leds to the most significant bits of the timer.
You can adjust the width of the timer to set the speed.

```python
```

leds16.py counts on 2 digilent 8-LED Pmods, connected on pmods 2 and 3.

This example shows how to define resources connected to Pmods.

```python
import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

class Leds(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(8)]
        timer = Signal(30)

        m = Module()
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += Cat([i.o for i in led]).eq(timer[-9:-1])
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
    platform.build(Leds(), do_program=True)
```

ledglow.py makes all 8 leds glow using PWM.

```python
import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

class LedGlow(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(8)]
        cnt = Signal(26)
        pwm_input = Signal(4)
        pwm = Signal(5)

        m = Module()

        m.d.sync += [
            cnt.eq(cnt + 1),
            pwm.eq(pwm[0:-1] + pwm_input)
        ]

        with m.If(cnt[-1]):
            m.d.sync += pwm_input.eq(cnt[-5:])
        with m.Else():
            m.d.sync += pwm_input.eq(~cnt[-5:])

        for l in led:
            m.d.comb += l.eq(pwm[-1])

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
    platform.build(LedGlow(), do_program=True)
```

### debounce

Debounces buttons.

The Debouncer is based on the one from fpga4fun.com.

```python
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
```

The test program, debounce.py counts up on the 8 leds, when you press button 1.

```python
import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

from debouncer import *

class Debounce(Elaboratable):
    def elaborate(self, platform):
        led  = [platform.request("led", i) for i in range(8)]
        btn1 = platform.request("button_fire", 0)
        leds = Cat([led[i].o for i in range(8)])

        m = Module()

        debouncer = Debouncer()
        m.submodules.debouncer = debouncer

        m.d.comb += debouncer.btn.eq(btn1)

        with m.If(debouncer.btn_up):
            m.d.sync += leds.eq(leds + 1)

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
    platform.build(Debounce(), do_program=True)
```

### seven_segment

This needs a Digilent 7-segment Pmod on the gpio pins 14 - 24.

There is a separate module to set the 7-segment leds to a given hex value:

```python
from nmigen import *

class SevenSegController(Elaboratable):
    def __init__(self):
        self.val  = Signal(4)
        self.leds = Signal(7)

    def elaborate(self, platform):
        m = Module()

        table = Array([
            0b0111111, # 0
            0b0000110, # 1
            0b1011011, # 2
            0b1001111, # 3
            0b1100110, # 4
            0b1101101, # 5
            0b1111101, # 6
            0b0000111, # 7
            0b1111111, # 8
            0b1101111, # 9
            0b1110111, # A
            0b1111100, # B
            0b0111001, # C
            0b1011110, # D
            0b1111001, # E
            0b1110001  # F
        ])

        m.d.comb += self.leds.eq(table[self.val])

        return m
```

And the test program, seven_test.py:

```python
import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *
from seven_seg import SevenSegController

seven_seg_pmod = [
    Resource("seven_seg", 0,
             Subsignal("aa", Pins("24-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ab", Pins("23-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ac", Pins("22-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ad", Pins("21-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ae", Pins("17-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("af", Pins("16-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ag", Pins("15-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")),
             Subsignal("ca", Pins("14-", dir="o", conn=("gpio", 0)), Attrs(IO_TYPE="LVCMOS33")))
]

class SevenTest(Elaboratable):
    def elaborate(self, platform):
        led = [platform.request("led", i) for i in range(8)]
        sw = [platform.request("switch", i) for i in range(4)]
        btn = [platform.request("button_pwr"),
               platform.request("button_fire", 0),
               platform.request("button_fire", 1),
               platform.request("button_up"),
               platform.request("button_down"),
               platform.request("button_left"),
               platform.request("button_right")]
        seg_pins = platform.request("seven_seg")

        timer = Signal(26)
        seven = SevenSegController()

        m = Module()
        m.submodules.seven = seven
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += [
            Cat([i.o for i in led]).eq(timer[-9:-1]),
            Cat([seg_pins.aa, seg_pins.ab, seg_pins.ac, seg_pins.ad,
                 seg_pins.ae, seg_pins.af, seg_pins.ag]).eq(seven.leds),
            seg_pins.ca.eq(timer[-1])
        ]
        with m.If(btn[1]):
             m.d.comb += seven.val.eq(Cat([i.i for i in sw]))
        with m.Else():
             m.d.comb += seven.val.eq(timer[-5:-1])

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
    platform.add_resources(seven_seg_pmod)
    platform.build(SevenTest(), do_program=True)
```

Or, you can run the simulation, seven_seg_sim.py

```python
from nmigen import *
from nmigen.sim import *
from seven_seg import SevenSegController

def print_seven(leds):
    line_top = ["   ", " _ "]
    line_mid = ["   ", "  |", " _ ", " _|", "|  ", "| |", "|_ ", "|_|"]
    line_bot = line_mid

    a = leds & 1
    fgb = ((leds >> 1) & 1) | ((leds >> 5) & 2) | ((leds >> 3) & 4)
    edc = ((leds >> 2) & 1) | ((leds >> 2) & 2) | ((leds >> 2) & 4)

    print(line_top[a])
    print(line_mid[fgb])
    print(line_bot[edc])


if __name__ == "__main__":
    def process():
        for i in range(16):
            yield dut.val.eq(i)
            yield Delay()
            print_seven((yield dut.leds))
    dut = SevenSegController()
    sim = Simulator(dut)
    sim.add_process(process)
    sim.run()
```

The two digit Dilgilent 7-segment Pmod has pins for driving just one 7-segment digit, and another pin (ca) selects which digit is active. To display values on both digits, you need to switch between each digit and display the required value on each digit at least one hundred times a second, so that the digits appear to be permanently lit.

### audio

These are audio examples from [fpga4fun.com](https://www.fpga4fun.com/MusicBox.html).

All these examples use a very simple way of generating tones on the audio output pin. They just generate a square wave by reversing the pin polarity at the required frequency.

More complex waveforms can be generated by using pulse width or pulse density modulation, which is used in the audio_stream example.

music1.py plays middle C:

```python
import argparse

from nmigen import *
from nmigen.build import *
from nmigen_boards.ulx3s import *

stereo = [
    Resource("stereo", 0,
        Subsignal("l", Pins("E4 D3 C3 B3", dir="o")),
        Subsignal("r", Pins("A3 B5 D5 C5", dir="o")),
    )
]

class Music1(Elaboratable):
    def elaborate(self, platform):
        stereo  = platform.request("stereo", 0)

        m = Module()

        left = stereo.l.o
        clkdivider = int(platform.default_clk_frequency / 440 / 2)
        counter = Signal(clkdivider.bit_length())

        with m.If(counter == 0):
           m.d.sync += [
               counter.eq(clkdivider - 1),
               left.eq(15 - left)
           ]
        with m.Else():
           m.d.sync += counter.eq(counter - 1)

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
    platform.add_resources(stereo)
    platform.build(Music1(), do_program=True)
```

music2.py plays 2 tones alternating:

music2a.py plays a siren:

music3.py plays a scale. It uses a divideby12 module:

music4.py plays a tune. It uses a readint function to read the tune from a file:


### audio_stream

This example is based on the fpga4fun uart audio_stream example.

Run stream.py:

And then on Linux systems with mpg123 installed, do:

```sh
mpg123 -m -s -4 --8bit <flename>.mp3 >$DEVICE
```

The quality is not very good.

### ps2_keyboard

The PS/2 protocol is a very simple one, using tow pins: a clock and and a data pin. In this example, the pins are input-only (keyboard to host), but the PS/2 protocol does allow host to device output for simple configuration of the device, such as setting leds.

An 8-bit scan code is read in a frame of 1o bits: a start bit, 8 data bits, and parity.

Information on PS/2 scan codes can be found [here](https://techdocs.altium.com/display/FPGA/PS2+Keyboard+Scan+Codes).

This is the PS/2 keyboard controller, ps2.v:

```python
from nmigen import *

class PS2(Elaboratable):
    def __init__(self):
        self.ps2_clk  = Signal(1)
        self.ps2_data = Signal(1)
        self.data     = Signal(8, reset=0)
        self.valid    = Signal(1, reset=0)
        self.error    = Signal(1, reset=0)

    def elaborate(self, platform):
        clk_filter  = Signal(8, reset=0xff)
        ps2_clk_in  = Signal(1, reset=1)
        ps2_data_in = Signal(1, reset=1)
        clk_edge    = Signal(1, reset=0)
        bit_count   = Signal(4, reset=0)
        shift_reg   = Signal(9, reset=0)
        parity      = Signal(1, reset=0)

        m = Module()

        m.d.sync += [
            ps2_data_in.eq(self.ps2_data),
            clk_filter.eq(Cat(clk_filter[1:], self.ps2_clk)),
            clk_edge.eq(0)
        ]

        with m.If(clk_filter.all()):
            m.d.sync += ps2_clk_in.eq(1)
        with m.Elif(clk_filter == 0):
            with m.If(ps2_clk_in):
                m.d.sync += clk_edge.eq(1)
            m.d.sync += ps2_clk_in.eq(0)

        m.d.sync += [
            self.valid.eq(0),
            self.error.eq(0)
        ]

        with m.If(clk_edge):
           with m.If(bit_count == 0):
               m.d.sync += parity.eq(0)
               with m.If(~ps2_data_in):
                   m.d.sync += bit_count.eq(bit_count + 1)
           with m.Else():
               with m.If(bit_count < 10):
                   m.d.sync += [
                       bit_count.eq(bit_count + 1),
                       shift_reg.eq(Cat([shift_reg[1:],ps2_data_in])),
                       parity.eq(parity ^ ps2_data_in)
                   ]
               with m.Elif(ps2_data_in):
                   m.d.sync += bit_count.eq(0)
                   with m.If(parity):
                       m.d.sync += [
                           self.data.eq(shift_reg[:8]),
                           self.valid.eq(1)
                       ]
                   with m.Else():
                       m.d.sync += self.error.eq(1)
               with m.Else():
                    m.d.sync += [
                        bit_count.eq(0),
                        self.error.eq(1)
                    ]

        return m
```

When you press a key on the keyboard the scan codes are written in hex to the uart, so run `cat $DEVICE`.

### rotary_encoder

This needs a quadrature rotary encoder connected to pins 2- and 3-.

Run rotary_encoder.py and see the leds change when yor turn the knob.

### oled

This needs a 7-pin spi ssd1331 oled display.

Run top_oled_vga.py to put a pattern on the display.

### st7789

This needs a 7-pin spi st7789 display.

The st7789 is a 240x240 color display, as opposed to the 96x64 resolution of the sdd1331, but the prices are similar.

Run st7789_test.py to get a pattern on the display.

### sdram16

This is a 16-bit single port SDRAM controller.

Run test_sdram16.py to see the results on the leds: green means passed, red failed.

### mitecpu

This is a [tiny 8-bit cpu](https://github.com/jbush001/MiteCPU) with a python assembler.

The least significant bits of the accumulator are mapped to the leds, so programs can flash the leds.

Assemble programs with assemble.py and run them with mitecpu.py.

The CPU has a Harvard architecture with a maximum of 256 instructions, and 256 8-bit data items. Instructions are 11 bits.
Instructions execute in 2 clock cycles, or one clock cycle if the negative edge triggers data accesses. Instructions have a 3-bit opcode and an 8 bit operand, which is usually a memory address. There are just 7 opcodes. There are three 8-bit registers: ip (instructon pointer), acc (accumulator) and index (index register).

MiteCPU is used as a wishbone master in the wishbone examples below.

### opc

This is an nmigen version of the [opc6](https://revaldinho.github.io/opc/) 16-bit one page CPU.

Assemble programs with opc6asm.py and run them with opc6_sim.py of opc_test.py.

This is just the cpu, without any connected ram or uart, so it doesn't do much.

### ov7670

![ov7670](https://github.com/lawrie/lawrie.github.io/blob/master/images/mx_ov7670.jpg)

Reads video from an OV7670 camera, and displays it in low resolution (60x60) on an st7789 color LCD display.

Run camtest.py and press button 1 to configure the camera into RGB mode.

### ov7670_sdram

This is an SDRAM version of the OV7670 test with a 320x240 frame buffer.

Run camtest.py and press button 1 to configure the camera into RGB mode.

