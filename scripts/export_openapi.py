"""Export OpenAPI 3.1 schema to openapi.json and openapi.yaml."""

from __future__ import annotations

import json
import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.abspath("src"))

import yaml
from sceneforge.api.app import create_app


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ["SKIP_STARTUP_CHECKS"] = "true"
    app = create_app()
    schema = app.openapi()
    schema["openapi"] = "3.1.0"

    out_json = os.path.join(root_dir, "openapi.json")
    out_yaml = os.path.join(root_dir, "openapi.yaml")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    with open(out_yaml, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, sort_keys=False, allow_unicode=True)

    print(f"Exported openapi.json and openapi.yaml ({len(schema.get('paths', {}))} paths):")
    for path in sorted(schema.get("paths", {}).keys()):
        print(f"  {path}")


if __name__ == "__main__":
    main()
