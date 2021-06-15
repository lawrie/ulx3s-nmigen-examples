# Copyright (C) 2020 Robert Baruch <robert.c.baruch@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# To synthesize:
# python3 cpu_ulx3s.py

import os
import subprocess
import itertools
from typing import List

from core import Core

from nmigen import Signal, Module, Elaboratable, ClockDomain
from nmigen.build import Resource, ResourceError, Pins, Attrs, Connector, Clock
from nmigen_boards.ulx3s import *

# Set FAKEMEM to True if you want to use a "software" ROM.
# This also hooks up the LEDs to the low byte of the address bus.
FAKEMEM = True

# This is the software ROM:
mem = {
    0xFFFE: 0x12,
    0xFFFF: 0x34,
    0x1234: 0x7E,  # JMP 0x1234
    0x1235: 0x12,
    0x1236: 0x34,
}

# Set SLOWCLK to True if you want a 1Hz clock.
SLOWCLK = True


class N6800(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        cpu = Core()
        m.submodules += cpu
        m.domains.ph1 = ph1 = ClockDomain("ph1")
        m.domains.ph2 = ph2 = ClockDomain("ph2", clk_edge="neg")

        # Hook up clocks and reset to pins

        if SLOWCLK:
            clk_freq = platform.default_clk_frequency
            timer = Signal(range(0, int(clk_freq // 2)),
                           reset=int(clk_freq // 2) - 1)
            tick = Signal()
            sync = ClockDomain()

            with m.If(timer == 0):
                m.d.sync += timer.eq(timer.reset)
                m.d.sync += tick.eq(~tick)
            with m.Else():
                m.d.sync += timer.eq(timer - 1)
            m.d.comb += [
                ph1.rst.eq(sync.rst),
                ph2.rst.eq(sync.rst),
                ph1.clk.eq(tick),
                ph2.clk.eq(~tick),
            ]

        # Hook up address lines to pins
        addr = []
        for i in range(16):
            pin = platform.request("addr", i)
            m.d.comb += pin.o.eq(cpu.Addr[i])
            addr.append(pin)

        data = []
        if not FAKEMEM:
            # Hook up data in/out + direction to pins
            for i in range(8):
                pin = platform.request("data", i)
                m.d.comb += pin.o.eq(cpu.Dout[i])
                m.d.ph2 += cpu.Din[i].eq(pin.i)
                data.append(pin)

        if FAKEMEM:
            with m.Switch(cpu.Addr):
                for a, d in mem.items():
                    with m.Case(a):
                        m.d.comb += cpu.Din.eq(d)
                with m.Default():
                    m.d.comb += cpu.Din.eq(0x00)
            for i in range(8):
                pin = platform.request("led", i)
                m.d.comb += pin.o.eq(cpu.Addr[i])

        rw = platform.request("rw")
        m.d.comb += rw.o.eq(cpu.RW)

        nIRQ = platform.request("n_irq")
        nNMI = platform.request("n_nmi")
        m.d.ph2 += cpu.IRQ.eq(~nIRQ)
        m.d.ph2 += cpu.NMI.eq(~nNMI)

        ba = platform.request("ba")
        m.d.comb += ba.o.eq(cpu.BA)
        m.d.comb += rw.oe.eq(~cpu.BA)
        for i in range(len(addr)):
            m.d.comb += addr[i].oe.eq(~cpu.BA)
        for i in range(len(data)):
            m.d.comb += data[i].oe.eq(~cpu.BA & ~cpu.RW)

        return m


def Bus(*args, pins, invert=False, conn=None, attrs=None, default_name, dir):
    """Adds a bus resource. Add to resources using *Bus(...)."""
    assert isinstance(pins, (str, list, dict))

    if isinstance(pins, str):
        pins = pins.split()
    if isinstance(pins, list):
        pins = dict(enumerate(pins))

    resources = []
    for number, pin in pins.items():
        ios = [Pins(pin, dir=dir, invert=invert, conn=conn)]
        if attrs is not None:
            ios.append(attrs)
        resources.append(
            Resource.family(*args, number, default_name=default_name, ios=ios)
        )
    return resources

class Ulx3sPlatform(ULX3S_85F_Platform):  
    resources: List[Resource] = [

        Resource("clk25", 0, Pins("G2", dir="i"), Clock(25e6), Attrs(IO_TYPE="LVCMOS33")),

        Resource("rst", 0, Pins("D6", dir="i"), Attrs(IO_TYPE="LVCMOS33")),

        *Bus(
            default_name="addr",
            pins="B11 C11 A10 A11 A9 B10 B9 C10 A7 A8 C8 B8 C6 C7 A6 B6",
            dir="oe",
            attrs=Attrs(IO_TYPE="LVCMOS33"),
        ),
        *Bus(
            default_name="data",
            pins="A4 A5 A2 B1 C4 B4 F4 E3",
            dir="io",
            attrs=Attrs(IO_TYPE="LVCMOS33"),
        ),
        *Bus(
            default_name="led",
            pins="H3 E1 E2 D1 D2 C1 C2 B2",
            dir="o",
            attrs=Attrs(IO_TYPE="LVCMOS33"),
        ),
        Resource("ba", 0, Pins("G3", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("rw", 0, Pins("F3", dir="oe"),
                 Attrs(IO_TYPE="LVCMOS33")),
        Resource("n_irq", 0, Pins("H4", dir="i"),
                 Attrs(IO_TYPE="LVCMOS33")),
        Resource("n_nmi", 0, Pins("G5", dir="i"),
                 Attrs(IO_TYPE="LVCMOS33")),
    ]

    default_rst = "rst"

if __name__ == "__main__":
    Ulx3sPlatform().build(N6800(), do_program=False, synth_opts="-abc2")
