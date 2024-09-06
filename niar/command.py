from typing import Callable

__all__ = ["Command"]

class Command:
    add_arguments: Callable
    name: str
    help: str

    def __init__(self, *, add_arguments, help):
        self.add_arguments = add_arguments
        self.name = add_arguments.__name__
        self.help = help
