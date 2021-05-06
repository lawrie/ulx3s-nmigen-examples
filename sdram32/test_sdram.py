"""
The state machine below writes ``0x12345678``
to the SDRAM, reads it back, and displays a byte at a time
to the LEDs. Once the four bytes finish displaying, the state
machine restarts by writing 0x12345678 and continues the 
write-read-display loop.

The SDRAM controller present a memory with 4-byte lines.
0x0 and 0x4 are seperated by 4-bytes.
The SDRAM controller presents a total of 8,388,608 lines
or addresses.
Thus the controller presents a total of 32MiBs in the memory.
"""

from nmigen import *
from debouncer import Debouncer
from ulx3s85f import ULX3SDomainGenerator
from sdram_controller import sdram_controller
from nmigen import Const

def led_display_value(m, led, value):
    value = Const(value, 8)
    statements = [light.eq(val) for light,val in zip(led, value)]
    return statements

def led_display_signal(m, led, signal):
    return [light.eq(sig) for light,sig in zip(led,signal)]

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        # get clock domains
        m.submodules.domains = ULX3SDomainGenerator()

        led = [platform.request("led",count) for count in range(8)]

        # help me debounce the button
        button = platform.request("button_fire", 1)
        debouncer = Debouncer()
        m.submodules.debouncer = debouncer
        m.d.comb += debouncer.btn.eq(button)

        m.submodules.mem = mem = sdram_controller()

        data_buffer = Signal(32)

        address = 0x1205
        data = 0x12345678

        with m.FSM(domain="compute"):
            with m.State("WRITE"):
                m.d.comb += mem.address.eq(address)
                m.d.comb += mem.data_in.eq(data)
                m.d.comb += mem.req_write.eq(1)
                m.next = "WRITE_COMPLETE"
            
            with m.State("WRITE_COMPLETE"):
                m.d.comb += mem.address.eq(address)
                m.d.comb += mem.data_in.eq(data)
                with m.If(mem.write_complete):
                    m.next = "READ"
            
            with m.State("READ"):
                m.d.comb += mem.address.eq(address)
                m.d.comb += mem.req_read.eq(1)
                m.next = "READ_COMPLETE"
            
            with m.State("READ_COMPLETE"):
                m.d.comb += mem.address.eq(address)
                with m.If(mem.data_valid):
                    m.d.compute += data_buffer.eq(mem.data_out)
                    m.next = "BYTE_0_TO_LED"
            
            with m.State(f"BYTE_0_TO_LED"):
                m.d.comb += led_display_signal(m, led[0:8], data_buffer[0:8])
                with m.If(debouncer.btn_up):
                    m.next = "BYTE_1_TO_LED"

            with m.State(f"BYTE_1_TO_LED"):
                m.d.comb += led_display_signal(m, led[0:8], data_buffer[8:16])
                with m.If(debouncer.btn_up):
                    m.next = "BYTE_2_TO_LED"

            with m.State(f"BYTE_2_TO_LED"):
                m.d.comb += led_display_signal(m, led[0:8], data_buffer[16:24])
                with m.If(debouncer.btn_up):
                    m.next = "BYTE_3_TO_LED"

            with m.State(f"BYTE_3_TO_LED"):
                m.d.comb += led_display_signal(m, led[0:8], data_buffer[24:32])
                with m.If(debouncer.btn_up):
                    m.next = "WRITE"

        return m


if __name__ == "__main__":
    from nmigen_boards.ulx3s import ULX3S_85F_Platform
    top = Top()
    platform = ULX3S_85F_Platform()
    platform.build(top, do_program=True)
