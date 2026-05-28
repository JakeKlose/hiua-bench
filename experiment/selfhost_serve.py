"""
Self-hosted vLLM inference on Modal, v2 architecture.

This is the *replacement* for v1's broken selfhost.py (archived as
selfhost_v1_broken.py.archive). v1 tried to instantiate parameterized @app.cls
objects per-trial across two Modal apps, fan-out via .map(), and stack ~21
in-flight requests per warm container designed for max_inputs=8. That cascade
of bad joints produced six independent failure modes and zero usable trial
rows for ~$60 of Modal credit.

The new architecture is the one Modal's vllm_inference example documents:

  - One Modal-deployed function per model
  - Each function runs `vllm serve` in a subprocess inside a Modal container
  - The container exposes port 8000 via @modal.web_server, giving each model
    its own stable HTTPS endpoint like
    https://jfklosowski--hiua-selfhost-qwen-2-5-7b-serve.modal.run
  - The orchestrator calls these endpoints via the OpenAI-compatible HTTP API
    (POST /v1/chat/completions) using the openai Python client with base_url=
    pointed at the Modal endpoint
  - Scale-to-zero between runs (no GPU cost when idle)

Reference: https://modal.com/docs/examples/vllm_inference

Usage:

  # First-time setup: download weights for ONE model to the volume.
  modal run selfhost_serve.py::download_weights --display qwen-2.5-7b

  # Smoke test ONE model end-to-end (deploys + curls + tears down).
  modal run selfhost_serve.py::smoke --display qwen-2.5-7b

  # Once smoke passes for all models, deploy them as persistent endpoints:
  modal deploy selfhost_serve.py

  # Each model becomes callable at a URL printed during deploy.
  # The orchestrator (modal_app.py) reads MODEL_SERVE_URLS to know where to call.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aiohttp
import modal

# --------------------------------------------------------------------------
# App, volumes, image
# --------------------------------------------------------------------------

APP_NAME = "hiua-selfhost"
app = modal.App(APP_NAME)

# Weight cache: where HF snapshots land. Persistent across runs.
hf_cache_vol = modal.Volume.from_name("hiua-llm-weights", create_if_missing=True)
HF_CACHE_DIR = "/root/.cache/huggingface"

# vLLM JIT-compilation cache. Speeds up warm starts on the same GPU shape.
vllm_cache_vol = modal.Volume.from_name("hiua-vllm-cache", create_if_missing=True)
VLLM_CACHE_DIR = "/root/.cache/vllm"

# Container image — uv pip is faster than pip for the install.
# CUDA 12.9 matches what Modal's vllm_inference example uses for vLLM 0.21.
#
# Python version note: add_python MUST match the local Python version that
# defines the @app.function(serialized=True) bodies in _make_serve_function,
# because Modal pickles bytecode and pickled bytecode is Python-version-
# specific. The user runs anaconda's Python 3.13, so add_python="3.13" here.
# If you switch local Python versions, update both images below in lockstep.
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.13")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0", "huggingface_hub[hf_transfer]")
    .env({
        # Faster HF model transfers — the modern replacement for HF_HUB_ENABLE_HF_TRANSFER.
        "HF_XET_HIGH_PERFORMANCE": "1",
        # Less log spam from vLLM at startup.
        "VLLM_LOGGING_LEVEL": "WARN",
        # Stats logging cadence (seconds) for observability into per-model TPS.
        "VLLM_LOG_STATS_INTERVAL": "10",
        # CRITICAL: force vLLM + transformers to read model weights from the
        # local HF cache (hiua-llm-weights volume mounted at HF_CACHE_DIR)
        # instead of re-fetching from huggingface.co. Without these, vLLM
        # makes HEAD requests against HF's CDN at serve startup which get
        # rate-limited / connection-reset (observed in the llama-3.3-70b
        # smoke on 2026-05-27), and the load stalls indefinitely on retry
        # loops. v1's HANDOFF flagged the same fix in the archived selfhost.py.
        #
        # Note on paths: _download_one ran snapshot_download(cache_dir=HF_CACHE_DIR)
        # which deposits weights at HF_CACHE_DIR/models--<org>--<name>/snapshots/.
        # Setting HF_HOME alone is sufficient — HF_HUB_CACHE defaults to
        # $HF_HOME/hub but the downloader didn't use that subfolder, so we
        # explicitly override HF_HUB_CACHE to the same dir as HF_HOME to
        # match where the snapshots actually live.
        "HF_HOME": HF_CACHE_DIR,
        "HF_HUB_CACHE": HF_CACHE_DIR,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
    # CRITICAL: when @app.function(serialized=True) is used (as in
    # _make_serve_function below), Modal pickles the function bytecode. The
    # pickle contains module-level *references* (e.g. to spec, VLLM_PORT,
    # SPECS_BY_DISPLAY) that the container resolves by importing this very
    # file. Without add_local_python_source, the unpickler raises
    # `ModuleNotFoundError: No module named 'selfhost_serve'`. v1's HANDOFF
    # flagged this exact symptom as failure mode #1; we hit it again here.
    .add_local_python_source("selfhost_serve")
)

# CPU-only image for weight downloads. No GPU bill while we pull ~200 GB total.
# Python version pinned to 3.13 to match local (see vllm_image comment).
# _download_one is at module scope so the deserializer can find it by name,
# but we add the source anyway for consistency with vllm_image.
download_image = (
    modal.Image.debian_slim(python_version="3.13")
    .uv_pip_install("huggingface_hub[hf_transfer]")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
    .add_local_python_source("selfhost_serve")
)

# Secrets — only HF_TOKEN is required (for gated repos like Llama / Gemma).
secrets = [modal.Secret.from_name("hf-token")]


# --------------------------------------------------------------------------
# Model registry
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ServeSpec:
    display: str            # short name used in routing + URL generation
    hf_model_id: str        # HuggingFace repo id (canonical instruct version)
    gpu: str                # Modal GPU type string ("L40S" | "A100-80GB" | "H100")
    n_gpus: int             # number of GPUs (drives --tensor-parallel-size)
    max_model_len: int      # context window the served model exposes
    served_model_name: str  # what clients will use as `model=` in the OpenAI API

# IMPORTANT: GPU sizing is governed by bf16 weights ≈ 2 bytes/param + KV cache
# + activation headroom + CUDA overhead. v1's SELFHOST_SPECS undersized the
# 70B+ models on single H100 (80 GB VRAM); that's mathematically impossible
# (Llama-3.3-70B in bf16 = ~141 GB just for weights), confirmed by a
# torch.OutOfMemoryError during llama-3.3-70b smoke on 2026-05-27. Per-spec
# math below uses 2 bytes/param × #params for weight memory, then doubles
# that for total VRAM budget (KV cache + activations + overhead). H100 has
# 80 GB so single H100 caps at ~35B-param bf16 models.
SPECS: list[ServeSpec] = [
    # Cheap tier — L40S ($1.95/hr), single GPU, 7B–8B params, ~16 GB bf16
    ServeSpec("qwen-2.5-7b",  "Qwen/Qwen2.5-7B-Instruct",          "L40S",      1, 8192, "qwen-2.5-7b"),
    ServeSpec("llama-3.1-8b", "meta-llama/Llama-3.1-8B-Instruct",  "L40S",      1, 8192, "llama-3.1-8b"),
    # Cheap tier — A100-80GB ($3.30/hr), single GPU, 20B–27B params, ~40-54 GB bf16
    ServeSpec("gemma-2-27b",  "google/gemma-2-27b-it",             "A100-80GB", 1, 8192, "gemma-2-27b"),
    ServeSpec("gpt-oss-20b",  "openai/gpt-oss-20b",                "A100-80GB", 1, 8192, "gpt-oss-20b"),
    # Mid tier — 2x H100 ($11/hr), tensor-parallel.
    # Llama-3.3-70B: 70.6B × 2 = ~141 GB weights. Single H100 (80 GB) OOMs.
    # 2x H100 (160 GB) fits with ~19 GB KV+overhead headroom. Tight but works.
    ServeSpec("llama-3.3-70b","meta-llama/Llama-3.3-70B-Instruct", "H100",      2, 8192, "llama-3.3-70b"),
    # Qwen-2.5-72B: 72.7B × 2 = ~145 GB weights. Single H100 OOMs.
    # 2x H100 (160 GB) fits with ~15 GB KV+overhead headroom. Tight, may need
    # max_model_len lowered if KV cache blows.
    ServeSpec("qwen-2.5-72b", "Qwen/Qwen2.5-72B-Instruct",         "H100",      2, 8192, "qwen-2.5-72b"),
    # GPT-OSS-120B: 116.8B × 2 = ~234 GB weights. 2x H100 (160 GB) OOMs too.
    # Needs 4x H100 (320 GB), ~$22/hr. Expensive but the flagship OSS scale point.
    ServeSpec("gpt-oss-120b", "openai/gpt-oss-120b",               "H100",      4, 8192, "gpt-oss-120b"),
    # Opus tier — 2x H100 ($11/hr) MoE.
    # Qwen3-235B-A22B (MoE): 235B total but only 22B active per token. Weights
    # are quoted as ~470 GB in bf16, but MoE inference loads experts lazily.
    # vLLM's MoE handling on 2xH100 may OOM on weight load even though active
    # memory is small; if so, bump to 4xH100. This is the highest-risk model.
    ServeSpec("qwen3-235b",   "Qwen/Qwen3-235B-A22B-Instruct-2507","H100",      2, 8192, "qwen3-235b"),
]

# Lookup by display name. Functions defined below reference SPECS_BY_DISPLAY[name].
SPECS_BY_DISPLAY: dict[str, ServeSpec] = {s.display: s for s in SPECS}


def _gpu_string(spec: ServeSpec) -> str:
    """Modal GPU descriptor: e.g. 'L40S:1', 'H100:2'."""
    return f"{spec.gpu}:{spec.n_gpus}"


# --------------------------------------------------------------------------
# Weight download (CPU container — no GPU bill while pulling ~10–500 GB per model)
# --------------------------------------------------------------------------

@app.function(
    image=download_image,
    volumes={HF_CACHE_DIR: hf_cache_vol},
    secrets=secrets,
    timeout=2 * 60 * 60,   # some models take 30+ min to pull
    cpu=4.0,
)
def _download_one(hf_model_id: str) -> str:
    """Pull a HuggingFace repo's safetensors + tokenizer into the volume cache."""
    from huggingface_hub import snapshot_download
    print(f"[download] {hf_model_id} -> {HF_CACHE_DIR}")
    path = snapshot_download(
        repo_id=hf_model_id,
        cache_dir=HF_CACHE_DIR,
        max_workers=8,
        allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.model", "*.txt"],
    )
    hf_cache_vol.commit()   # persist to the volume so vllm serve can read it
    print(f"[download] {hf_model_id} done at {path}")
    return path


