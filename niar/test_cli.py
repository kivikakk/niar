import unittest
from argparse import ArgumentParser

from amaranth import Elaboratable, Module
from amaranth_boards.icebreaker import ICEBreakerPlatform

from . import Project, build, logger

calling_test = False


class FixtureTop(Elaboratable):
    def elaborate(self, platform):
        return Module()


class FixtureProject(Project):
    name = "fixture"
    top = FixtureTop
    targets = [ICEBreakerPlatform]


class TestCLI(unittest.TestCase):
    def setUp(self):
        logger.disable()
        self.addCleanup(logger.enable)

    def test_build_works(self):
        parser = ArgumentParser()
        build.add_arguments(FixtureProject(), parser)
        args, _argv = parser.parse_known_args()
        args.func(args)
