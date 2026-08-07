"""Generate checked OpenAPI and Desktop contract artifacts."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .contract_openapi import build_openapi
from .contract_typescript import generate_runtime_rules, generate_types

REPO_ROOT = Path(__file__).parents[1]
CONTRACT_DIR = REPO_ROOT / "src" / "renderer" / "contracts"
OPENAPI_PATH = CONTRACT_DIR / "openapi.json"
TYPES_PATH = CONTRACT_DIR / "generated.d.ts"
RUNTIME_RULES_PATH = CONTRACT_DIR / "runtimeRules.ts"


def render_artifacts() -> dict[Path, bytes]:
    """Build every generated artifact entirely in memory."""
    document = build_openapi()
    openapi = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    canonical = json.loads(openapi)
    typescript = generate_types(canonical).encode()
    runtime_rules = generate_runtime_rules(canonical).encode()
    return {
        OPENAPI_PATH: openapi,
        TYPES_PATH: typescript,
        RUNTIME_RULES_PATH: runtime_rules,
    }


def write_atomic(path: Path, content: bytes) -> None:
    """Replace one generated artifact atomically in its destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    """Generate artifacts or report drift without modifying the repository."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files differ")
    options = parser.parse_args()
    artifacts = render_artifacts()
    stale = [
        path
        for path, content in artifacts.items()
        if not path.exists() or path.read_bytes() != content
    ]
    if options.check:
        if stale:
            for path in stale:
                print(f"generated contract is stale: {path.relative_to(REPO_ROOT)}")
            return 1
        return 0
    for path, content in artifacts.items():
        write_atomic(path, content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