@app.local_entrypoint()
def download_weights(display: str = "all"):
    """Download weights for one model or all.

    Usage:
        modal run selfhost_serve.py::download_weights --display qwen-2.5-7b
        modal run selfhost_serve.py::download_weights --display all
    """
    if display == "all":
        targets = SPECS
    elif display in SPECS_BY_DISPLAY:
        targets = [SPECS_BY_DISPLAY[display]]
    else:
        raise SystemExit(
            f"unknown display name: {display!r}. "
            f"known: {sorted(SPECS_BY_DISPLAY)} or 'all'"
        )
    print(f"Downloading weights for {len(targets)} model(s):")
    for s in targets:
        print(f"  {s.display}  ({s.hf_model_id})")
    # Parallel download via .map() — each download is its own CPU container.
    # wrap_returned_exceptions=False opts into Modal's future behavior of
    # returning the underlying exception directly instead of the internal
    # UserCodeException wrapper. Suppresses the deprecation warning and
    # makes the `isinstance(r, Exception)` check below more meaningful when
    # we eventually log error types.
    hf_ids = [s.hf_model_id for s in targets]
    results = list(_download_one.map(
        hf_ids,
        return_exceptions=True,
        wrap_returned_exceptions=False,
    ))
    print("\n=== Download summary ===")
    for s, r in zip(targets, results):
        if isinstance(r, Exception):
            print(f"  FAIL  {s.display}  ({type(r).__name__}: {r})")
        else:
            print(f"  OK    {s.display}")


