import pytest
from argparse import ArgumentParser

from amaranth import Elaboratable, Module
from amaranth_boards.icebreaker import ICEBreakerPlatform

from niar import Project, build, logging


class FixtureTop(Elaboratable):
    def elaborate(self, platform):
        return Module()


class FixtureProject(Project):
    name = "fixture"
    top = FixtureTop
    targets = [ICEBreakerPlatform]


def test_build_works():
    parser = ArgumentParser()
    build.add_arguments(FixtureProject(), parser)
    args, _argv = parser.parse_known_args()
    args.func(args)
