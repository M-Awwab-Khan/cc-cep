from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NS = "cc-cep"
PROM = "prom/prometheus:v3.15.1@sha256:fa3302279710be2f21a8301ec17a8b4f2301fd829bd113839b3b6b02b6f191a2"
GRAFANA = (
    "grafana/grafana:13.3.0@sha256:488984b716c0862639f91a698adbe2862677a5a07bad42da5f03f3030883b205"
)


def main():
    config = {
        "global": {"scrape_interval": "1s"},
        "scrape_configs": [
            {
                "job_name": "benchmark",
                "metrics_path": "/metrics/",
                "static_configs": [
                    {
                        "targets": [f"{tier}-{cohort}:8000"],
                        "labels": {"cohort": cohort, "tier": tier},
                    }
                    for cohort in ("control", "treatment")
                    for tier in ("frontend", "dependency")
                ],
            }
        ],
    }
    datasource = {
        "apiVersion": 1,
        "datasources": [
            {
                "name": "Prometheus",
                "type": "prometheus",
                "access": "proxy",
                "url": "http://prometheus:9090",
                "isDefault": True,
            }
        ],
    }
    objects = [
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "prometheus-config", "namespace": NS},
            "data": {"prometheus.yml": yaml.safe_dump(config)},
        },
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "grafana-datasource", "namespace": NS},
            "data": {"datasource.yaml": yaml.safe_dump(datasource)},
        },
    ]
    for name, image, port, volume, mount, args in (
        (
            "prometheus",
            PROM,
            9090,
            "prometheus-config",
            "/etc/prometheus",
            [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.path=/prometheus",
                "--storage.tsdb.retention.time=2h",
            ],
        ),
        (
            "grafana",
            GRAFANA,
            3000,
            "grafana-datasource",
            "/etc/grafana/provisioning/datasources",
            None,
        ),
    ):
        container = {
            "name": name,
            "image": image,
            "ports": [{"containerPort": port}],
            "resources": {
                "requests": {"cpu": "100m", "memory": "128Mi"},
                "limits": {"cpu": "1", "memory": "512Mi"},
            },
            "volumeMounts": [{"name": "config", "mountPath": mount}],
        }
        if args:
            container["args"] = args
        else:
            # Disposable local dashboard; never exposed with a LoadBalancer or NodePort.
            container["env"] = [
                {"name": "GF_AUTH_ANONYMOUS_ENABLED", "value": "true"},
                {"name": "GF_AUTH_ANONYMOUS_ORG_ROLE", "value": "Viewer"},
                {"name": "GF_AUTH_DISABLE_LOGIN_FORM", "value": "true"},
            ]
        objects.extend(
            [
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"name": name, "namespace": NS},
                    "spec": {
                        "selector": {"app": name},
                        "ports": [{"port": port, "targetPort": port}],
                    },
                },
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": name, "namespace": NS},
                    "spec": {
                        "replicas": 1,
                        "selector": {"matchLabels": {"app": name}},
                        "template": {
                            "metadata": {
                                "labels": {"app": name},
                                "annotations": {"sidecar.istio.io/inject": "false"},
                            },
                            "spec": {
                                "automountServiceAccountToken": False,
                                "containers": [container],
                                "volumes": [{"name": "config", "configMap": {"name": volume}}],
                            },
                        },
                    },
                },
            ]
        )
    (ROOT / "deploy/observability.yaml").write_text(yaml.safe_dump_all(objects, sort_keys=False))


if __name__ == "__main__":
    main()
