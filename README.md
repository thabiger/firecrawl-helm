# Firecrawl Helm chart

A self-contained Helm chart for a single-node or small-cluster Firecrawl
deployment. It runs the Firecrawl API with its queue workers in one process,
plus the optional supporting services:

| Component | Default | Purpose |
|---|---|---|
| `api` | enabled | Firecrawl HTTP API and in-process queue workers |
| `playwright` | enabled | Browser renderer for JavaScript-heavy pages |
| `searxng` | enabled | Search backend used by Firecrawl search |
| `redis` | enabled | Rate limiting and queue cache |
| `rabbitmq` | enabled | NuQ job queue |
| `nuq-postgres` | enabled | NuQ job state and queue metadata |

The chart is generic: it does not assume a namespace, storage class, image
registry, ingress controller, or CNI. NetworkPolicy is available but opt-in.

## Requirements

- Kubernetes 1.27 or newer.
- A default StorageClass if persistence is enabled (the default).
- Outbound internet access from the Firecrawl pods for scraping.
- A CNI that enforces NetworkPolicy if you enable it (for example Calico).

## Install

Install from a checkout:

```bash
helm upgrade --install firecrawl . \
  --namespace firecrawl \
  --create-namespace
```

Or install the packaged chart from GitHub Releases:

```bash
helm upgrade --install firecrawl \
  https://github.com/thabiger/firecrawl-helm/releases/download/v0.1.0/firecrawl-0.1.0.tgz \
  --namespace firecrawl \
  --create-namespace
```

The chart is also published as an OCI artifact. Private repositories require a
registry login first:

```bash
echo "$GITHUB_TOKEN" | helm registry login ghcr.io -u YOUR_GITHUB_USER --password-stdin

helm upgrade --install firecrawl \
  oci://ghcr.io/thabiger/charts/firecrawl \
  --version 0.1.0 \
  --namespace firecrawl \
  --create-namespace
```

The chart creates its own Secret with generated credentials when
`existingSecret` is empty. This is the quickest way to get started. For a
production deployment, create the Secret outside the chart as shown below.

For a production deployment, create the Secret outside the chart and reference
it. The Secret must contain these keys:

- `POSTGRES_USER`
- `POSTGRES_DB`
- `POSTGRES_PASSWORD`
- `SEARXNG_SECRET`
- `BULL_AUTH_KEY`

```bash
kubectl -n firecrawl create secret generic firecrawl-secrets \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_DB=firecrawl \
  --from-literal=POSTGRES_PASSWORD='change-me' \
  --from-literal=SEARXNG_SECRET="$(openssl rand -hex 32)" \
  --from-literal=BULL_AUTH_KEY="$(openssl rand -hex 32)"

helm upgrade --install firecrawl . \
  --namespace firecrawl \
  --create-namespace \
  --values examples/values-existing-secret.yaml
```

The chart-generated Secret path uses `lookup` to preserve existing random
values across upgrades. Supplying values in `secret.*` overrides them.

## Verify

```bash
kubectl -n firecrawl rollout status deployment/firecrawl-api
kubectl -n firecrawl port-forward svc/firecrawl-api 3002:3002
curl -fsS http://localhost:3002/v0/health/readiness
```

Run one scrape through the API:

```bash
curl -fsS -X POST http://localhost:3002/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"]}'
```

## Values

The most important values are:

| Value | Default | Description |
|---|---|---|
| `existingSecret` | `""` | Use an external Secret instead of creating one |
| `secret.*` | generated | Credentials used when `existingSecret` is empty |
| `images.*` | pinned Firecrawl images | Image repository, tag, digest, and pull policy per component |
| `names.*` | `""` | Optional per-component service/workload name overrides |
| `service.*` | ClusterIP | Service type and port per component |
| `api.resources` | small | API requests and limits |
| `playwright.resources` | small | Browser renderer resources |
| `searxng.resources` | small | Search backend resources |
| `redis.*`, `rabbitmq.*`, `nuqPostgres.*` | small | Resources and persistence per stateful component |
| `config.*` | see `values.yaml` | Firecrawl concurrency, logging, and service URLs |
| `networkPolicy.enabled` | `false` | Opt-in egress and ingress policies |
| `commonLabels`, `podLabels`, `podAnnotations` | `{}` | Additional metadata |

