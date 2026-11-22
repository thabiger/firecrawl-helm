#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${FIRECRAWL_VERSION:-v2.11.162}

if [ ! -d vendor/firecrawl/.git ]; then
  mkdir -p vendor
  git clone --branch "$VERSION" --depth 1 \
    https://github.com/firecrawl/firecrawl.git vendor/firecrawl
else
  echo "Retaining existing vendor/firecrawl checkout."
fi

python3 scripts/patch-firecrawl.py
