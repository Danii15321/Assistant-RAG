"""Disposable, memory/CPU-bounded parser. stdout is a private pipe, not a log."""

import json
import resource
import sys
from dataclasses import asdict
from pathlib import Path

from app.services.extraction import ExtractionError, extract


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    try:
        units = extract(Path(sys.argv[1]), sys.argv[2])
        json.dump({"units": [asdict(u) for u in units]}, sys.stdout, ensure_ascii=False)
    except ExtractionError as error:
        json.dump({"error": error.code}, sys.stdout)
    except MemoryError:
        json.dump({"error": "extraction_limit"}, sys.stdout)


if __name__ == "__main__":
    main()
