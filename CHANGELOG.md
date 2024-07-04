# Changelog

## 0.1.2 (unreleased)

New:

* build: `platform_kwargs` defined on the platform will be included in the `platform.prepare()` call.
* build: timing information from place-and-route shown as part of post-build log.

Changed:

* template: build CXXRTL with optimisations by default in CI
  (cf. [amaranth-lang/amaranth-yosys#12](https://github.com/amaranth-lang/amaranth-yosys/pull/12)).
* **XXX** cxxrtl: disabled dependency tracking for now, as it's broken in the important case of
  source files which depend on the CXXRTL module itself (e.g. those which instantiate it!).

Fixed:

* python: use PDM and declare dependencies correctly.
* build: use generated IL to calculate digest, not what's on disk.
* build: synthesis depends on the yosys script too, not just IL.

## 0.1.1

New:

* setup-action: GitHub Actions support for preparing.
* workflows: test in CI.
* template: getting started template.

Changed:

* python: move to src layout.
* project: define root where `pyproject.toml` found.
* cxxrtl: dependency tracking to avoid needless rebuilds.
* cxxrtl: fix distinction between optimising RTL and code.
* build: only resynthesise when RTLIL changes.
* build: `build` subdirectory per platform.

Fixed:

* cxxrtl: correctly disable when not used.

## 0.1

Initial release.
