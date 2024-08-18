from abc import ABCMeta, abstractmethod

__all__ = ["CxxrtlPlatform"]


class CxxrtlPlatform(metaclass=ABCMeta):
    default_clk_frequency = property(abstractmethod(lambda _: None))
    uses_zig = False
