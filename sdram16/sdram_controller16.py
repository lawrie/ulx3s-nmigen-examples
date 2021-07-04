from nmigen import Signal, Instance, Elaboratable, C
from nmigen import Module, ClockSignal, ResetSignal
from nmigen.build import Pins, Attrs
from sdram16 import Sdram

class sdram_controller(Elaboratable):
    def __init__(self):
        # inputs
        self.address   = Signal(24) # word address
        self.req_read  = Signal()
        self.req_write = Signal()
        self.data_in   = Signal(16)
        self.init      = Signal()
        self.sync      = Signal()

        # outputs
        self.data_out  = Signal(16)
    
    def elaborate(self, platform):
        m = Module()

        # Get the SDRAM pins
        dir_dict = {
            "a":"-",
            "ba":"-",
            "cke":"-",
            "clk":"-",
            "clk_en":"-",
            "dq":"io",
            "dqm":"-",
            "cas":"-",
            "cs":"-",
            "ras":"-",
            "we":"-",
            }
        
        sdram = platform.request("sdram", dir=dir_dict)

        # Create the controller
        m.submodules.ctrl = ctrl = Sdram()

        m.d.comb += [
            # Set the chip output pins
            sdram.a.eq(ctrl.sd_addr),
            sdram.dqm.eq(ctrl.sd_dqm),
            sdram.ba.eq(ctrl.sd_ba),
            sdram.cs.eq(ctrl.sd_cs),
            sdram.we.eq(ctrl.sd_we),
            sdram.ras.eq(ctrl.sd_ras),
            sdram.cas.eq(ctrl.sd_cas),
            sdram.clk_en.eq(1),
            sdram.clk.eq(ClockSignal("sdram_clk")),
            sdram.dq.o.eq(ctrl.sd_data_out),
            sdram.dq.oe.eq(~ctrl.sd_data_dir), # Should not need the negation
            # Set the controller input pins
            ctrl.init.eq(self.init),
            ctrl.din.eq(self.data_in),
            ctrl.addr.eq(self.address),
            ctrl.we.eq(self.req_write),
            ctrl.oe.eq(self.req_read),
            ctrl.sync.eq(self.sync),
            ctrl.ds.eq(C(0b11,2)),
            ctrl.sd_data_in.eq(sdram.dq.i),
            # Set output pins
            self.data_out.eq(ctrl.dout)
        ]

        return m

