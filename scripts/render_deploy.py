#!/usr/bin/env python3
"""Render the small, isolated two-cohort benchmark. Does not contact Kubernetes."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NS = "cc-cep"
IMAGE = "cc-cep:0.1.0"  # local build, pullPolicy Never; build ID recorded before trials
PREFIX = "cc-cep.local/"


def render():
    objects = [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": NS,
                "labels": {"istio-injection": "enabled", PREFIX + "disposable": "true"},
            },
        }
    ]
    objects.append(
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "cc-cep-safety",
                "namespace": NS,
                "labels": {PREFIX + "disposable": "true"},
            },
            "data": {"purpose": "Disposable CC-CEP lab"},
        }
    )
    for cohort in ("control", "treatment"):
        for tier in ("frontend", "dependency"):
            name = f"{tier}-{cohort}"
            labels = {"app": name, "cohort": cohort, "tier": tier}
            env = [{"name": "CC_COHORT", "value": cohort}]
            if tier == "frontend":
                env.append(
                    {"name": "CC_DEPENDENCY_URL", "value": f"http://dependency-{cohort}:8000"}
                )
            objects.extend(
                [
                    {
                        "apiVersion": "v1",
                        "kind": "Service",
                        "metadata": {"name": name, "namespace": NS},
                        "spec": {
                            "selector": labels,
                            "ports": [{"name": "http", "port": 8000, "targetPort": 8000}],
                        },
                    },
                    {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": {"name": name, "namespace": NS},
                        "spec": {
                            "replicas": 1,
                            "selector": {"matchLabels": labels},
                            "template": {
                                "metadata": {"labels": labels},
                                "spec": {
                                    "automountServiceAccountToken": False,
                                    "securityContext": {"runAsNonRoot": True, "runAsUser": 10001},
                                    "containers": [
                                        {
                                            "name": "app",
                                            "image": IMAGE,
                                            "imagePullPolicy": "Never",
                                            "env": env,
                                            "ports": [{"containerPort": 8000}],
                                            "resources": {
                                                "requests": {"cpu": "100m", "memory": "96Mi"},
                                                "limits": {"cpu": "1", "memory": "256Mi"},
                                            },
                                            "securityContext": {
                                                "allowPrivilegeEscalation": False,
                                                "capabilities": {"drop": ["ALL"]},
                                            },
                                            "readinessProbe": {
                                                "httpGet": {"path": "/health", "port": 8000}
                                            },
                                            "livenessProbe": {
                                                "httpGet": {"path": "/health", "port": 8000},
                                                "initialDelaySeconds": 10,
                                            },
                                        }
                                    ],
                                },
                            },
                        },
                    },
                ]
            )
    from cc_cep.istio import safe_spec

    objects.append(
        {
            "apiVersion": "networking.istio.io/v1",
            "kind": "VirtualService",
            "metadata": {
                "name": "cc-cep-fault",
                "namespace": NS,
                "labels": {PREFIX + "managed": "true"},
                "annotations": {PREFIX + "expires": "0"},
            },
            "spec": safe_spec(),
        }
    )
    # Controller/watchdog mutate only the pre-created managed VirtualService.
    objects.extend(
        [
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "cc-cep-controller", "namespace": NS},
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {"name": "fault-editor", "namespace": NS},
                "rules": [
                    {
                        "apiGroups": [""],
                        "resources": ["configmaps"],
                        "resourceNames": ["cc-cep-safety"],
                        "verbs": ["get", "patch"],
                    },
                    {
                        "apiGroups": ["networking.istio.io"],
                        "resources": ["virtualservices"],
                        "resourceNames": ["cc-cep-fault"],
                        "verbs": ["get", "patch"],
                    },
                ],
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": "fault-editor", "namespace": NS},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": "fault-editor",
                },
                "subjects": [
                    {"kind": "ServiceAccount", "name": "cc-cep-controller", "namespace": NS}
                ],
            },
        ]
    )
    (ROOT / "deploy/benchmark.yaml").write_text(yaml.safe_dump_all(objects, sort_keys=False))


if __name__ == "__main__":
    render()
