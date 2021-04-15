#!/usr/bin/env python3

import argparse

from migen import *

from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock import S7PLL, S7IDELAYCTRL

from litex_boards.platforms import antmicro_lpddr4_test_board
from litedram.phy import lpddr4
from liteeth.phy import LiteEthS7PHYRGMII

from rowhammer_tester.targets import common
from litehyperbus.core.hyperbus import HyperRAM

# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys2x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys8x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()

        # # #

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        pll.create_clkout(self.cd_sys2x,  2 * sys_clk_freq)
        pll.create_clkout(self.cd_sys8x,  8 * sys_clk_freq)
        pll.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# SoC ----------------------------------------------------------------------------------------------

class SoC(common.RowHammerSoC):
    mem_map = {
        "hyperram": 0x26000000,
    }
    mem_map.update(common.RowHammerSoC.mem_map)

    def __init__(self, iodelay_clk_freq=200e6, **kwargs):
        self.iodelay_clk_freq = iodelay_clk_freq
        super().__init__(**kwargs)
        self.submodules.hyperram = HyperRAM(self.platform.request("hyperram"))
        self.register_mem("hyperram", self.mem_map["hyperram"], self.hyperram.bus, 8*1024*1024)

    def get_platform(self):
        return antmicro_lpddr4_test_board.Platform()

    def get_crg(self):
        return CRG(self.platform, self.sys_clk_freq, iodelay_clk_freq=self.iodelay_clk_freq)

    def get_ddrphy(self):
        return lpddr4.K7LPDDR4PHY(self.platform.request("lpddr4"),
            iodelay_clk_freq = self.iodelay_clk_freq,
            sys_clk_freq     = self.sys_clk_freq)

    def get_sdram_ratio(self):
        return "1:8"

    def get_sdram_module(self, speedgrade=None):
        return self.sdram_module_cls(self.sys_clk_freq, "1:8", speedgrade=speedgrade)

    def add_host_bridge(self):
        self.submodules.ethphy = LiteEthS7PHYRGMII(
            clock_pads = self.platform.request("eth_clocks"),
            pads       = self.platform.request("eth"))
        self.add_etherbone(
            phy          = self.ethphy,
            ip_address   = self.ip_address,
            mac_address  = self.mac_address,
            udp_port     = self.udp_port,
            buffer_depth = 256)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on LPDDR4 Test Board")

    common.parser_args(parser, sys_clk_freq='50e6', module='MT53E256M16D1')
    vivado_build_args(parser)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(**soc_kwargs)

    target_name = 'lpddr4_test_board'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)

if __name__ == "__main__":
    main()

