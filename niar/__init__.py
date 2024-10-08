from argparse import ArgumentParser

from . import build, cxxrtl
from .cxxrtl_platform import CxxrtlPlatform
from .project import Project

__all__ = ["Project", "cli", "CxxrtlPlatform"]


def cli(np: Project):
    parser = ArgumentParser(prog=np.name)
    subparsers = parser.add_subparsers(required=True)

    build.add_arguments(
        np, subparsers.add_parser("build", help="build the design, and optionally program it"))
    if np.cxxrtl_targets:
        cxxrtl.add_arguments(
            np, subparsers.add_parser("cxxrtl", help="run the C++ simulator tests"))

    for command in np.commands:
        command.add_arguments(np, subparsers.add_parser(command.name, help=command.help))

    args = parser.parse_args()
    args.func(args)
