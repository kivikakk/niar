import niar

from . import rtl
from .targets import cxxrtl, icebreaker, ulx3s

__all__ = ["NewProject"]


class NewProject(niar.Project):
    name = "newproject"
    top = rtl.Top
    targets = [icebreaker, ulx3s]
    cxxrtl_targets = [cxxrtl]
