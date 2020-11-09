from nmigen import *

MOV=0x0;AND=0x1;OR=0x2;XOR=0x3;ADD=0x4;ADC=0x5;STO=0x6;LD=0x7;ROR=0x8;JSR=0x9;SUB=0xA;SBC=0xB;INC=0xC;LSR=0xD;DEC=0xE;ASR=0xF
HLT=0x10;BSWP=0x11;PPSR=0x12;GPSR=0x13;RTI=0x14;NOT=0x15;OUT=0x16;IN=0x17;PUSH=0x18;POP=0x19;CMP=0x1A;CMPC=0x1B
FET0=0x0;FET1=0x1;EAD=0x2;RDM=0x3;EXEC=0x4;WRM=0x5;INT=0x6
EI=3;S=2;C=1;Z=0;P0=15;P1=14;P2=13;IRLEN=12;IRLD=16;IRSTO=17;IRNPRED=18;IRWBK=19;INT_VECTOR0=0x0002;INT_VECTOR1=0x0004

class OPC6(Elaboratable):
    def __init__(self): # define cpu ports
        self.reset_b = Signal()
        self.din = Signal(16)
        self.int_b = Signal(2)
        self.clken = Signal()
        self.vpa = Signal()
        self.vda = Signal()
        self.vio = Signal()
        self.dout = Signal(16)
        self.address = Signal(16)
        self.rnw = Signal()
        self.halted = Signal()

    def ports(self): # For simulation
        return [self.reset_b, self.din, self.int_b, self.clken, self.halted,
                self.vpa, self.vda, self.vio, self.dout, self.address, self.rnw]

    def elaborate(self, platform):
        OR_q       = Signal(16)
        PC_q       = Signal(16)
        PCI_q      = Signal(16)
        result     = Signal(16)
        IR_q       = Signal(20)
        FSM_q      = Signal(3)
        swiid      = Signal(4)
        PSRI_q     = Signal(4)
        PSR_q      = Signal(8)
        zero       = Signal()
        carry      = Signal()
        sign       = Signal()
        enable_int = Signal()
        reset_s0_b = Signal()
        reset_s1_b = Signal()
        pred_q     = Signal()
        op         = Signal(5)
        op_d       = Signal(5)
        pred_d     = Signal()
        pred_din   = Signal()
        RF_w_p2    = Signal(16)
        RF_dout    = Signal(16)
        operand    = Signal(16)
        repl1      = Signal(16)
        repl2      = Signal(16)

        RF_q = Memory(width=16, depth=16, name="reg")       
        m = Module()

        m.d.comb += [
            op.eq(Cat([IR_q[8:12],IR_q[IRNPRED]])),
            op_d.eq(Cat([self.din[8:12], (self.din[13:] == 1)])),
            pred_d.eq((self.din[13:] == 1) | (self.din[P2] ^ Mux(self.din[P1], Mux(self.din[P0],sign,zero), Mux(self.din[P0],carry,1)))),
            pred_din.eq((self.din[13:] == 1) | (self.din[P2] ^ Mux(self.din[P1], Mux(self.din[P0], PSR_q[S], PSR_q[Z]), Mux(self.din[P0], PSR_q[C], 1)))),
            repl1.eq(Repl((IR_q[4:8] != 0),16)),
            repl2.eq(Repl((IR_q[:4] != 0),16)),
            RF_w_p2.eq(Mux(IR_q[4:8] == 0xf, PC_q, repl1 & RF_q[IR_q[4:8]])),
            RF_dout.eq(Mux(IR_q[:4] == 0xf, PC_q, repl2 & RF_q[IR_q[:4]])),
            operand.eq(Mux(IR_q[IRLEN] | IR_q[IRLD] | (op == INC) | (op == DEC) | IR_q[IRWBK], OR_q, RF_w_p2)),
            self.rnw.eq((FSM_q != WRM)), # Set CPU outputs
            self.dout.eq(RF_w_p2),
            self.address.eq(Mux((FSM_q == WRM) | (FSM_q == RDM), Mux(op == POP, RF_dout, OR_q), PC_q)),
            self.vpa.eq((FSM_q == FET0) | (FSM_q == FET1) | (FSM_q == EXEC)),
            self.vda.eq(((FSM_q == RDM) | (FSM_q == WRM)) & (op != IN) & (op != OUT)),
            self.vio.eq(((FSM_q == RDM) | (FSM_q == WRM)) & ((op == IN) | (op == OUT))),
            Cat([zero, carry, sign, enable_int, swiid]).eq(Mux((op == PPSR), operand[:8], Mux((IR_q[:4] != 0xf), Cat([(result == 0), carry, result[15], PSR_q[3:8]]), PSR_q)))
        ]

        with m.If((op == HLT) & (FSM_q == EXEC)): # Makes simulator detecting halted easier
            m.d.sync += self.halted.eq(1)

        with m.Switch(op): # ALU
            with m.Case(AND, OR):
                m.d.comb += Cat([result,carry]).eq(Mux(Cat([IR_q[8],PSR_q[C]]), (RF_dout & operand), (RF_dout | operand)))
            with m.Case(ADD, ADC, INC):
                m.d.comb += Cat([result,carry]).eq(RF_dout + operand + (IR_q[8] & PSR_q[C]))
            with m.Case(SUB, SBC, CMP, CMPC, DEC):
                m.d.comb += Cat([result,carry]).eq(RF_dout + (operand ^ 0xffff) + Mux(IR_q[8], PSR_q[C],1))
            with m.Case(XOR, GPSR):
                m.d.comb += Cat([result,carry]).eq(Mux(IR_q[IRNPRED], Cat([PSR_q,Const(0,8),PSR_q[C]]), (RF_dout ^ operand)))
            with m.Case(NOT, BSWP):
                m.d.comb += Cat([carry,result]).eq(Mux(IR_q[10],Cat([PSR_q[C], ~operand]),Cat([PSR_q[C], operand[8:], operand[:8]])))
            with m.Case(ROR, ASR, LSR):
                m.d.comb += Cat([carry,result]).eq(Cat([operand, Mux((IR_q[10] == 0), PSR_q[C], Mux(IR_q[8], operand[15], 0))]))
            with m.Default():
                m.d.comb += Cat([result,carry]).eq(Cat([operand, PSR_q[C]]))

        with m.If(self.clken):
            m.d.sync += [
                reset_s0_b.eq(self.reset_b), # sync reset
                reset_s1_b.eq(reset_s0_b),
                pred_q.eq(Mux(FSM_q == FET0, pred_din, pred_d))
            ]
            with m.If(reset_s1_b == 0): # reset
                m.d.sync += [
                    PC_q.eq(0),
                    PCI_q.eq(0),
                    PSR_q.eq(0),
                    FSM_q.eq(0)
                ]
            with m.Else(): 
                with m.Switch(FSM_q): # FSM
                    with m.Case(FET0):
                        m.d.sync += FSM_q.eq(Mux(self.din[IRLEN], FET1, Mux((pred_din == 0),  FET0, Mux(((self.din[8:12] == LD) | (self.din[8:12] == STO) | (op_d == PUSH) | (op_d == POP)), EAD, EXEC))))
                    with m.Case(FET1):
                        m.d.sync += FSM_q.eq(Mux((pred_q == 0), FET0, Mux(((IR_q[:4] != 0) | IR_q[IRLD] | IR_q[IRSTO]), EAD, EXEC)))
                    with m.Case(EAD):
                        m.d.sync += FSM_q.eq(Mux(IR_q[IRLD], RDM, Mux(IR_q[IRSTO], WRM, EXEC)))
                    with m.Case(EXEC):
                        m.d.sync += FSM_q.eq(Mux((((self.int_b != 3) & PSR_q[EI]) | ((op == PPSR) & (swiid != 0))), INT, Mux(((IR_q[:4] == 0xf) | (op == JSR)), FET0, Mux(self.din[IRLEN], FET1, Mux(((self.din[8:12] == LD) | (self.din[8:12] == STO) | (op_d == POP) | (op_d == PUSH)), EAD, Mux(pred_d, EXEC, FET0))))))
                    with m.Case(WRM):
                        m.d.sync += FSM_q.eq(Mux(((self.int_b != 3) & PSR_q[EI]), INT, FET0))
                    with m.Default():
                        m.d.sync += FSM_q.eq(Mux((FSM_q == RDM), EXEC, FET0))
                m.d.sync += OR_q.eq(Mux(((FSM_q == FET0) | (FSM_q == EXEC)), Repl((op_d == PUSH), 16) ^ Cat([Mux(((op_d == DEC) | (op_d == INC)), self.din[4:8], Cat([op_d == POP, Const(0,3)])), Const(0,12)]), Mux(FSM_q == EAD, RF_w_p2 + OR_q, self.din))) # Registers operand
                with m.If(FSM_q == INT): # Set PC, PSR etc
                    m.d.sync += [
                        PC_q.eq(Mux((self.int_b[1] == 0), INT_VECTOR1, INT_VECTOR0)),
                        PCI_q.eq(PC_q),
                        PSRI_q.eq(PSR_q[:4]),
                        PSR_q[EI].eq(0)
                    ]
                with m.Elif((FSM_q == FET0) | (FSM_q == FET1)):
                    m.d.sync += PC_q.eq(PC_q + 1)
                with m.Elif(FSM_q == EXEC):
                    m.d.sync += [
                        PC_q.eq(Mux((op == RTI), PCI_q, Mux(((IR_q[:4] == 0xf) | (op == JSR)), result, Mux((((self.int_b != 3) & PSR_q[EI]) | ((op == PPSR) & (swiid != 0))), PC_q, PC_q + 1)))),
                        PSR_q.eq(Mux((op == RTI), Cat([PSRI_q,Const(0,4)]), Cat([zero, carry, sign, enable_int, swiid])))
                    ]
                with m.If(((FSM_q == EXEC) & (op != CMP) & (op != CMPC)) | (((FSM_q == WRM) | (FSM_q == RDM)) & IR_q[IRWBK])): # Write to register
                    m.d.sync += RF_q[IR_q[:4]].eq(Mux((op == JSR), PC_q, result)) 
                with m.If((FSM_q == FET0) | (FSM_q == EXEC)): # IR_q registers the instruction with some extra flags
                    m.d.sync += IR_q.eq(Cat([self.din, ((self.din[8:12] == LD) | (op_d == POP)), ((self.din[8:12] == STO) | (op_d == PUSH)), ((self.din[13:] == 1)), ((op_d == PUSH) | (op_d == POP))])) 
                with m.Elif(((FSM_q == EAD) & (IR_q[IRLD] | IR_q[IRSTO])) | (FSM_q == RDM)):
                    m.d.sync += IR_q[:8].eq(Cat([IR_q[4:8],IR_q[:4]])) #  Swap source/dest reg in EA for reads and writes for writeback of 'source' in push/pop .. swap back again in RDMEM
            
        return m

