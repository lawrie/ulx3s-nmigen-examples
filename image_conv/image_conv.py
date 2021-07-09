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

        def connect(c, ch):
            m.d.comb += [
                c.i_p.eq(ch),
                c.i_valid.eq(self.i_valid)
            ]

        def select(c_r, c_g, c_b):
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

        # Create the convolution modules
        m.submodules.blur_r = blur_r = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=5,sh=sh_blur)
        m.submodules.blur_g = blur_g = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=6,sh=sh_blur)
        m.submodules.blur_b = blur_b = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=5,sh=sh_blur)

        connect(blur_r, self.i_r)
        connect(blur_g, self.i_g)
        connect(blur_b, self.i_b)

        m.submodules.edge_r = edge_r = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=5,sh=sh_edge)
        m.submodules.edge_g = edge_g = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=6,sh=sh_edge)
        m.submodules.edge_b = edge_b = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=5,sh=sh_edge)

        connect(edge_r, self.i_r)
        connect(edge_g, self.i_g)
        connect(edge_b, self.i_b)

        m.submodules.sharp_r = sharp_r = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=5,sh=sh_sharp)
        m.submodules.sharp_g = sharp_g = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=6,sh=sh_sharp)
        m.submodules.sharp_b = sharp_b = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=5,sh=sh_sharp)

        connect(sharp_r, self.i_r)
        connect(sharp_g, self.i_g)
        connect(sharp_b, self.i_b)

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
                select(edge_r.o_p, edge_g.o_p, edge_b.o_p)
            with m.Default():
                select(ident_r.o_p, ident_g.o_p, ident_b.o_p)

        return m