# Module-scope helper for list_cached_weights — Modal can't import a closure
# (qualname contains ".<locals>."), so this lives outside the entrypoint.
@app.function(image=download_image, volumes={HF_CACHE_DIR: hf_cache_vol})
def _list_cache_contents():
    import subprocess
    try:
        out = subprocess.check_output(
            ["du", "-sh", f"{HF_CACHE_DIR}/hub"], stderr=subprocess.STDOUT
        ).decode()
        print(out)
    except Exception as e:
        print(f"du failed: {e}")
    hub = f"{HF_CACHE_DIR}/hub"
    if os.path.isdir(hub):
        for entry in sorted(os.listdir(hub)):
            if entry.startswith("models--"):
                print(entry)


@app.local_entrypoint()
def list_cached_weights():
    """Print what's currently in the hiua-llm-weights volume."""
    _list_cache_contents.remote()


# --------------------------------------------------------------------------
# vLLM serve functions — one per model, generated programmatically at module
# scope. Modal requires decorators applied at module load time so the runtime
# can register each function for deployment.
# --------------------------------------------------------------------------
#
# Why one function per spec instead of one parameterized class?
#
# v1 tried the parameterized-class route: a single @app.cls with model_id as
# a modal.parameter(), instantiated per-call. That couples warm-container
# lifetime to per-call parameters and forces each (gpu, n_gpus) shape to be a
# separate class anyway. The result was complex enough that bugs hid in the
# joints. One concrete function per model is dumber and more debuggable: you
# can `modal run selfhost_serve.py::serve_qwen_2_5_7b` and only that one
# container starts, with no dispatch fan-out logic to mis-fire.
#
# The cost is module-level code generation. We do it explicitly in a `for`
# loop below, using `exec` only to bind the function name. The generated
# functions are otherwise identical except for the (gpu, n_gpus) decorator
# args and the captured spec object.

