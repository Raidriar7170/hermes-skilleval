"""Compatibility entrypoint for the shared canary."""

import runpy

if __name__ == "__main__":
    runpy.run_module("hermes_skilleval._maintenance.environment", run_name="__main__")
