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
        self.i_x         = Signal(10)
        self.i_y         = Signal(9)
        self.i_r         = Signal(5)
        self.i_g         = Signal(6)
        self.i_b         = Signal(5)
        self.sel         = Signal(4)

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

        m.submodules.blur_r = blur_r = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=5,sh=sh_blur)
        m.submodules.blur_g = blur_g = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=6,sh=sh_blur)
        m.submodules.blur_b = blur_b = Conv3(k_blur, w=self.res_x, h=self.res_y, dw=5,sh=sh_blur)

        m.submodules.edge_r = edge_r = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=5,sh=sh_edge)
        m.submodules.edge_g = edge_g = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=6,sh=sh_edge)
        m.submodules.edge_b = edge_b = Conv3(k_edge, w=self.res_x, h=self.res_y, dw=5,sh=sh_edge)

        m.submodules.sharp_r = sharp_r = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=5,sh=sh_sharp)
        m.submodules.sharp_g = sharp_g = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=6,sh=sh_sharp)
        m.submodules.sharp_b = sharp_b = Conv3(k_sharp, w=self.res_x, h=self.res_y, dw=5,sh=sh_sharp)

        m.submodules.ident_r = ident_r = Conv3(k_ident, w=self.res_x, h=self.res_y, dw=5,sh=sh_ident)
        m.submodules.ident_g = ident_g = Conv3(k_ident, w=self.res_x, h=self.res_y, dw=6,sh=sh_ident)
        m.submodules.ident_b = ident_b = Conv3(k_ident, w=self.res_x, h=self.res_y, dw=5,sh=sh_ident)

        m.d.comb += [
            ident_r.i_p.eq(self.i_r),
            ident_g.i_p.eq(self.i_g),
            ident_b.i_p.eq(self.i_b),
            ident_r.i_valid.eq(self.i_valid),
            ident_g.i_valid.eq(self.i_valid),
            ident_b.i_valid.eq(self.i_valid),
            sharp_r.i_p.eq(self.i_r),
            sharp_g.i_p.eq(self.i_g),
            sharp_b.i_p.eq(self.i_b),
            sharp_r.i_valid.eq(self.i_valid),
            sharp_g.i_valid.eq(self.i_valid),
            sharp_b.i_valid.eq(self.i_valid),
            blur_r.i_p.eq(self.i_r),
            blur_g.i_p.eq(self.i_g),
            blur_b.i_p.eq(self.i_b),
            blur_r.i_valid.eq(self.i_valid),
            blur_g.i_valid.eq(self.i_valid),
            blur_b.i_valid.eq(self.i_valid),
            edge_r.i_p.eq(self.i_r),
            edge_g.i_p.eq(self.i_g),
            edge_b.i_p.eq(self.i_b),
            edge_r.i_valid.eq(self.i_valid),
            edge_g.i_valid.eq(self.i_valid),
            edge_b.i_valid.eq(self.i_valid),
            self.o_stall.eq(ident_r.o_stall),
            self.o_valid.eq(ident_r.i_valid),
            self.o_x.eq(ident_r.o_x),
            self.o_y.eq(ident_r.o_y)
        ]

        with m.Switch(self.sel):
            with m.Case(1):
                m.d.comb += [
                    self.o_r.eq(blur_r.o_p),
                    self.o_g.eq(blur_g.o_p),
                    self.o_b.eq(blur_b.o_p)
                ]
            with m.Case(2):
                m.d.comb += [
                    self.o_r.eq(sharp_r.o_p),
                    self.o_g.eq(sharp_g.o_p),
                    self.o_b.eq(sharp_b.o_p)
                ]
            with m.Case(3):
                m.d.comb += [
                    self.o_r.eq(edge_r.o_p),
                    self.o_g.eq(edge_g.o_p),
                    self.o_b.eq(edge_b.o_p)
                ]
            with m.Default():
                m.d.comb += [
                    self.o_r.eq(ident_r.o_p),
                    self.o_g.eq(ident_g.o_p),
                    self.o_b.eq(ident_b.o_p)
                ]

        return m

