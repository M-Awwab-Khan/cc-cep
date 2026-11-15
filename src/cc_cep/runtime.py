"""Exclusive run locking, atomic checkpoints, and a bounded local fault adapter."""

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import httpx


class RunLock:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a")
        try:
            if os.name == "nt":
                import msvcrt

                self.file.seek(0, os.SEEK_END)
                if self.file.tell() == 0:
                    self.file.write("0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("another controller owns this target") from None
        return self

    def __exit__(self, *args):
        if os.name == "nt":
            import msvcrt

            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        self.file.close()


def checkpoint(path, controller):
    """Persist before applying the next fault. Restart is cleanup-only, never blind resume."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": controller.state,
        "cleanup_errors": controller.cleanup_errors,
        "reason": controller.reason,
        "last": asdict(controller.last) if controller.last else None,
        "ledgers": {k: asdict(v) for k, v in controller.ledgers.items()},
        "config": asdict(controller.config),
        "intensity": controller.intensity,
    }
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".checkpoint-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class LocalFault:
    def __init__(self, url, token, family="abort"):
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("local fault adapter requires loopback HTTP")
        if not token or family not in {"abort", "delay"}:
            raise ValueError("token and supported fault family required")
        self.url = url + "/local-fault"
        self.family = family
        self.client = httpx.Client(headers={"x-fault-token": token}, timeout=2, trust_env=False)

    def apply(self, intensity, ttl=2):
        response = self.client.put(
            self.url, json={"intensity": intensity, "ttl": ttl, "family": self.family}
        )
        response.raise_for_status()
        if self.active() != (intensity > 0):
            raise RuntimeError("fault readback mismatch")

    def clear(self):
        self.client.delete(self.url).raise_for_status()

    def active(self):
        response = self.client.get(self.url)
        response.raise_for_status()
        return response.json()["active"]


def process_token(pid):
    """Linux start-time token prevents a reused PID from being treated as our child."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None
