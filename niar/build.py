import inspect
import logging
import re
from functools import partial
from typing import Optional

from amaranth.build import Platform

from .logging import logger, logtime
from .project import Project

__all__ = ["add_arguments"]


def add_arguments(np: Project, parser):
    parser.set_defaults(func=partial(main, np))
    match sorted(t.__name__ for t in np.targets):
        case []:
            raise RuntimeError("no buildable targets defined")
        case [first, *rest]:
            parser.add_argument(
                "-b",
                "--board",
                choices=[first, *rest],
                help="which board to build for",
                required=bool(rest),
                **({"default": first} if not rest else {}),
            )
    parser.add_argument(
        "-p",
        "--program",
        action="store_true",
        help="program the design onto the board after building",
    )
    parser.add_argument(
        "-v",
        "--verilog",
        action="store_true",
        help="output debug Verilog",
    )


def main(np: Project, args):
    logger.info("building %s for %s", np.name, args.board)

    platform = np.target_by_name(args.board)
    design = construct_top(np, platform)

    with logtime(logging.DEBUG, "elaboration"):
        plan = platform.prepare(
            design,
            np.name,
            debug_verilog=args.verilog,
            yosys_opts="-g",
        )
    fn = f"{np.name}.il"
    size = len(plan.files[fn])
    logger.debug(f"{fn!r}: {size:,} bytes")

    with logtime(logging.DEBUG, "synthesis/pnr"):
        products = plan.execute_local("build")

    if args.program:
        with logtime(logging.DEBUG, "programming"):
            platform.toolchain_program(products, np.name)

    heading = re.compile(r"^\d+\.\d+\. Printing statistics\.$", flags=re.MULTILINE)
    next_heading = re.compile(r"^\d+\.\d+\. ", flags=re.MULTILINE)
    log_file_between(logging.INFO, f"build/{np.name}.rpt", heading, next_heading)

    logger.info("Device utilisation:")
    heading = re.compile(r"^Info: Device utilisation:$", flags=re.MULTILINE)
    next_heading = re.compile(r"^Info: Placed ", flags=re.MULTILINE)
    log_file_between(
        logging.INFO, f"build/{np.name}.tim", heading, next_heading, prefix="Info: "
    )


def construct_top(np: Project, platform: Platform, **kwargs):
    sig = inspect.signature(np.top)
    if "platform" in sig.parameters:
        kwargs["platform"] = platform
    return np.top(**kwargs)


def log_file_between(
    level: int,
    path: str,
    start: re.Pattern,
    end: re.Pattern,
    *,
    prefix: Optional[str] = None,
):
    with open(path, "r") as f:
        for line in f:
            if start.match(line):
                break
        else:
            return

        for line in f:
            if end.match(line):
                return
            line = line.rstrip()
            if prefix is not None:
                line = line.removeprefix(prefix)
            logger.log(level, line)
