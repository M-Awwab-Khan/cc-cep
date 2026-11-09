"""Small benchmark service; fault controls enabled ONLY for local loopback validation.

Cluster faults belong to Istio. The local lease is checked on every request, so a dead
controller cannot extend a fault. Separate instances provide independent cohort state.
"""

import asyncio
import hashlib
import os
import random
import secrets
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field

COHORT = os.environ.get("CC_COHORT", "control")
TOKEN = os.environ.get("CC_LOCAL_FAULT_TOKEN", "")
DEPENDENCY = os.environ.get("CC_DEPENDENCY_URL", "")
SYNTHETIC = os.environ.get("CC_SYNTHETIC_ENABLED") == "true"
REQUESTS = Counter("cc_requests", "Eligible server responses", ["cohort", "outcome"])
LATENCY = Histogram(
    "cc_duration_seconds",
    "Server latency",
    ["cohort"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
lease = {"intensity": 0.0, "expires": 0.0, "family": "abort", "delay": 0.6}


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=2) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


class Fault(BaseModel):
    intensity: float = Field(ge=0, le=1, allow_inf_nan=False)
    ttl: float = Field(gt=0, le=10, allow_inf_nan=False)
    family: str = "abort"
    delay: float = Field(default=0.6, gt=0, le=2, allow_inf_nan=False)


def authorize(token):
    if not TOKEN or COHORT != "treatment" or not secrets.compare_digest(token, TOKEN):
        raise HTTPException(403, "local fault control disabled")


@app.put("/local-fault")
async def set_fault(fault: Fault, x_fault_token: str = Header(default="")):
    authorize(x_fault_token)
    if fault.family not in {"abort", "delay"}:
        raise HTTPException(400, "unsupported fault family")
    lease.update(
        intensity=fault.intensity,
        expires=time.monotonic() + fault.ttl,
        family=fault.family,
        delay=fault.delay,
    )
    return {"active": fault.intensity > 0}


@app.delete("/local-fault")
async def clear_fault(x_fault_token: str = Header(default="")):
    authorize(x_fault_token)
    lease.update(intensity=0, expires=0)
    return {"active": False}


@app.get("/local-fault")
async def fault_status(x_fault_token: str = Header(default="")):
    authorize(x_fault_token)
    return {"active": time.monotonic() < lease["expires"] and lease["intensity"] > 0}


@app.get("/health")
async def health():
    return {"ok": True, "cohort": COHORT}


def organic_event(seed, key, cohort, probability):
    if not 0 <= probability <= 0.1:
        raise ValueError("synthetic probability must be in [0, .1]")
    value = int.from_bytes(hashlib.sha256(f"{seed}:{cohort}:{key}".encode()).digest()[:8], "big")
    return value / 2**64 < probability


@app.get("/work")
async def work(
    x_cc_seed: str = Header(default="0"),
    x_cc_key: str = Header(default=""),
    x_cc_background: float = Header(default=0),
):

    started = time.perf_counter()
    failed = False
    try:
        if SYNTHETIC and organic_event(x_cc_seed, x_cc_key, COHORT, x_cc_background):
            failed = True
            raise HTTPException(503, "synthetic organic error", headers={"X-CC-Organic": "1"})
        if time.monotonic() < lease["expires"] and random.random() < lease["intensity"]:
            if lease["family"] == "abort":
                failed = True
                raise HTTPException(503, "injected abort")
            await asyncio.sleep(lease["delay"])
        if DEPENDENCY:
            response = await app.state.client.get(DEPENDENCY + "/work")
            if response.status_code >= 400:
                failed = True
                raise HTTPException(502, "dependency error")
        else:
            await asyncio.sleep(0.005)
        return {"ok": True, "cohort": COHORT}
    except httpx.HTTPError:
        failed = True
        raise HTTPException(504, "dependency timeout") from None
    finally:
        REQUESTS.labels(COHORT, "failure" if failed else "success").inc()
        LATENCY.labels(COHORT).observe(time.perf_counter() - started)
