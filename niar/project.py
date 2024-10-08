import os
import sys
from pathlib import Path
from typing import Optional

from amaranth import Elaboratable
from amaranth.build import Platform

from .command import Command
from .cxxrtl_platform import CxxrtlPlatform

__all__ = ["Project"]


class Prop:
    def __init__(
        self,
        name: str,
        *,
        description: str,
        required: bool,
        isinstance: Optional[type] = None,
        isinstance_list: Optional[type] = None,
        issubclass: Optional[type] = None,
        issubclass_list: Optional[type] = None,
    ):
        self.name = name
        self.description = description
        self.required = required
        self.isinstance = isinstance
        self.isinstance_list = isinstance_list
        self.issubclass = issubclass
        self.issubclass_list = issubclass_list

    def validate(self, project):
        assert len(list(filter(None, [
            self.isinstance,
            self.isinstance_list,
            self.issubclass,
            self.issubclass_list,
        ]))) == 1, "must define exactly one of the is... parameters"

        if self.required:
            assert hasattr(project, self.name), (
                f"{project.__module__}.{project.__class__.__qualname__} is missing "
                f"property {self.name!r} ({self.description})"
            )
        elif not hasattr(project, self.name):
            return

        attr = getattr(project, self.name)
        if self.isinstance:
            assert isinstance(attr, self.isinstance), (
                f"{project.__module__}.{project.__class__.__qualname__} property "
                f"{self.name!r} ({self.description}) should an instance of "
                f"{self.isinstance!r}, but is {attr!r}"
            )
        if self.isinstance_list:
            assert isinstance(attr, list)
            for elem in attr:
                assert isinstance(elem, self.isinstance_list), (
                    f"{project.__module__}.{project.__class__.__qualname__} property "
                    f"{self.name!r} ({self.description}) should a list of instances of "
                    f"{self.isinstanc_list!r}, but has element {elem!r}"
                )
        if self.issubclass:
            assert issubclass(attr, self.issubclass), (
                f"{project.__module__}.{project.__class__.__qualname__} property "
                f"{self.name!r} ({self.description}) should be a subclass of "
                f"{self.issubclass!r}, but is {attr!r}"
            )
        if self.issubclass_list:
            assert isinstance(attr, list)
            for elem in attr:
                assert issubclass(elem, self.issubclass_list), (
                    f"{project.__module__}.{project.__class__.__qualname__} property "
                    f"{self.name!r} ({self.description}) should be a list of subclasses of "
                    f"{self.issubclass_list!r}, but has element {elem!r}"
                )


class Project:
    name: str
    top: type[Elaboratable]
    targets: list[type[Platform]]
    cxxrtl_targets: list[type[CxxrtlPlatform]] = []
    externals: list[str] = []
    commands: list[Command] = []

    origin: Path

    PROPS = [
        Prop(
            "name",
            description="a keyword-like identifier for the project",
            required=True,
            isinstance=str,
        ),
        Prop(
            "top",
            description="a reference to the default top-level elaboratable to be built",
            required=True,
            issubclass=Elaboratable,
        ),
        Prop(
            "targets",
            description="a list of platform classes the elaboratable is targetted for",
            required=True,
            issubclass_list=Platform,
        ),
        Prop(
            "cxxrtl_targets",
            description="a list of niar.CxxrtlPlatform classes the elaboratable is targetted for",
            required=False,
            issubclass_list=CxxrtlPlatform,
        ),
        Prop(
            "externals",
            description="a list of Verilog and RTLIL project paths to include in the build",
            required=False,
            isinstance_list=str,
        ),
        Prop(
            "commands",
            description="a list of Command objects which extend the CLI",
            required=False,
            isinstance_list=Command,
        ),
    ]

    def __init_subclass__(cls):
        if origin := os.getenv("NIAR_WORKING_DIRECTORY"):
            cls.origin = Path(origin).absolute()
        else:
            # We expect to be called from project-root/module/__init.py__ or similar;
            # cls.origin is project-root. Keep going up until we find pyproject.toml.
            origin = Path(sys._getframe(1).f_code.co_filename).absolute().parent
            while True:
                if (origin / "pyproject.toml").is_file():
                    cls.origin = origin
                    break
                if not any(origin.parents):
                    assert False, "could not find pyproject.toml"
                origin = origin.parent

        os.chdir(cls.origin)

        extras = cls.__dict__.keys() - {"__module__", "__doc__", "origin"}
        for prop in cls.PROPS:
            prop.validate(cls)
            extras -= {prop.name}
        assert extras == set(), f"unknown project properties: {extras}"

    def target_by_name(self, name: str) -> Platform:
        for t in self.targets:
            if t.__name__ == name:
                return t()
        raise KeyError(f"unknown target {name!r}")

    def cxxrtl_target_by_name(self, name: str) -> CxxrtlPlatform:
        for t in self.cxxrtl_targets:
            if t.__name__ == name:
                return t()
        raise KeyError(f"unknown CXXRTL target {name!r}")

    def main(self):
        from . import cli

        cli(self)

    @property
    def path(self):
        return ProjectPath(self)

    @classmethod
    def command(cls, *, help):
        def inner(add_arguments):
            cls.commands.append(Command(
                add_arguments=add_arguments,
                help=help,
            ))
        return inner


class ProjectPath:
    def __init__(self, np: Project):
        self.np = np

    def __call__(self, *components):
        return self.np.origin.joinpath(*components)

    def build(self, *components):
        return self("build", *components)
