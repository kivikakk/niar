import hashlib
import inspect
import shlex
import subprocess

from .logging import logger

__all__ = ["CompilationUnit", "CommandRunner", "CommandFailedError"]


class CompilationUnit:
    def __init__(self, cmd, *, infs, outf, chdir):
        if inspect.isfunction(cmd):
            self.cmd = cmd
        else:
            self.cmd = [str(el) for el in cmd]
        self.infs  = infs
        self.outf  = str(outf) if outf else None
        self.chdir = chdir

        self.forced = False
        self.digest_path = f"{outf}.dig"

    @property
    def up_to_date(self):
        if self.outf is None:
            return False
        try:
            with open(self.digest_path, "r") as f:
                return f.read() == self.digest_ins_with_cmd()
        except FileNotFoundError:
            return False

    def mark_up_to_date(self):
        if self.outf is None:
            return
        with open(self.digest_path, "w") as f:
            f.write(self.digest_ins_with_cmd())

    def digest_ins_with_cmd(self):
        m = hashlib.sha256()

        def digest_int(i):
            m.update(f"{i:08x}".encode())

        def digest_bytes(b):
            digest_int(len(b))
            m.update(b)

        def digest_str(s):
            digest_bytes(s.encode())

        infs = self.process_infs()

        digest_int(len(infs))
        for in_path in sorted(infs.keys()):
            digest_str(in_path)
            digest_bytes(infs[in_path])

        if not inspect.isfunction(self.cmd):
            digest_int(len(self.cmd))
            for el in self.cmd:
                digest_str(el)

        return m.hexdigest()

    def process_infs(self):
        r = {}
        for inf in self.infs:
            if isinstance(inf, dict):
                for k, v in inf.items():
                    if isinstance(v, str):
                        v = v.encode()
                    r[str(k)] = v
            else:
                with open(inf, "rb") as f:
                    r[str(inf)] = f.read()
        return r


class CommandRunner:
    cus: list[CompilationUnit]

    def __init__(self, *, force=False):
        self.cus = []
        self.force = force

    @property
    def compile_commands(self):
        return {cu.outf: cu.cmd for cu in self.cus}

    def add_process(self, cmd, *, infs, outf, chdir=None):
        self.cus.append(
            CompilationUnit(cmd, infs=infs, outf=outf, chdir=chdir))

    def run(self, step="compile"):
        self.run_cus(self.cus, step)
        self.cus = []

    def run_cmd(self, cmd, *, step="compile", chdir=None):
        cu = CompilationUnit(cmd, infs=[], outf=None, chdir=chdir)
        self.run_cus([cu], step)

    def run_cus(self, cus, step):
        runnables = []
        for cu in cus:
            if cu.up_to_date:
                if self.force:
                    cu.forced = True
                    runnables.append([cu, None])
                else:
                    self.report(cu, skip=True)
            else:
                runnables.append([cu, None])

        for cu_proc in runnables:
            cu = cu_proc[0]
            self.report(cu)
            if inspect.isfunction(cu.cmd):
                cu.cmd()
            else:
                cu_proc[1] = subprocess.Popen(cu.cmd, cwd=cu.chdir)

        failed = []
        for cu, proc in runnables:
            if proc is not None and proc.wait() != 0:
                failed.append(cu)

        if failed:
            logger.error("the following process(es) failed:")
            for cu in failed:
                logger.error(f"  {formatted(cu)}")
            raise CommandFailedError(f"failed {step} step")

        for cu, _ in runnables:
            cu.mark_up_to_date()

    def report(self, cu, *, skip=False):
        if cu.forced:
            assert(not skip)
            action = "[force]"
        elif skip:
            action = "[skip] "
        else:
            action = "[run]  "
        logger.info(f"{action} {formatted(cu)}")


class CommandFailedError(RuntimeError):
    pass


def formatted(cu):
    if inspect.isfunction(cu.cmd):
        return cu.cmd.__name__

    cmd = shlex.join(cu.cmd)
    if cu.chdir:
        return f"(in {cu.chdir}/) {cmd}"
    return cmd
