import argparse

from nmigen import *
from nmigen_boards.ulx3s import *

def readhex():
    f = open("progmem.hex","r")
    l = []
    while True:
        s = f.readline()
        if s:
            l.append(int(s,16))
        else:
            break
    f.close()
    return l

class MiteCPU(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(8)]
        clk25 = platform.request("clk25")
        prog = readhex()
        print(" ".join(hex(n) for n in prog))
        code = Memory(width=11, depth=256, init=prog)
        data = Memory(width=8, depth=256)
        ip = Signal(8, reset=0xff)
        ip_nxt = Signal(8)
        instr = Signal(11, reset=0)
        acc = Signal(8, reset=0)
        index = Signal(8, reset=0)
        op = Signal(8, reset=0)
        addr = Signal(8)
        leds = Cat(led[i].o for i in range(8))
        delay = Signal(22)

        m = Module()

        # Create sync domain
        m.domains.sync = ClockDomain()
        m.d.comb += ClockSignal().eq(clk25.i)

        # Create negedge domain
        neg = ClockDomain("neg", clk_edge="neg")
        m.domains += neg
        m.d.comb += neg.clk.eq(clk25.i)
       
        # Set address 
        m.d.comb += addr.eq(instr[0:8] + index)

        # Set ip_nxt
        with m.If((instr[8:] == 4) & acc[7]):
            m.d.comb += ip_nxt.eq(instr[0:8])
        with m.Else():
            m.d.comb += ip_nxt.eq(ip + 1)

        # Delay counter
        m.d.sync += delay.eq(delay + 1)

        with m.If(delay == 0):
            # Advance instruction pointer
            m.d.sync += ip.eq(ip_nxt)
            
            # Fetch next instruction
            m.d.sync += instr.eq(code[ip_nxt])

            # Decode and execute current instruction
            m.d.sync += index.eq(0) # index defaults to zero
            with m.Switch(instr[8:]):
                with m.Case("000"):
                    m.d.sync += acc.eq(acc + op)
                with m.Case("001"):
                    m.d.sync += acc.eq(acc - op)
                with m.Case("110"):
                    m.d.sync += acc.eq(acc & op)
                with m.Case("010"):
                    m.d.sync += acc.eq(instr[0:8])
                with m.Case("101"):
                    m.d.sync += index.eq(op)
                with m.Case("011"):
                    m.d.sync += data[addr].eq(acc)
                    # data[0] is leds
                    with m.If(instr[0:8] == 0):
                        m.d.sync += leds.eq(acc)
           
            # Fetch the op on the negative edge of clock
            m.d.neg += op.eq(data[addr])
 
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
    platform.build(MiteCPU(), do_program=True)
