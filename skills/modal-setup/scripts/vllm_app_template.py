"""
Working template: serve an open-weights LLM on Modal via vLLM.

Copy this file into your project, change HF_MODEL_ID and GPU at the top, then:

  1. modal secret create hf-token HF_TOKEN=<your-token>        # one-time
  2. modal run vllm_app_template.py::download_weights          # one-time, ~5 min
  3. modal run vllm_app_template.py::smoke_test                # ~3 min first call

This template bakes in every Modal+vLLM gotcha we know about:
  - No `from __future__ import annotations` (would break modal.parameter())
  - Module-scope @app.cls (no factory functions)
  - Upper bound on transformers (vLLM's open bound resolves to broken majors)
  - Real-slash weight path layout (HF validator rejects sanitized paths)
  - scaledown_window not container_idle_timeout (Modal v1 rename)
  - @modal.concurrent for parallelism (allow_concurrent_inputs deprecated)
  - HF_HUB_OFFLINE to skip HF validator on local-only paths
"""

# DO NOT add `from __future__ import annotations` here. Modal's parameter
# validator reads class annotations at decoration time and chokes on strings.

import os
import modal

# ---------- Edit these for your use case --------------------------------
HF_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"   # any HuggingFace instruct model
GPU = "L40S"                                # L40S / A100-80GB / H100 / H100:2
DTYPE = "bfloat16"                          # bfloat16 (most models) or "auto"
MAX_MODEL_LEN = 8192                        # context window vLLM will allocate
# -----------------------------------------------------------------------

WEIGHTS_VOL = modal.Volume.from_name("llm-weights", create_if_missing=True)
WEIGHTS_DIR = "/weights"

# Image for vLLM serving. Pinned versions are critical:
#   - vllm 0.8.5 (April 2025) is widely tested
#   - transformers UPPER bound is critical; vllm's setup.py only says
#     `transformers>=4.51.1` and pip will happily pick 5.x which broke vllm's
#     tokenizer cache. Cap at <4.56.
#   - HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE prevent HF helpers from rejecting
#     paths that don't look like canonical org/name HF repo IDs.
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.11")
    .pip_install(
        "vllm==0.8.5",
        "transformers>=4.51.1,<4.56",
        "huggingface_hub[hf_transfer]",
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "HF_XET_HIGH_PERFORMANCE": "1",
        "VLLM_LOGGING_LEVEL": "WARN",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
)

# CPU-only image for the weight downloader. Faster builds, cheaper to run
# than spinning up a GPU container just to call HuggingFace.
download_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("vllm-template")


def weights_subdir(hf_id: str) -> str:
    """Keep the real `/` in the path. vLLM's HF validator inspects the model
    path and rejects anything not in `namespace/repo_name` shape. Sanitizing
    the slash to e.g. `__` will cause HFValidationError."""
    return f"{WEIGHTS_DIR}/{hf_id}"


# --------------------------------------------------------------------------
# Weight downloader — runs once per model, results persist in the volume
# --------------------------------------------------------------------------

@app.function(
    image=download_image,
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=60 * 60,
    secrets=[modal.Secret.from_name("hf-token")],   # required for gated models
)
def download_weights(hf_id: str = HF_MODEL_ID) -> str:
    """Pull weights from HuggingFace to the persistent volume. Idempotent."""
    from huggingface_hub import snapshot_download
    target = weights_subdir(hf_id)
    print(f"[download] {hf_id} -> {target}")
    snapshot_download(
        repo_id=hf_id, local_dir=target,
        max_workers=8,
        allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.model", "*.txt"],
    )
    WEIGHTS_VOL.commit()
    print(f"[download] {hf_id} done")
    return target


# --------------------------------------------------------------------------
# vLLM runner — @app.cls MUST be at module scope, not inside a factory.
# If you need multiple GPU shapes, duplicate this class for each shape.
# --------------------------------------------------------------------------

@app.cls(
    image=vllm_image,
    gpu=GPU,
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=20 * 60,
    scaledown_window=5 * 60,    # NOT container_idle_timeout (renamed in Modal v1)
)
@modal.concurrent(max_inputs=8)   # NOT allow_concurrent_inputs (deprecated)
class VLLMRunner:
    # Bare `str` / `int` — not strings. modal.parameter() needs real type objects,
    # which is why we can't use `from __future__ import annotations` in this file.
    hf_model_id: str = modal.parameter(default=HF_MODEL_ID)
    dtype: str = modal.parameter(default=DTYPE)
    max_model_len: int = modal.parameter(default=MAX_MODEL_LEN)

    @modal.enter()
    def load(self):
        from vllm import LLM
        local_dir = weights_subdir(self.hf_model_id)
        print(f"[vllm] loading {self.hf_model_id} from {local_dir}")
        self.llm = LLM(
            model=local_dir,
            dtype=self.dtype,
            gpu_memory_utilization=0.90,
            max_model_len=self.max_model_len,
            enforce_eager=False,
        )
        self.tokenizer = self.llm.get_tokenizer()
        print(f"[vllm] {self.hf_model_id} ready")

    @modal.method()
    def generate(self, system: str, user: str, seed: int = 0,
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        from vllm import SamplingParams
        prompt = self.tokenizer.apply_chat_template(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True,
        )
        params = SamplingParams(
            temperature=temperature, max_tokens=max_tokens, seed=seed,
        )
        outputs = self.llm.generate([prompt], params)
        return outputs[0].outputs[0].text


# --------------------------------------------------------------------------
# Local entry point — verify the whole pipeline works end-to-end
# --------------------------------------------------------------------------

@app.local_entrypoint()
def smoke_test():
    """One inference call to verify install / weights / vLLM all work.
    First call ~3-8 min (image build + weight load + vLLM init).
    Subsequent calls within scaledown_window (~5 min) are ~2 sec."""
    runner = VLLMRunner()
    out = runner.generate.remote(
        system="You are a precise assistant.",
        user="Say exactly: HELLO MODAL",
        seed=0, temperature=0.0, max_tokens=20,
    )
    print(f"OUTPUT: {out!r}")
