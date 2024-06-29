import argparse
import json
import logging
import os
import shutil
from enum import Enum, nonmember
from functools import partial
from pathlib import Path

from amaranth._toolchain.yosys import find_yosys
from amaranth.back import rtlil

from .build import construct_top
from .cmdrunner import CommandRunner
from .logging import logtime
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
    rtl = "rtl"
    code = "code"
    none = "none"
    all = "all"

    def __str__(self):
        return self.value

    @nonmember
    class ArgparseAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            match (values, namespace.optimize):
                case (_Optimize.rtl, _Optimize.code) | (_Optimize.code, _Optimize.rtl):
                    # Choosing rtl or code when the other is chosen becomes all.
                    newval = _Optimize.all
                case _:
                    # Other cases are:
                    #   Choosing all or none always sets it, regardless of old value.
                    #   Choosing rtl or code when old value is all/none/same always sets it.
                    newval = values

            setattr(namespace, self.dest, newval)

    @property
    def opt_rtl(self) -> bool:
        return self in (self.rtl, self.all)

    @property
    def opt_code(self) -> bool:
        return self in (self.code, self.all)


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
        action=_Optimize.ArgparseAction,
        type=_Optimize,
        choices=_Optimize,
        default=_Optimize.all,
        help="build with optimizations — may be specified multiple times. default if unspecified: all.",
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
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="don't use cached compilations",
    )


def main(np: Project, args):
    yosys = find_yosys(lambda ver: ver >= (0, 10))

    platform = np.cxxrtl_target_by_name(args.target)
    design = construct_top(np, platform)

    subdir = type(platform).__name__
    os.makedirs(np.path.build(subdir), exist_ok=True)

    cr = CommandRunner(force=args.force)

    with logtime(logging.DEBUG, "elaboration"):
        il_path = np.path.build(subdir, f"{np.name}.il")
        rtlil_text = rtlil.convert(design, name=np.name, platform=platform)
        with open(il_path, "w") as f:
            f.write(rtlil_text)

        cxxrtl_cc_path = np.path.build(subdir, f"{np.name}.cc")
        yosys_script_path = _make_absolute(np.path.build(subdir, f"{np.name}.ys"))
        black_boxes = {}

        with open(yosys_script_path, "w") as f:
            for box_source in black_boxes.values():
                f.write(f"read_rtlil <<rtlil\n{box_source}\nrtlil\n")
            f.write(f"read_rtlil {_make_absolute(il_path)}\n")
            if args.optimize.opt_rtl:
                f.write("opt\n")
                f.write(f"write_rtlil {_make_absolute(il_path)}.opt\n")
            else:
                # Allow apples-to-apples comparison of generated RTLIL by
                # rewriting it with Yosys.
                f.write(f"write_rtlil {_make_absolute(il_path)}.noopt\n")
            f.write(f"write_cxxrtl -header {_make_absolute(cxxrtl_cc_path)}\n")

        def rtlil_to_cc():
            # "opt" without "proc" generates a bunch of warnings like:
            #
            #   Warning: Ignoring module ili9341spi.initter because it contains
            #   processes (run 'proc' command first).
            #
            # Those passes warn and don't run (instead of removing things we
            # care about), so just let them. We don't want to run "proc" --- it
            # dovetails poorly with CXXRTL and the result is slower than had we
            # done nothing at all.  Note the following option taken by
            # "write_cxxrtl":
            #
            #   -noproc
            #
            #       don't convert processes to netlists. in most designs,
            #       converting processes significantly improves evaluation
            #       performance at the cost of slight increase in compilation
            #       time.
            #
            # Presumably "proc" does it worse, for CXXRTL's purposes.
            yosys.run(["-q", yosys_script_path], ignore_warnings=True)

        cr.add_process(rtlil_to_cc,
            infs=[il_path, yosys_script_path],
            outf=cxxrtl_cc_path)
        cr.run()

    with logtime(logging.DEBUG, "compilation"):
        cc_odep_paths = {cxxrtl_cc_path: (np.path.build(subdir, f"{np.name}.o"), [])}
        depfs = list(np.path("cxxrtl").glob("**/*.h"))
        for path in np.path("cxxrtl").glob("**/*.cc"):
            # XXX: we make no effort to distinguish cxxrtl/a.cc and cxxrtl/dir/a.cc.
            cc_odep_paths[path] = (np.path.build(subdir, f"{path.stem}.o"), depfs)

        cxxflags = CXXFLAGS + [
            f"-DCLOCK_HZ={int(platform.default_clk_frequency)}",
            *(["-O3"] if args.optimize.opt_code else ["-O0"]),
            *(["-g"] if args.debug else []),
        ]
        if platform.uses_zig:
            cxxflags += [
                "-DCXXRTL_INCLUDE_CAPI_IMPL",
                "-DCXXRTL_INCLUDE_VCD_CAPI_IMPL",
            ]

        for cc_path, (o_path, dep_paths) in cc_odep_paths.items():
            cmd = [
                "c++",
                *cxxflags,
                f"-I{np.path.build(subdir)}",
                f"-I{yosys.data_dir() / "include" / "backends" / "cxxrtl" / "runtime"}",
                "-c",
                cc_path,
                "-o",
                o_path,
            ]
            if platform.uses_zig:
                cmd = ["zig"] + cmd
            cr.add_process(cmd, infs=[cc_path] + dep_paths, outf=o_path)

        # Not feasible to do these per-CXXRTL platform, as clangd won't find
        # them (and how could it know which to choose?). Worth noting it checks
        # inside a directory named "build" specifically.
        with open(np.path.build("compile_commands.json"), "w") as f:
            json.dump(
                [{
                    "directory": str(np.path()),
                    "file": file,
                    "arguments": arguments,
                } for file, arguments in cr.compile_commands.items()],
                f,
            )

        cr.run()

        exe_o_path = np.path.build(subdir, np.name)
        cc_o_paths = [o_path for (o_path, _) in cc_odep_paths.values()]
        if platform.uses_zig:
            # Note that we don't clear zig's cache on args.force.
            cmd = [
                "zig",
                "build",
                f"-Dclock_hz={int(platform.default_clk_frequency)}",
                f"-Dyosys_data_dir={yosys.data_dir()}",
            ] + [
                # Zig really wants relative paths.
                f"-Dcxxrtl_o_path=../{p.relative_to(np.path())}" for p in cc_o_paths
            ]
            if args.optimize.opt_code:
                cmd += ["-Doptimize=ReleaseFast"]
            outf = "cxxrtl/zig-out/bin/cxxrtl"
            cr.add_process(cmd,
                infs=cc_o_paths + list(np.path("cxxrtl").glob("**/*.zig")),
                outf=outf,
                chdir="cxxrtl")
            cr.run()
            shutil.copy(outf, exe_o_path)
        else:
            cmd = [
                "c++",
                # Hard to imagine these flags having any effect.
                *(["-O3"] if args.optimize.opt_code else ["-O0"]),
                *(["-g"] if args.debug else []),
                *cc_o_paths,
                "-o",
                exe_o_path,
            ]
            cr.add_process(cmd,
                infs=cc_o_paths,
                outf=exe_o_path)
            cr.run()

    if not args.compile:
        cmd = [exe_o_path]
        if args.vcd:
            cmd += ["--vcd", args.vcd]
        with logtime(logging.DEBUG, "run"):
            cr.run_cmd(cmd, step="run")


def _make_absolute(path):
    if path.is_absolute():
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            raise AssertionError("path must be relative to cwd for builtin-yosys to access it")
    return path
