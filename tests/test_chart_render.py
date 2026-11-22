import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HELM = shutil.which("helm")
CHART = ROOT

BASE_VALUES = {
    "secret": {
        "postgresUser": "postgres",
        "postgresDb": "firecrawl",
        "postgresPassword": "known-postgres-password",
        "searxngSecret": "known-searxng-secret",
        "bullAuthKey": "known-bull-auth-key",
    }
}

FORBIDDEN = "her" + "mes"


def render(extra_values=None):
    values = dict(BASE_VALUES)
    if extra_values:
        values.update(extra_values)
    with tempfile.TemporaryDirectory() as tmp:
        values_path = Path(tmp) / "values.yaml"
        values_path.write_text(yaml.safe_dump(values), encoding="utf-8")
        result = subprocess.run(
            [
                HELM,
                "template",
                "firecrawl",
                str(CHART),
                "--namespace",
                "firecrawl",
                "--values",
                str(values_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def by_kind(docs, kind):
    return [doc for doc in docs if doc["kind"] == kind]


def by_name(docs, kind, name):
    for doc in docs:
        if doc["kind"] == kind and doc["metadata"]["name"] == name:
            return doc
    raise AssertionError(f"{kind}/{name} not rendered")


@unittest.skipUnless(HELM, "helm is not installed")
class ChartRenderTests(unittest.TestCase):
    def test_renders_the_expected_workloads(self):
        docs = render()
        services = {doc["metadata"]["name"] for doc in by_kind(docs, "Service")}
        deployments = {doc["metadata"]["name"] for doc in by_kind(docs, "Deployment")}
        statefulsets = {doc["metadata"]["name"] for doc in by_kind(docs, "StatefulSet")}

        self.assertEqual(
            services,
            {
                "firecrawl-api",
                "firecrawl-playwright",
                "firecrawl-searxng",
                "firecrawl-redis",
                "firecrawl-rabbitmq",
                "firecrawl-nuq-postgres",
            },
        )
        self.assertEqual(
            deployments,
            {"firecrawl-api", "firecrawl-playwright", "firecrawl-searxng"},
        )
        self.assertEqual(
            statefulsets,
            {"firecrawl-redis", "firecrawl-rabbitmq", "firecrawl-nuq-postgres"},
        )

    def test_generated_secret_has_required_keys(self):
        docs = render()
        secret = by_name(docs, "Secret", "firecrawl-secrets")
        self.assertEqual(
            set(secret["stringData"]),
            {
                "POSTGRES_USER",
                "POSTGRES_DB",
                "POSTGRES_PASSWORD",
                "SEARXNG_SECRET",
                "BULL_AUTH_KEY",
            },
        )
        self.assertEqual(secret["stringData"]["POSTGRES_DB"], "firecrawl")

    def test_existing_secret_suppresses_the_chart_secret(self):
        docs = render({"existingSecret": "external-firecrawl-secrets"})
        self.assertEqual(by_kind(docs, "Secret"), [])
        api = by_name(docs, "Deployment", "firecrawl-api")
        env = {
            entry["name"]: entry
            for entry in api["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        self.assertEqual(
            env["POSTGRES_PASSWORD"]["valueFrom"]["secretKeyRef"]["name"],
            "external-firecrawl-secrets",
        )

    def test_password_never_appears_in_a_configmap(self):
        docs = render()
        password = BASE_VALUES["secret"]["postgresPassword"]
        for doc in by_kind(docs, "ConfigMap"):
            self.assertNotIn(password, yaml.safe_dump(doc))

    def test_names_are_configurable(self):
        docs = render(
            {
                "names": {
                    "api": "custom-api",
                    "playwright": "custom-playwright",
                    "searxng": "custom-searxng",
                    "redis": "custom-redis",
                    "rabbitmq": "custom-rabbitmq",
                    "nuqPostgres": "custom-postgres",
                }
            }
        )
        services = {doc["metadata"]["name"] for doc in by_kind(docs, "Service")}
        self.assertIn("custom-api", services)
        self.assertIn("custom-postgres", services)
        config = by_name(docs, "ConfigMap", "custom-api-config")
        self.assertEqual(config["data"]["POSTGRES_HOST"], "custom-postgres")

    def test_network_policy_is_disabled_by_default(self):
        docs = render()
        self.assertEqual(by_kind(docs, "NetworkPolicy"), [])

    def test_network_policy_renders_generic_peer_rules(self):
        docs = render(
            {
                "networkPolicy": {
                    "enabled": True,
                    "ingress": {
                        "allowSameRelease": True,
                        "allowFrom": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {
                                        "kubernetes.io/metadata.name": "apps"
                                    }
                                },
                                "podSelector": {
                                    "matchLabels": {
                                        "app.kubernetes.io/name": "client"
                                    }
                                },
                            }
                        ],
                    },
                }
            }
        )
        egress = by_name(docs, "NetworkPolicy", "firecrawl-egress")
        ingress = by_name(docs, "NetworkPolicy", "firecrawl-ingress")
        self.assertEqual(egress["spec"]["policyTypes"], ["Egress"])
        self.assertEqual(ingress["spec"]["policyTypes"], ["Ingress"])
        rendered = yaml.safe_dump(ingress)
        self.assertIn("kubernetes.io/metadata.name: apps", rendered)
        self.assertIn("app.kubernetes.io/name: client", rendered)

    def test_persistence_is_configurable(self):
        docs = render(
            {
                "redis": {"persistence": {"storageClass": "fast", "size": "3Gi"}},
                "rabbitmq": {"persistence": {"storageClass": "fast", "size": "3Gi"}},
                "nuqPostgres": {"persistence": {"storageClass": "fast", "size": "8Gi"}},
            }
        )
        for name in ("firecrawl-redis", "firecrawl-rabbitmq", "firecrawl-nuq-postgres"):
            statefulset = by_name(docs, "StatefulSet", name)
            claim = statefulset["spec"]["volumeClaimTemplates"][0]
            self.assertEqual(claim["spec"]["storageClassName"], "fast")

    def test_images_support_digests(self):
        docs = render(
            {
                "images": {
                    "api": {
                        "repository": "ghcr.io/firecrawl/firecrawl",
                        "tag": "2.11.162",
                        "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
                        "pullPolicy": "IfNotPresent",
                    }
                }
            }
        )
        api = by_name(docs, "Deployment", "firecrawl-api")
        image = api["spec"]["template"]["spec"]["containers"][0]["image"]
        self.assertIn("@sha256:", image)

    def test_external_services_need_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            values_path = Path(tmp) / "values.yaml"
            values_path.write_text(
                yaml.safe_dump({"redis": {"enabled": False}}), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    HELM,
                    "template",
                    "firecrawl",
                    str(CHART),
                    "--namespace",
                    "firecrawl",
                    "--values",
                    str(values_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config.redisUrl is required", result.stderr)

    def test_lint_succeeds(self):
        result = subprocess.run(
            [
                HELM,
                "lint",
                str(CHART),
                "--values",
                str(ROOT / "ci" / "test-values.yaml"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rendered_manifests_have_no_legacy_references(self):
        rendered = yaml.safe_dump_all(render(), sort_keys=True).lower()
        self.assertNotIn(FORBIDDEN, rendered)


if __name__ == "__main__":
    unittest.main()
