"""Unit tests for OpenAPI 3.1 specification (IS-02, IS-09)."""

from __future__ import annotations

import os
import yaml
import pytest


def test_openapi_yaml_exists_and_valid():
    """Verify openapi.yaml is present and valid YAML."""
    assert os.path.isfile("openapi.yaml"), "openapi.yaml does not exist"
    with open("openapi.yaml", "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    assert isinstance(spec, dict)
    assert spec.get("openapi") == "3.1.0", f"Expected OpenAPI 3.1.0, got {spec.get('openapi')}"
    assert "info" in spec
    assert "paths" in spec


def test_openapi_documents_v1_endpoints():
    """Verify all /api/v1 routes and root routes are documented in openapi.yaml."""
    with open("openapi.yaml", "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    paths = spec.get("paths", {})
    required_paths = [
        "/health",
        "/ready",
        "/jobs",
        "/jobs/{job_id}",
        "/jobs/{job_id}/storyboard",
        "/jobs/{job_id}/artifacts",
        "/api/v1/health",
        "/api/v1/ready",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/storyboard",
        "/api/v1/jobs/{job_id}/artifacts",
    ]
    for rp in required_paths:
        assert rp in paths, f"Path {rp} missing from openapi.yaml"


def test_job_create_schema_aspect_ratios():
    """Verify JobCreateRequest documents 16:9, 9:16, and 1:1 aspect ratios."""
    with open("openapi.yaml", "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    schemas = spec.get("components", {}).get("schemas", {})
    req_schema = schemas.get("JobCreateRequest", {})
    ar_prop = req_schema.get("properties", {}).get("aspect_ratio", {})
    pattern = ar_prop.get("pattern", "")
    assert "1:1" in pattern, f"Expected 1:1 in pattern, got {pattern}"
    assert "16:9" in pattern
    assert "9:16" in pattern


def test_job_create_response_has_progress_and_links():
    """Verify JobCreateResponse includes progress and result_links (IS-03)."""
    with open("openapi.yaml", "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    schemas = spec.get("components", {}).get("schemas", {})
    resp_schema = schemas.get("JobCreateResponse", {})
    props = resp_schema.get("properties", {})
    assert "job_id" in props
    assert "status" in props
    assert "progress" in props
    assert "result_links" in props