MINUTES = 60   # seconds
VLLM_PORT = 8000

# How long to stay warm with no traffic before scale-to-zero kicks in.
# 5 min is the Modal default; we leave it short so dev_selfhost runs don't
# leave a $5.50/hr H100 sitting idle after they finish.
SCALEDOWN_WINDOW = 5 * MINUTES

# How long Modal waits for vllm serve to come up before failing the container.
# Raised from 15 min to 30 min after the first dev_selfhost attempt timed out
# every H100 trial at the trial_selfhost layer's 20-min ceiling. The actual
# vLLM startup probably wasn't completing within that window for the bigger
# models (Llama-3.3-70B at ~140GB, Qwen-2.5-72B at ~145GB, GPT-OSS-120B at
# ~240GB) — weight load from the volume + JIT compile + first-token latency
# can easily exceed 15 min for those. 30 min gives real headroom. Qwen3-235B
# on 2xH100 might still be tight; if it specifically times out, bump further.
STARTUP_TIMEOUT = 30 * MINUTES


def _make_serve_function(spec: ServeSpec):
    """Build the @modal-decorated serve_<name>() function for one spec.

    Returns the decorated function so the caller can bind it as a module
    attribute. The function body launches `vllm serve` as a subprocess inside
    a Modal container of the right GPU shape, mounts the weight + JIT-cache
    volumes, and exposes port 8000 via @modal.web_server.
    """

    # serialized=True is REQUIRED here because Modal's function-import
    # validator rejects anything whose __qualname__ contains ".<locals>." —
    # which is exactly what a closure produced by a factory function looks
    # like. With serialized=True, Modal pickles the function bytes at deploy
    # time rather than importing by qualified name. Cost: a one-time
    # serialization at deploy time. Benefit: the factory pattern stays, so
    # one SPECS list still drives the entire panel and we don't have to
    # hand-write 8 near-identical @app.function blocks. v1's HANDOFF flagged
    # this exact gotcha for @app.cls; the same rule holds for @app.function.
    #
    # name=... gives each generated function a unique registration in the
    # Modal app. Without it, all 8 functions collide as
    # `_make_serve_function.<locals>._serve` and Modal overwrites each as we
    # iterate, so only the last one (qwen3-235b) would actually deploy.
    serve_name = "serve_" + spec.display.replace("-", "_").replace(".", "_")

    @app.function(
        name=serve_name,
        image=vllm_image,
        gpu=_gpu_string(spec),
        volumes={
            HF_CACHE_DIR: hf_cache_vol,
            VLLM_CACHE_DIR: vllm_cache_vol,
        },
        secrets=secrets,
        scaledown_window=SCALEDOWN_WINDOW,
        timeout=STARTUP_TIMEOUT,
        serialized=True,
    )
    @modal.concurrent(max_inputs=64)   # vLLM batches internally; this is per-replica
    @modal.web_server(port=VLLM_PORT, startup_timeout=STARTUP_TIMEOUT)
    def _serve():
        """Launch `vllm serve` in a subprocess. The @modal.web_server decorator
        waits for port 8000 to come up before reporting the container as ready.
        """
        import subprocess

        import json as _json
        cmd = [
            "vllm", "serve",
            spec.hf_model_id,
            "--served-model-name", spec.served_model_name,
            "--host", "0.0.0.0",
            "--port", str(VLLM_PORT),
            "--max-model-len", str(spec.max_model_len),
            "--uvicorn-log-level=info",
            # Fast boot: skip torch.compile + CUDA graph capture. Trades peak
            # throughput for ~30s faster cold starts. The right tradeoff while
            # we're iterating and each dev_selfhost run cold-starts every model.
            "--enforce-eager",
            # Tensor parallel for multi-GPU models (Qwen3-235B on 2x H100).
            "--tensor-parallel-size", str(spec.n_gpus),
            # Skip multimodal — saves a chunk of GPU memory for KV cache.
            # JSON via json.dumps + explicit shell-safe string (Modal's
            # vllm_inference example does the same). Without this, vLLM picks
            # up shell-interpreted brace tokens on some platforms.
            "--limit-mm-per-prompt", _json.dumps({"image": 0, "video": 0, "audio": 0}),
            # Use vLLM's default sampling config rather than each model's
            # shipped generation_config.json. This is critical for cross-model
            # methodology: without this flag, each model would serve under its
            # own trained defaults (Qwen2.5: temp=0.7, top_p=0.8, repetition
            # penalty=1.05; reasoning models often temp=0.6, top_p=0.95). The
            # orchestrator passes temperature explicitly per trial, so we want
            # the served model to honor that single source of truth rather
            # than mixing it with model-specific repetition penalties etc.
            "--generation-config", "vllm",
        ]
        print(f"[vllm serve] {spec.display}: launching")
        print(f"[vllm serve] cmd = {' '.join(cmd)}")
        subprocess.Popen(cmd)

    return _serve


