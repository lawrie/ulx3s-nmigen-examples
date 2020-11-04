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

