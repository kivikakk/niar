import sys
from pathlib import Path
from typing import Optional

from amaranth import Elaboratable
from amaranth.build import Platform

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
        issubclass: Optional[type] = None,
        issubclass_list: Optional[type] = None,
    ):
        self.name = name
        self.description = description
        self.required = required
        self.isinstance = isinstance
        self.issubclass = issubclass
        self.issubclass_list = issubclass_list

    def validate(self, project):
        assert not (
            self.issubclass and self.issubclass_list
        ), "may only define one of issubclass and issubclass_list"

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
                    f"{self.issubclass!r}, but has element {attr!r}"
                )


class Project:
    name: str
    top: type[Elaboratable]
    targets: list[type[Platform]]
    cxxrtl_targets: Optional[list[type[CxxrtlPlatform]]]

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
    ]

    def __init_subclass__(cls):
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
        for t in self.cxxrtl_targets or []:
            if t.__name__ == name:
                return t()
        raise KeyError(f"unknown CXXRTL target {name!r}")

    def main(self):
        from . import cli

        cli(self)

    @property
    def path(self):
        return ProjectPath(self)


class ProjectPath:
    def __init__(self, np: Project):
        self.np = np

    def __call__(self, *components):
        return self.np.origin.joinpath(*components)

    def build(self, *components):
        return self("build", *components)
