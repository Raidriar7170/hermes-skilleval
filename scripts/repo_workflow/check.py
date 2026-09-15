"""Compatibility entrypoint for the installed maintenance implementation."""

import runpy

if __name__ == "__main__":
    runpy.run_module("hermes_skilleval._maintenance.check", run_name="__main__")
