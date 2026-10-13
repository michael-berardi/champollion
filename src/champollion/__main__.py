"""Module and directly executable vendored entry point."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from champollion.cli import main
else:
    from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
