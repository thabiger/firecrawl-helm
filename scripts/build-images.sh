#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${FIRECRAWL_VERSION:-v2.11.162}
TAG=${FIRECRAWL_IMAGE_TAG:-${VERSION#v}}
LOAD=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --load) LOAD=1 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ ! -f vendor/firecrawl/apps/api/Dockerfile ]; then
  scripts/fetch-firecrawl.sh
fi

docker build -f vendor/firecrawl/apps/api/Dockerfile \
  -t "localhost/firecrawl-api:$TAG" vendor/firecrawl/apps/api
docker build -f vendor/firecrawl/apps/playwright-service-ts/Dockerfile \
  -t "localhost/firecrawl-playwright:$TAG" vendor/firecrawl/apps/playwright-service-ts
docker build -f vendor/firecrawl/apps/nuq-postgres/Dockerfile \
  -t "localhost/firecrawl-nuq-postgres:$TAG" vendor/firecrawl/apps/nuq-postgres

if [ "$LOAD" -eq 1 ]; then
  command -v minikube >/dev/null 2>&1 || {
    echo "minikube is required for --load" >&2
    exit 1
  }
  for image in \
    "localhost/firecrawl-api:$TAG" \
    "localhost/firecrawl-playwright:$TAG" \
    "localhost/firecrawl-nuq-postgres:$TAG"; do
    minikube image load "$image"
  done
fi

printf '\nBuilt:\n'
printf '  localhost/firecrawl-api:%s\n' "$TAG"
printf '  localhost/firecrawl-playwright:%s\n' "$TAG"
printf '  localhost/firecrawl-nuq-postgres:%s\n' "$TAG"