Resource defaults are intentionally small. Raise them for production traffic,
especially `config.workersPerQueue`, `config.crawlConcurrentRequests`, and the
memory limits.

### External services

Disable the internal component and point the API at your own service. The
example in `examples/values-external-services.yaml` shows the full set. When a
component is disabled, the matching URL or host is required; the chart fails
early instead of rendering an unreachable deployment.

For credentials in external service URLs, use `api.extraEnvFrom` to reference a
Secret rather than placing them in `config.*`, which becomes a ConfigMap.

### Names

By default resources are named `<release>-<chart>-<component>` (or
`<release>-<component>` when the release name already contains the chart name).
Use `fullnameOverride` to control the prefix, or `names.*` to set exact names:

```yaml
names:
  api: firecrawl-api
  redis: firecrawl-redis
  rabbitmq: firecrawl-rabbitmq
  nuqPostgres: firecrawl-nuq-postgres
  searxng: firecrawl-searxng
  playwright: firecrawl-playwright
```

## Images

The default values use Firecrawl's published images for the API and for the
Playwright and NuQ Postgres services, pinned by digest or version. The API
`2.11.162` image is the same build that runs `node dist/src/harness.js
--start-docker`.

The official Playwright and NuQ Postgres images do not publish version tags,
so this chart pins their current digests. When changing the API version,
validate those two images against the new API or publish source-matched images
with the optional image workflow.

A non-empty `digest` takes precedence over `tag`. Clear `digest` when you want
to select an image by tag instead.

For a fully source-matched deployment, build the three Firecrawl images once
from the pinned source and use `examples/values-local-images.yaml`:

```bash
scripts/build-images.sh --load
```

The build script fetches Firecrawl `v2.11.162` into `vendor/firecrawl`, applies
the compatibility patches in `scripts/patch-firecrawl.py`, and builds:

- `localhost/firecrawl-api:2.11.162`
- `localhost/firecrawl-playwright:2.11.162`
- `localhost/firecrawl-nuq-postgres:2.11.162`

The optional `images.yaml` GitHub workflow publishes those images to GHCR for
use without a local Docker build. It is manual by design because the API image
is a large Rust and Node build.

## NetworkPolicy

NetworkPolicy is disabled by default because DNS selectors vary between
clusters. Enable it with `examples/values-secure-network.yaml` or your own
overrides. The defaults, once enabled:

- allow DNS to `kube-system`;
- allow traffic between pods in the same release;
- allow internet egress while excluding private, link-local, and metadata
  ranges;
- allow ingress only from the same release unless `ingress.allowFrom` adds
  peers.

Review the ranges before enabling. If your cluster uses a different DNS label
or you need private-network scraping, adjust the values.

Firecrawl is not an SSRF boundary. Keep outbound access narrow and do not
expose the API directly to untrusted networks without authentication.

## Persistence and backup

`redis`, `rabbitmq`, and `nuq-postgres` use StatefulSets with persistent volume
claims by default. Set `persistence.enabled: false` to use `emptyDir` for
ephemeral environments. Set `persistence.storageClass` per component, or leave
it empty to use the cluster default.

Back up the three volumes if job state and queued work matter. The chart does
not create backups automatically.

## Upgrade and uninstall

```bash
helm upgrade --install firecrawl . -n firecrawl -f values.yaml
helm uninstall firecrawl -n firecrawl
```

`helm uninstall` leaves PersistentVolumeClaims and Secrets created outside the
chart in place. Delete them deliberately.

## Development

```bash
helm lint . --values ci/test-values.yaml
helm template firecrawl . -n firecrawl --values ci/test-values.yaml
uv run --with pyyaml python -m unittest discover -s tests -v
```

## License

The chart source in this repository is MIT licensed; see `LICENSE`.

Firecrawl itself is licensed under AGPL-3.0. The default images are published
by the Firecrawl project. If you build and redistribute Firecrawl images, the
AGPL source-offer obligations apply; see `NOTICE`.
