#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

needle="her""mes"

if grep -RIn \
    --exclude-dir=.git \
    --exclude-dir=vendor \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    -i "$needle" .; then
  printf 'Disallowed legacy reference found.\n' >&2
  exit 1
fi

printf 'No legacy references found.\n'
