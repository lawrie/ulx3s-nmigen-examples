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
            "dq":"-",
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
            # Set the controller input pins
            ctrl.init.eq(self.init),
            ctrl.din.eq(self.data_in),
            ctrl.addr.eq(self.address),
            ctrl.we.eq(self.req_write),
            ctrl.oe.eq(self.req_read),
            ctrl.sync.eq(self.sync),
            ctrl.ds.eq(C(0b11,2)),
            # Set output pins
            self.data_out.eq(ctrl.dout)
        ]

        # Set dq to input or output depending on sd_data_dir
        for i in range(16):
            dq_io = Instance("BB",
                io_B=sdram.dq[i],
                i_T=~ctrl.sd_data_dir,
                i_I=ctrl.sd_data_out[i],
                o_O=ctrl.sd_data_in[i]
            )

            m.submodules += dq_io
        return m

