"""Write ``seon.network.json``.

Usage: ``python -m processrecall.ontology.seon [--source DIR] [--out FILE]``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from processrecall.ontology.seon.network import digest

if TYPE_CHECKING:
    from collections.abc import Sequence

_ONTOLOGY = Path(__file__).resolve().parents[1]
# The pinned inputs are a build input, not shipped: they sit at the root of the
# processrecall-ontology source tree, beside src/ (seon -> ontology -> processrecall -> src).
_SOURCE = _ONTOLOGY.parents[2] / "seon-1.0.5"
# The digest is the pinned runtime artifact, shipped inside the package.
_OUT = _ONTOLOGY / "data" / "seon.network.json"


def main(argv: Sequence[str] | None = None) -> None:
    """Digest *--source* and write the JSON to *--out*; *argv* defaults to ``sys.argv``."""
    parser = argparse.ArgumentParser(
        prog="python -m processrecall.ontology.seon", description=__doc__
    )
    parser.add_argument(
        "--source", type=Path, default=_SOURCE, help="pinned SEON inputs (default: %(default)s)"
    )
    parser.add_argument("--out", type=Path, default=_OUT, help="output file (default: %(default)s)")
    arguments = parser.parse_args(argv)
    out: Path = arguments.out
    document = digest(arguments.source)
    # LF on every platform, so the checked-in artifact is the same bytes everywhere.
    out.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
