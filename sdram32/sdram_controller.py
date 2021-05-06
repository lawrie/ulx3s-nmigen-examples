from nmigen import Signal, Instance, Elaboratable
from nmigen import Module, ClockSignal, ResetSignal
from nmigen.build import Pins, Attrs

class sdram_controller(Elaboratable):

    def __init__(self):
        # inputs
        self.address = Signal(24)
        self.req_read = Signal()
        self.req_write = Signal()
        self.data_in = Signal(32)

        # outputs
        self.data_out = Signal(32)
        self.data_valid = Signal()
        self.write_complete = Signal()
    
    def elaborate(self, platform):
        m = Module()
        import os 
        dir_path = os.path.dirname(os.path.realpath(__file__))
        with open(dir_path + "/sdram_controller.v") as f:
            platform.add_file("sdram_controller.v", f.read())

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
        
        sdram = platform.request("sdram",dir=dir_dict)
        
        m.submodules += Instance("sdram_controller",
            i_CLOCK_50 = ClockSignal("compute"),
            i_CLOCK_100 = ClockSignal("sdram"),
            i_CLOCK_100_del_3ns = ClockSignal("sdram_180_deg"),
            i_rst = ResetSignal("sdram"),

            i_address = self.address,
            i_req_read = self.req_read,
            i_req_write = self.req_write,
            i_data_in = self.data_in,
            o_data_out = self.data_out,
            o_data_valid= self.data_valid,
            o_write_complete= self.write_complete,

            o_DRAM_ADDR = sdram.a,
            o_DRAM_BA = sdram.ba,
            o_DRAM_CKE = sdram.clk_en,
            o_DRAM_CLK = sdram.clk,

            io_DRAM_DQ = sdram.dq,

            o_DRAM_DQM = sdram.dqm,

            o_DRAM_CAS_N = sdram.cas,
            o_DRAM_CS_N = sdram.cs,
            o_DRAM_RAS_N = sdram.ras,
            o_DRAM_WE_N = sdram.we
            )

        return m