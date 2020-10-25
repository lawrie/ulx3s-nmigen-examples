from nmigen import *

from ov7670_config import *
from sccb import *
from readhex import *

class CamConfig(Elaboratable):
    def __init__(self):
        self.start = Signal()
        self.sioc = Signal()
        self.siod = Signal()
        self.done = Signal()
        self.rom_addr = Signal(8)

    def elaborate(self, platform):
        m = Module()

        config_data = readhex("config.mem")
        config_rom = Memory(width=16, depth=len(config_data), init=config_data)
        m.submodules.r = r = config_rom.read_port()

        ov7670_config = OV7670Config()
        m.submodules.ov7670_config = ov7670_config

        sccb = SCCB()
        m.submodules.sccb = sccb

        m.d.comb += [
            self.sioc.eq(~sccb.sioc_oe),
            self.siod.eq(~sccb.siod_oe),
            self.done.eq(ov7670_config.done),
            r.addr.eq(ov7670_config.rom_addr),
            ov7670_config.sccb_ready.eq(sccb.ready),
            ov7670_config.start.eq(self.start),
            ov7670_config.rom_data.eq(r.data),
            sccb.address.eq(ov7670_config.sccb_addr),
            sccb.data.eq(ov7670_config.sccb_data),
            sccb.start.eq(ov7670_config.sccb_start),
            self.rom_addr.eq(ov7670_config.rom_addr)
        ]

        return m
