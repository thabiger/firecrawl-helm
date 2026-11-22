#!/usr/bin/env python3
"""Apply known builder and Rust dependency fixes to pinned Firecrawl source.

Idempotent. Refuses unknown upstream Dockerfiles rather than silently patching
an incompatible future release.
"""
import sys
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================
root = Path(__file__).resolve().parent.parent
vendor = root / "vendor/firecrawl"
if not (vendor / "apps/api/Dockerfile").is_file():
    sys.exit("Firecrawl source missing: run scripts/fetch-firecrawl.sh first")

patches = {
    "apps/api/Dockerfile": [
        ("FROM node:22-slim", "FROM docker.io/library/node:22-slim"),
        ("FROM golang:1.24", "FROM docker.io/library/golang:1.24"),
    ],
    "apps/playwright-service-ts/Dockerfile": [
        ("FROM node:22-slim", "FROM docker.io/library/node:22-slim"),
        ("ARG PORT\n", "ARG PORT=3000\n"),
        ("EXPOSE ${PORT}", "EXPOSE 3000"),
    ],
    "apps/nuq-postgres/Dockerfile": [
        ("FROM postgres:${PG_MAJOR}", "FROM docker.io/library/postgres:${PG_MAJOR}"),
    ],
}

# =============================================================================
# Step 1/2 - Patch the Dockerfiles
# =============================================================================
for rel, changes in patches.items():
    path = vendor / rel
    if not path.is_file():
        sys.exit(f"Missing source Dockerfile: {path}")
    source = path.read_text()
    for before, after in changes:
        if after in source:
            continue
        if before not in source:
            sys.exit(f"Unexpected upstream content in {rel}: missing {before!r}")
        source = source.replace(before, after)
    if source != path.read_text():
        path.write_text(source)
        print(f"Patched {rel}")
    else:
        print(f"Already compatible: {rel}")
# =============================================================================
# Step 2/2 - Pin the compatible nodesig revision
# =============================================================================
# Firecrawl follows the moving default branch of nodesig. The newer nodesig
# requires kuchikiki 0.8.9-speedreader, incompatible with Firecrawl's own
# kuchikiki 0.8.2. Pin the previously compatible revision. Do not rewrite
# another explicit version/revision: fail visibly instead.
cargo = vendor / "apps/api/native/Cargo.toml"
if not cargo.is_file():
    sys.exit(f"Missing native Cargo.toml: {cargo}")
source = cargo.read_text()
old = 'nodesig = { git = "https://github.com/firecrawl/nodesig" }'
new = ('nodesig = { git = "https://github.com/firecrawl/nodesig", '
       'rev = "b8ebc4a710810dbc36e189d9a0df87b877702b3c" }')
if new in source:
    print("Already pinned: nodesig")
elif old in source:
    cargo.write_text(source.replace(old, new))
    print("Pinned nodesig to b8ebc4a710810dbc36e189d9a0df87b877702b3c")
else:
    sys.exit("Unexpected nodesig dependency declaration; inspect native/Cargo.toml")
print("Firecrawl builder and nodesig compatibility patches verified.")
