# Changelog

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
