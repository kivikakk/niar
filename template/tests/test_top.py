import unittest

from amaranth.hdl import Fragment
from amaranth.sim import Simulator

from newproject.rtl import Blinker


class test:
    simulation = True
    default_clk_frequency = 8.0


class TestBlinker(unittest.TestCase):
    platform = test()

    def test_blinks(self):
        dut = Blinker()

        async def testbench(ctx):
            for ledr in [0, 1, 1, 0, 0, 1, 1, 0]:
                for _ in range(2):
                    assert ctx.get(dut.ledr) == ledr
                    assert ctx.get(dut.ledg)
                    await ctx.tick()

        sim = Simulator(Fragment.get(dut, self.platform))
        sim.add_clock(1 / 8)
        sim.add_testbench(testbench)
        sim.run()
