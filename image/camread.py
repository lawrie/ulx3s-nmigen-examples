from nmigen import *

class CamRead(Elaboratable):
    WAIT_FRAME_START = 0
    ROW_CAPTURE      = 1

    def __init__(self):
        self.p_clock     = Signal()
        self.vsync       = Signal()
        self.href        = Signal()
        self.p_data      = Signal(8)
        self.pixel_data  = Signal(16)
        self.pixel_valid = Signal()
        self.frame_done  = Signal()
        self.row         = Signal(10)
        self.col         = Signal(9)

    def elaborate(self, platform):
        m = Module()

        # Create pclock domain
        pclock = ClockDomain("pclock")
        m.domains += pclock
        m.d.comb += pclock.clk.eq(self.p_clock)

        first_byte     = Signal(8)
        second_byte    = Signal(8)
        row_count      = Signal(10)
        col_count      = Signal(10)
        start_of_frame = Signal(1, reset=0)
        data           = Signal(8)
        fsm_state      = Signal(1, reset=0)
        pixel_half     = Signal()
        
        m.d.comb += [
            self.row.eq(row_count),
            self.col.eq(col_count)
        ]

        with m.Switch(fsm_state):
           with m.Case(self.WAIT_FRAME_START):
               m.d.pclock += [
                   self.frame_done.eq(0),
                   pixel_half.eq(0),
                   start_of_frame.eq(1),
                   row_count.eq(0),
                   col_count.eq(0)
               ]
               with m.If(~self.vsync):
                   m.d.pclock += fsm_state.eq(self.ROW_CAPTURE)
           with m.Case(self.ROW_CAPTURE):
               m.d.pclock += [
                   self.frame_done.eq(self.vsync),
                   self.pixel_valid.eq(self.href & pixel_half)
               ]
               with m.If(self.vsync):
                   m.d.pclock += fsm_state.eq(self.WAIT_FRAME_START)
               with m.If(self.href):
                   with m.If(start_of_frame):
                       with m.If(~pixel_half):
                           m.d.pclock += [
                               first_byte.eq(self.p_data),
                               data.eq(self.p_data)
                           ]
                       with m.Else():
                           m.d.pclock += [
                               start_of_frame.eq(0),
                               second_byte.eq(self.p_data)
                           ]
                   with m.If(pixel_half):
                       m.d.pclock += [
                           self.pixel_data[0:8].eq(self.p_data),
                           row_count.eq(row_count + 1)
                       ]
                   with m.Else():
                       m.d.pclock += [
                           self.pixel_data[8:].eq(self.p_data)
                       ]
                   m.d.pclock += pixel_half.eq(~pixel_half)
               with m.Else():
                   m.d.pclock += row_count.eq(0)
                   with m.If(row_count != 0):
                       m.d.pclock += col_count.eq(col_count + 1)

        return m
 
