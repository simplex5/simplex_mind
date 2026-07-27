"""`python -m simplex_cli` entry point; also works via direct path invocation
(`py src/simplex_cli/__main__.py`)."""
import sys
from pathlib import Path

try:
    from .cli import main
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplex_cli.cli import main

sys.exit(main())
