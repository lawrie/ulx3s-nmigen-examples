#
# This file is part of LUNA.
#
# Copyright (c) 2020 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause


import os
import subprocess

from abc import ABCMeta, abstractmethod

from nmigen import *
from nmigen.build import *
import nmigen_boards.ulx3s as _ulx3s

class ULX3SDomainGenerator(Elaboratable):
    """ Clock domain generator that creates the domain clocks for the ULX3S. """

    def elaborate(self, platform):
        m = Module()

        # Grab our default input clock.
        input_clock = platform.request(platform.default_clk, dir="i")

        # Create our domains; but don't do anything else for them, for now.
        m.domains.sync   = ClockDomain()
        m.domains.usb    = ClockDomain()
        m.domains.usb_io = ClockDomain()
        m.domains.fast   = ClockDomain()

        feedback = Signal()
        locked_12_48   = Signal()

        # ... create our 48 MHz IO and 12 MHz USB clock...
        clk48  = Signal()
        clk12  = Signal()


        m.submodules.pll_12_48 = Instance("EHXPLLL",
            i_RST=1,
            i_STDBY=0,
            i_CLKI=input_clock.i,
            i_PHASESEL0=0,
            i_PHASESEL1=0,
            i_PHASEDIR=1,
            i_PHASESTEP=1,
            i_PHASELOADREG=1,
            i_PLLWAKESYNC=0,
            i_ENCLKOP=0,
            i_CLKFB=feedback,

            o_LOCK=locked_12_48,
            o_CLKOP=feedback,
            o_CLKOS=clk48,
            o_CLKOS2=clk12,

            p_PLLRST_ENA="DISABLED",
            p_INTFB_WAKE="DISABLED",
            p_STDBY_ENABLE="DISABLED",
            p_DPHASE_SOURCE="DISABLED",
            p_OUTDIVIDER_MUXA="DIVA",
            p_OUTDIVIDER_MUXB="DIVB",
            p_OUTDIVIDER_MUXC="DIVC",
            p_OUTDIVIDER_MUXD="DIVD",
            p_CLKI_DIV=5,
            p_CLKOP_ENABLE="ENABLED",

            p_CLKOS2_ENABLE="ENABLED",
            p_CLKOP_DIV=48,
            p_CLKOP_CPHASE=9,
            p_CLKOP_FPHASE=0,
            p_CLKOS_ENABLE="ENABLED",
            p_CLKOS_DIV=10,
            p_CLKOS_CPHASE=0,
            p_CLKOS_FPHASE=0,
            p_CLKOS2_DIV=40,
            p_CLKOS2_CPHASE=0,
            p_CLKOS2_FPHASE=0,
            p_FEEDBK_PATH="CLKOP",
            p_CLKFB_DIV=2,

            a_FREQUENCY_PIN_CLKI="25",
            a_FREQUENCY_PIN_CLKOP="48",
            a_FREQUENCY_PIN_CLKOS="48",
            a_FREQUENCY_PIN_CLKOS2="12",
            a_ICP_CURRENT="12",
            a_LPF_RESISTOR="8",
            a_MFG_ENABLE_FILTEROPAMP="1",
            a_MFG_GMCREF_SEL="2",

        )

        m.domains.compute = ClockDomain()
        m.domains.sdram = ClockDomain()
        m.domains.sdram_180_deg = ClockDomain()

        locked_70_140   = Signal()

        # ... create fast clocks for SDRAM controller
        clk140  = Signal()
        clk140_3ns  = Signal()
        clk70  = Signal()

        m.submodules.pll_70_140 = Instance("EHXPLLL",
            i_RST=0,
            i_STDBY=0,
            i_CLKI=input_clock.i,
            o_CLKOP=clk140,
            o_CLKOS=clk140_3ns,

            o_CLKOS2=clk70,
            i_CLKFB=clk140,

            i_PHASESEL0=0,
            i_PHASESEL1=0,

            i_PHASEDIR=1,
            i_PHASESTEP=1,
            i_PHASELOADREG=1,
            i_PLLWAKESYNC=0,
            i_ENCLKOP=0,

            o_LOCK=locked_70_140,


            p_PLLRST_ENA="DISABLED",
            p_INTFB_WAKE="DISABLED",
            p_STDBY_ENABLE="DISABLED",
            p_DPHASE_SOURCE="DISABLED",
            p_OUTDIVIDER_MUXA="DIVA",

            p_OUTDIVIDER_MUXB="DIVB",
            p_OUTDIVIDER_MUXC="DIVC",
            p_OUTDIVIDER_MUXD="DIVD",
            p_CLKI_DIV=1,
            p_CLKOP_ENABLE="ENABLED",

            p_CLKOP_DIV=6,
            p_CLKOP_CPHASE=2,
            p_CLKOP_FPHASE=0,
            p_CLKOS_ENABLE="ENABLED",
            p_CLKOS_DIV=6,

            p_CLKOS_CPHASE=5,
            p_CLKOS_FPHASE=0,
            p_CLKOS2_ENABLE="ENABLED",
            p_CLKOS2_DIV=12,
            p_CLKOS2_CPHASE=2,

            p_CLKOS2_FPHASE=0,
            p_FEEDBK_PATH="CLKOP",
            p_CLKFB_DIV=4,

            a_FREQUENCY_PIN_CLKI="25",
            a_FREQUENCY_PIN_CLKOP="100",
            a_FREQUENCY_PIN_CLKOS="100",
            a_FREQUENCY_PIN_CLKOS2="50",
            a_ICP_CURRENT="12",
            a_LPF_RESISTOR="8",
            a_MFG_ENABLE_FILTEROPAMP="1",
            a_MFG_GMCREF_SEL="2",

        )

        # We'll use our 48MHz clock for everything _except_ the usb domain...
        m.d.comb += [
            ClockSignal("usb")              .eq(clk12),
            ClockSignal("sync")             .eq(clk48),
            ClockSignal("usb_io")           .eq(clk48),
            ClockSignal("fast")             .eq(clk48),

            ResetSignal("usb")              .eq(~locked_12_48),
            ResetSignal("sync")             .eq(~locked_12_48),
            ResetSignal("usb_io")           .eq(~locked_12_48),
            ResetSignal("fast")             .eq(~locked_12_48),

            ClockSignal("compute")          .eq(clk70),
            ClockSignal("sdram")            .eq(clk140),
            ClockSignal("sdram_180_deg")    .eq(clk140_3ns),

            ResetSignal("compute")          .eq(~locked_70_140),
            ResetSignal("sdram")            .eq(~locked_70_140),
            ResetSignal("sdram_180_deg")    .eq(~locked_70_140)
        ]

        return m