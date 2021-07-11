from nmigen import *
from nmigen.build import Platform

from conv3 import Conv3

class ImageConv(Elaboratable):
    def __init__(self, res_x = 320, res_y = 480):
        # Parameters
        self.res_x       = res_x
        self.res_y       = res_y
        
        # Inputs
        self.i_valid     = Signal()
        self.i_r         = Signal(5)
        self.i_g         = Signal(6)
        self.i_b         = Signal(5)
        self.sel         = Signal(4)
        self.x_flip      = Signal()
        self.y_flip      = Signal()
        self.mono        = Signal()

        # Outputs
        self.o_stall     = Signal()
        self.o_valid     = Signal()
        self.o_x         = Signal(10)
        self.o_y         = Signal(9)
        self.o_r         = Signal(5)
        self.o_g         = Signal(6)
        self.o_b         = Signal(5)

    def elaborate(self, platform):
        m = Module()

        p_s = Signal(7)
        def connect(c, ch):
            m.d.comb += [
                c.i_p.eq(ch),
                c.i_valid.eq(self.i_valid)
            ]

        def select(c_r, c_g, c_b):
            with m.If(self.mono):
                m.d.comb += [
                    p_s.eq(c_r + c_g + c_b),
                    self.o_r.eq(p_s[2:]),
                    self.o_g.eq(p_s[1:]),
                    self.o_b.eq(p_s[2:])
                ]
            with m.Else():
                m.d.comb += [
                    self.o_r.eq(c_r),
                    self.o_g.eq(c_g),
                    self.o_b.eq(c_b)
                ]

        # Identity
        k_ident = Array([0,0,0,
                         0,1,0,
                         0,0,0])
        sh_ident = 0
        
        # Edge detection
        k_edge = Array([-1,-1,-1,
                        -1, 8,-1,
                        -1,-1,-1])
        sh_edge = 0
        
        # Sharpen
        k_sharp = Array([ 0,-1, 0,
                          -1, 5,-1,
                          0,-1, 0])
        sh_sharp=0
        
        # Guassian blur
        k_blur = Array([1, 2 , 1,
                        2, 4,  2,
                        1, 2,  1])
        sh_blur = 4

        # Box blur
        k_box = Array([1, 1, 1,
                       1, 1, 1,
                       1, 1, 1])
        sh_box = 3

        # Emboss
        k_emboss = Array([-2, -1,  0,
                          -1,  1,  1,
                           0 , 1,  2])
        sh_emboss = 0

        # Adjust color balance (not used)
        k_bal = Array([0,0,0,
                       0,3,0,
                       0,0,0])
        sh_bal = 2
                   
        # Create the convolution modules
        m.submodules.blur_r = blur_r = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=5,sh=sh_blur)
        m.submodules.blur_g = blur_g = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=6,sh=sh_blur)
        m.submodules.blur_b = blur_b = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=5,sh=sh_blur)

        connect(blur_r, self.i_r)
        connect(blur_g, self.i_g)
        connect(blur_b, self.i_b)

        m.submodules.box_r = box_r = Conv3(k_box, w=self.res_x, h=self.res_y, dw=5,sh=sh_box,same=1)
        m.submodules.box_g = box_g = Conv3(k_box, w=self.res_x, h=self.res_y, dw=6,sh=sh_box,same=1)
        m.submodules.box_b = box_b = Conv3(k_box, w=self.res_x, h=self.res_y, dw=5,sh=sh_box,same=1)

        connect(box_r, self.i_r)
        connect(box_g, self.i_g)
        connect(box_b, self.i_b)

        m.submodules.edge_r = edge_r = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=5,sh=sh_edge)
        m.submodules.edge_g = edge_g = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=6,sh=sh_edge)
        m.submodules.edge_b = edge_b = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=5,sh=sh_edge)

        connect(edge_r, self.i_r)
        connect(edge_g, self.i_g)
        connect(edge_b, self.i_b)

        m.submodules.sharp_r = sharp_r = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=5,sh=sh_sharp,same=1)
        m.submodules.sharp_g = sharp_g = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=6,sh=sh_sharp,same=1)
        m.submodules.sharp_b = sharp_b = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=5,sh=sh_sharp,same=1)

        connect(sharp_r, self.i_r)
        connect(sharp_g, self.i_g)
        connect(sharp_b, self.i_b)

        m.submodules.emboss_r = emboss_r = Conv3(k_emboss, w=self.res_x, h=self.res_y, dw=5,sh=sh_emboss,same=1)
        m.submodules.emboss_g = emboss_g = Conv3(k_emboss, w=self.res_x, h=self.res_y, dw=6,sh=sh_emboss,same=1)
        m.submodules.emboss_b = emboss_b = Conv3(k_emboss, w=self.res_x, h=self.res_y, dw=5,sh=sh_emboss,same=1)

        connect(emboss_r, self.i_r)
        connect(emboss_g, self.i_g)
        connect(emboss_b, self.i_b)

        m.submodules.ident_r = ident_r = Conv3(k_ident, w=self.res_x, h=self.res_y, dw=5,sh=sh_ident)
        m.submodules.ident_g = ident_g = Conv3(k_ident, w=self.res_x, h=self.res_y, dw=6,sh=sh_ident)
        m.submodules.ident_b = ident_b = Conv3(k_ident, w=self.res_x, h=self.res_y, dw=5,sh=sh_ident)

        connect(ident_r, self.i_r)
        connect(ident_g, self.i_g)
        connect(ident_b, self.i_b)

        # Any channel can be used for these outputs
        m.d.comb += [
            self.o_stall.eq(ident_r.o_stall),
            self.o_valid.eq(ident_r.i_valid),
            self.o_x.eq(Mux(self.x_flip, self.res_x - 1 - ident_r.o_x, ident_r.o_x)),
            self.o_y.eq(Mux(self.y_flip, self.res_y - 1 - ident_r.o_y, ident_r.o_y))
        ]

        # Select the required convolution
        with m.Switch(self.sel):
            with m.Case(1):
                select(blur_r.o_p, blur_g.o_p, blur_b.o_p)
            with m.Case(2):
                select(sharp_r.o_p, sharp_g.o_p, sharp_b.o_p)
            with m.Case(3):
                select(emboss_r.o_p, emboss_g.o_p, emboss_b.o_p)
            with m.Case(4):
                select(edge_r.o_p, edge_g.o_p, edge_b.o_p)
            with m.Case(5):
                select(box_r.o_p, box_g.o_p, box_b.o_p)
            with m.Default():
                select(ident_r.o_p, ident_g.o_p, ident_b.o_p)

        return m

