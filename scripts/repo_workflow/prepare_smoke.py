"""Compatibility entrypoint for the installed maintenance implementation."""

import runpy

if __name__ == "__main__":
    runpy.run_module("hermes_skilleval._maintenance.prepare_smoke", run_name="__main__")
