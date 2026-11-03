"""Restricted Istio adapter for the dedicated kind-cc-cep disposable cluster only.

Istio has no fault TTL. Admission therefore requires a live independent watchdog.
ResourceVersion tests prevent stale cleanup/renewal writes from racing silently.
"""

import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

CONTEXT = "kind-cc-cep"
NAMESPACE = "cc-cep"
RESOURCE = "cc-cep-fault"
PREFIX = "cc-cep.local/"
HOST = "dependency-treatment.cc-cep.svc.cluster.local"


def safe_spec(fault=None):
    route = {"route": [{"destination": {"host": HOST, "port": {"number": 8000}}}]}
    if fault:
        route["fault"] = fault
    return {"hosts": [HOST], "exportTo": ["."], "http": [route]}


class IstioFault:
    def __init__(self, family="abort", binary=None, clock=time.time):
        if family not in {"abort", "delay"}:
            raise ValueError("unsupported fault family")
        self.family = family
        self.binary = str(binary or Path(__file__).resolve().parents[2] / ".tools/bin/kubectl")
        self.clock = clock

    def _run(self, *args, payload=None):
        result = subprocess.run(
            [
                self.binary,
                "--kubeconfig",
                str(Path(__file__).resolve().parents[2] / "kubeconfig.local"),
                "--context",
                CONTEXT,
                "--namespace",
                NAMESPACE,
                "--request-timeout=3s",
                *args,
            ],
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else None

    def inspect(self):
        namespace = self._run("get", "configmap", "cc-cep-safety", "-o", "json")
        if namespace["metadata"].get("labels", {}).get(PREFIX + "disposable") != "true":
            raise RuntimeError("namespace is not marked disposable")
        self.last_watchdog = float(
            namespace["metadata"].get("annotations", {}).get(PREFIX + "watchdog", 0)
        )
        resource = self._run("get", "virtualservice", RESOURCE, "-o", "json")
        if resource["metadata"].get("labels", {}).get(PREFIX + "managed") != "true":
            raise RuntimeError("refusing unmanaged VirtualService")
        if resource["spec"].get("hosts") != [HOST]:
            raise RuntimeError("unexpected target host")
        return resource

    def beat(self, now):
        self._run(
            "patch",
            "configmap",
            "cc-cep-safety",
            "--type=merge",
            "-p",
            json.dumps({"metadata": {"annotations": {PREFIX + "watchdog": str(now)}}}),
            "-o",
            "json",
        )

    def patch(self, resource, spec, annotations):
        # Patch annotation map atomically against the last resource version.
        metadata = resource["metadata"]
        merged = metadata.get("annotations", {}) | annotations
        operations = [
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": metadata["resourceVersion"],
            },
            {"op": "replace", "path": "/spec", "value": spec},
            {"op": "add", "path": "/metadata/annotations", "value": merged},
        ]
        return self._run(
            "patch",
            "virtualservice",
            RESOURCE,
            "--type=json",
            "-p",
            json.dumps(operations),
            "-o",
            "json",
        )

    def apply(self, intensity, ttl=5):
        if not math.isfinite(intensity) or not 0 <= intensity <= 1 or not 0 < ttl <= 10:
            raise ValueError("invalid finite fault intensity/TTL")
        resource = self.inspect()
        now = self.clock()
        heartbeat = self.last_watchdog
        if not 0 <= now - heartbeat <= 2:
            raise RuntimeError("independent watchdog heartbeat missing/stale")
        fault = (
            {"abort": {"httpStatus": 503, "percentage": {"value": intensity * 100}}}
            if self.family == "abort"
            else {"delay": {"fixedDelay": "600ms", "percentage": {"value": intensity * 100}}}
        )
        self.patch(
            resource,
            safe_spec(fault if intensity else None),
            {
                PREFIX + "expires": str(now + ttl),
                PREFIX + "updated": datetime.now(timezone.utc).isoformat(),
            },
        )
        current = self.inspect()
        if current["spec"] != safe_spec(fault if intensity else None):
            raise RuntimeError("Istio API fault readback mismatch")
        # API readback is not Envoy propagation proof; cluster validation must measure that.

    def clear(self):
        self.patch(self.inspect(), safe_spec(), {PREFIX + "expires": "0"})

    def active(self):
        return any("fault" in route for route in self.inspect()["spec"].get("http", []))
