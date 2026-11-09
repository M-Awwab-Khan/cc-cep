"""Temporary opt-in stack tracing for the disposable benchmark; restores commands afterward."""

import argparse
import json
import signal
import subprocess
import threading
import time
import traceback
from pathlib import Path

from cc_cep.cluster_smoke import smoke
from cc_cep.evidence import ROOT
from cc_cep.istio import IstioFault
from cc_cep.live import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False, parents=True)
    base = [
        str(ROOT / ".tools/bin/kubectl"),
        "--kubeconfig",
        str(ROOT / "kubeconfig.local"),
        "--context",
        "kind-cc-cep",
        "-n",
        "cc-cep",
    ]

    def kubectl(*arguments, timeout=20):
        result = subprocess.run(
            [*base, *arguments], capture_output=True, text=True, timeout=timeout
        )
        if result.returncode:
            raise RuntimeError(result.stderr[-3000:])
        return result.stdout

    def patch(name, command):
        value = {
            "spec": {"template": {"spec": {"containers": [{"name": "app", "command": command}]}}}
        }
        kubectl("patch", "deployment", name, "--type=strategic", "-p", json.dumps(value))
        kubectl("rollout", "status", "deployment/" + name, "--timeout=120s", timeout=130)

    original = {}
    stop = threading.Event()
    worker = None

    def sample():
        probe = (
            "import os,signal,urllib.request,json; os.kill(1,signal.SIGUSR1); "
            "print(open('/proc/1/stat').read()); "
            "print('fds',len(os.listdir('/proc/1/fd'))); "
            "print(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).read().decode())"
        )
        while not stop.wait(10):
            for cohort in ("control", "treatment"):
                name = "frontend-" + cohort
                with (output / (cohort + "-samples.log")).open("a") as log:
                    log.write(f"\nUTC_EPOCH {time.time()}\n")
                    for command in (
                        ("exec", "deployment/" + name, "-c", "app", "--", "python", "-c", probe),
                        ("logs", "deployment/" + name, "-c", "app", "--since=30s", "--tail=160"),
                    ):
                        try:
                            log.write(kubectl(*command, timeout=8))
                        except Exception as exc:
                            log.write(repr(exc) + "\n")

    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if IstioFault().active():
            raise RuntimeError("another fault is active; refusing diagnostic")
        command = [
            "python",
            "-c",
            "import faulthandler,signal,uvicorn; faulthandler.register(signal.SIGUSR1,all_threads=True); uvicorn.run('cc_cep.app:app',host='0.0.0.0',port=8000,access_log=False)",
        ]
        for name in ("frontend-control", "frontend-treatment"):
            deployment = json.loads(kubectl("get", "deployment", name, "-o", "json"))
            app = next(
                c
                for c in deployment["spec"]["template"]["spec"]["containers"]
                if c["name"] == "app"
            )
            original[name] = app.get("command")
            (output / "original-commands.json").write_text(json.dumps(original, indent=2))
            patch(name, command)
        config = json.loads((ROOT / "results/raw/high-load-diagnosis-01/config.json").read_text())
        config.update(
            workload_seed=9003,
            purpose="Instrumented no-fault stall diagnosis; excluded from comparison data",
        )
        (output / "config.json").write_text(json.dumps(config, indent=2))
        smoke(output / "safety")
        worker = threading.Thread(target=sample, daemon=True)
        worker.start()
        result = run(output / "config.json", output / "safety/integration.json", output / "trial")
        (output / "diagnostic-status.json").write_text(json.dumps(result, indent=2))
    except BaseException:
        (output / "diagnostic-error.txt").write_text(traceback.format_exc())
        raise
    finally:
        stop.set()
        if worker:
            worker.join(timeout=35)
        restored = {}
        for name, command in original.items():
            try:
                patch(name, command)
                restored[name] = True
            except Exception as exc:
                restored[name] = repr(exc)
        (output / "restoration.json").write_text(json.dumps(restored, indent=2))


if __name__ == "__main__":
    main()