# Bind one module-level function per spec. After this loop runs at import
# time, the module has serve_qwen_2_5_7b, serve_llama_3_1_8b, etc. — each a
# @modal-decorated function Modal can deploy independently.
for _spec in SPECS:
    _fn_name = "serve_" + _spec.display.replace("-", "_").replace(".", "_")
    globals()[_fn_name] = _make_serve_function(_spec)


# --------------------------------------------------------------------------
# Smoke test: end-to-end against ONE model.
#
# Use this BEFORE `modal deploy`. It spins up a fresh replica of one model's
# serve function (paying the cold-start), waits for the health endpoint, hits
# /v1/chat/completions, prints the response. If this works, the model is ready
# to be deployed for real.
#
# Per v1's HANDOFF: "Test ONE model end-to-end before scaling."
# --------------------------------------------------------------------------

@app.local_entrypoint()
def smoke(display: str = "qwen-2.5-7b", prompt: str | None = None):
    """Smoke-test a single model end-to-end.

    Spins up the model's serve function (cold start, can be slow on first run),
    hits /health, then sends one OpenAI-compatible chat completion request.

    Usage:
        modal run selfhost_serve.py::smoke --display qwen-2.5-7b
        modal run selfhost_serve.py::smoke --display llama-3.1-8b --prompt "Say hi."
    """
    if display not in SPECS_BY_DISPLAY:
        raise SystemExit(f"unknown display: {display}. known: {sorted(SPECS_BY_DISPLAY)}")
    spec = SPECS_BY_DISPLAY[display]
    fn = globals()["serve_" + spec.display.replace("-", "_").replace(".", "_")]
    asyncio.run(_smoke_async(fn, spec, prompt or "Say the word 'pong' and nothing else."))


async def _smoke_async(serve_fn, spec: ServeSpec, prompt: str):
    import time   # local because we only need it here, and want no top-level junk
    url = await serve_fn.get_web_url.aio()
    print(f"\n[smoke] {spec.display} ({spec.hf_model_id})")
    print(f"[smoke] URL: {url}")
    print(f"[smoke] Waiting for /health ...")
    t0 = time.time()
    async with aiohttp.ClientSession(base_url=url) as session:
        # Health check — Modal's @modal.web_server already waits for the port
        # to open, but vllm serve may take additional seconds after port-open
        # before the /health endpoint returns 200.
        for attempt in range(60):
            try:
                async with session.get("/health", timeout=10) as resp:
                    if resp.status == 200:
                        print(f"[smoke] /health OK after {time.time()-t0:.1f}s")
                        break
            except Exception:
                pass
            await asyncio.sleep(2.0)
        else:
            raise SystemExit(f"[smoke] /health never returned 200 (waited {time.time()-t0:.1f}s)")

        # Real request
        payload = {
            "model": spec.served_model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 50,
        }
        print(f"[smoke] POST /v1/chat/completions  payload.messages[0]={prompt!r}")
        t1 = time.time()
        async with session.post("/v1/chat/completions", json=payload, timeout=120) as resp:
            resp.raise_for_status()
            body = await resp.json()
        print(f"[smoke] response in {time.time()-t1:.2f}s")
        msg = body["choices"][0]["message"]["content"]
        print(f"\n[smoke] >>> {msg!r}")
        print(f"\n[smoke] OK. Model is responsive.")
