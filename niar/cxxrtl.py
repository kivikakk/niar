import json
import logging
import subprocess
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any

from amaranth import Elaboratable
from amaranth._toolchain.yosys import YosysBinary, find_yosys
from amaranth.back import rtlil

from .build import construct_top
from .cxxrtl_platform import CxxrtlPlatform
from .logger import logger, logtime
from .project import Project

__all__ = ["add_arguments"]

CXXFLAGS = [
    "-std=c++17",
    "-g",
    "-pedantic",
    "-Wall",
    "-Wextra",
    "-Wno-zero-length-array",
    "-Wno-unused-parameter",
]


class _Optimize(Enum):
    none = "none"
    rtl = "rtl"

    def __str__(self):
        return self.value

    @property
    def opt_rtl(self) -> bool:
        return self in (self.rtl,)


def add_arguments(np: Project, parser):
    parser.set_defaults(func=partial(main, np))
    match sorted(t.__name__ for t in np.cxxrtl_targets or []):
        case []:
            raise RuntimeError("no cxxrtl targets defined")
        case [first, *rest]:
            parser.add_argument(
                "-t",
                "--target",
                choices=[first, *rest],
                help="which CXXRTL target to build",
                required=bool(rest),
                **({"default": first} if not rest else {}),
            )
    parser.add_argument(
        "-c",
        "--compile",
        action="store_true",
        help="compile only; don't run",
    )
    parser.add_argument(
        "-O",
        "--optimize",
        type=_Optimize,
        choices=_Optimize,
        help="build with optimizations (default: rtl)",
        default=_Optimize.rtl,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="generate source-level debug information",
    )
    parser.add_argument(
        "-v",
        "--vcd",
        action="store",
        type=str,
        help="output a VCD file",
    )


def main(np: Project, args):
    yosys = find_yosys(lambda ver: ver >= (0, 10))

    platform = np.cxxrtl_target_by_name(args.target)
    design = construct_top(np, platform)

    cxxrtl_cc_path = np.path.build(f"{np.name}.cc")
    with logtime(logging.DEBUG, "elaboration"):
        _cxxrtl_convert_with_header(
            yosys,
            cxxrtl_cc_path,
            design,
            np.name,
            platform,
            black_boxes={},
        )

    cc_o_paths = {
        cxxrtl_cc_path: np.path.build(f"{np.name}.o"),
    }
    for path in np.path("cxxrtl").glob("*.cc"):
        cc_o_paths[path] = np.path.build(f"{path.stem}.o")

    cxxflags = CXXFLAGS + [
        f"-DCLOCK_HZ={int(platform.default_clk_frequency)}",
        *(["-O3"] if args.optimize.opt_rtl else ["-O0"]),
        *(["-g"] if args.debug else []),
    ]

    procs = []
    compile_commands = {}
    for cc_path, o_path in cc_o_paths.items():
        cmd = [
            "c++",
            *cxxflags,
            "-I" + str(np.path("build")),
            "-I"
            + str(yosys.data_dir() / "include" / "backends" / "cxxrtl" / "runtime"),
            "-c",
            str(cc_path),
            "-o",
            str(o_path),
        ]
        compile_commands[o_path] = cmd
        logger.debug(" ".join(str(e) for e in cmd))
        procs.append((cc_path, subprocess.Popen(cmd)))

    with open(np.path.build("compile_commands.json"), "w") as f:
        json.dump(
            [
                {
                    "directory": str(np.path()),
                    "file": str(file),
                    "arguments": arguments,
                }
                for file, arguments in compile_commands.items()
            ],
            f,
        )

    failed = []
    for cc_path, p in procs:
        if p.wait() != 0:
            failed.append(cc_path)

    if failed:
        logger.error("Failed to build paths:")
        for p in failed:
            logger.error(f"- {p}")
        raise RuntimeError("failed compile step")

    exe_o_path = np.path.build("cxxrtl")
    cmd = [
        "c++",
        *cxxflags,
        *cc_o_paths.values(),
        "-o",
        exe_o_path,
    ]
    logger.debug(" ".join(str(e) for e in cmd))
    subprocess.run(cmd, check=True)

    if not args.compile:
        cmd = [exe_o_path]
        if args.vcd:
            cmd += ["--vcd", args.vcd]
        logger.debug(" ".join(str(e) for e in cmd))
        subprocess.run(cmd, check=True)


def _cxxrtl_convert_with_header(
    yosys: YosysBinary,
    cc_out: Path,
    design: Elaboratable,
    name: str,
    platform: CxxrtlPlatform,
    *,
    black_boxes: dict[Any, str],
):
    if cc_out.is_absolute():
        try:
            cc_out = cc_out.relative_to(Path.cwd())
        except ValueError:
            raise AssertionError(
                "cc_out must be relative to cwd for builtin-yosys to write to it"
            )
    rtlil_text = rtlil.convert(design, name=name, platform=platform)
    script = []
    for box_source in black_boxes.values():
        script.append(f"read_rtlil <<rtlil\n{box_source}\nrtlil")
    script.append(f"read_rtlil <<rtlil\n{rtlil_text}\nrtlil")
    script.append(f"write_cxxrtl -header {cc_out}")
    yosys.run(["-q", "-"], "\n".join(script))
