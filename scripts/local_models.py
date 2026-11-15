"""Start the project-local llama.cpp service installed for the measured WSL run."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".local-models"


def main():
    if sys.platform != "linux":
        raise SystemExit("Run this command inside the configured WSL/Linux project.")
    try:
        response = httpx.get("http://localhost:11435/v1/models", timeout=2)
        response.raise_for_status()
        print("Local model service already running:", [m["id"] for m in response.json()["data"]])
        return
    except httpx.HTTPError:
        pass
    gpu_servers = list((BASE / "llama-gpu").rglob("llama-server"))
    use_gpu = bool(gpu_servers) and (BASE / "gpu-lib-path.txt").exists()
    executable = gpu_servers[0] if use_gpu else BASE / "ubuntu-runtime/root/usr/bin/llama-server"
    if not executable.exists() or not (BASE / "models.ini").exists():
        raise SystemExit("Local runtime/weights are not installed here. See docs/OPEN_MODEL_COMPARISON.md.")
    backend = BASE / "ubuntu-runtime/root/usr/lib/x86_64-linux-gnu/ggml/backends0/libggml-cpu-alderlake.so"
    env = dict(os.environ)
    if use_gpu:
        env["LD_LIBRARY_PATH"] = (BASE / "gpu-lib-path.txt").read_text()
        env.pop("GGML_BACKEND_PATH", None)
    else:
        env.update(LD_LIBRARY_PATH=(BASE / "llama-env.txt").read_text(), GGML_BACKEND_PATH=str(backend))
    source = ["--models-dir", str(BASE / "gpu-models")] if use_gpu else ["--models-preset", str(BASE / "models.ini")]
    command = [str(executable), *source, "--models-max", "2",
               "--host", "127.0.0.1", "--port", "11435", "--ctx-size", "8192", "--parallel", "1", "--threads", "6", "--jinja"]
    if use_gpu:
        command += ["--n-gpu-layers", "99"]
    with (BASE / "llama-server.log").open("a") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
    (BASE / "llama-server.pid").write_text(str(process.pid))
    for _ in range(50):
        if process.poll() is not None:
            raise SystemExit(f"Model service stopped; inspect {BASE / 'llama-server.log'}")
        try:
            response = httpx.get("http://localhost:11435/v1/models", timeout=1)
            response.raise_for_status()
            print(f"Local model service ready on localhost:11435 (PID {process.pid})")
            return
        except httpx.HTTPError:
            time.sleep(.2)
    raise SystemExit("Model service is still starting; inspect .local-models/llama-server.log")


if __name__ == "__main__":
    main()
