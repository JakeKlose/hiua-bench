"""
Llama 3.1 8B Instruct on Modal via vLLM.

Usage (run these from your laptop, in the directory that contains this file):

  1. modal secret create hf-token HF_TOKEN=hf_xxx_your_token_here   # one time
  2. modal run llama_app.py::download_weights                       # one time, ~5-10 min
  3. modal run llama_app.py::smoke_test                             # ~3-8 min first call

After smoke_test works, call it from any Python script with `call_llama.py`.
"""

# IMPORTANT: do NOT add `from __future__ import annotations` here.
# Modal's parameter validator reads the class type hints at decoration time
# and chokes if they've been turned into strings by the future import.

import modal

# ---------- Edit these if you want a different model / GPU ---------------
HF_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
GPU = "L40S"           # L40S handles 8B BF16 comfortably for ~$1.95/hr
DTYPE = "bfloat16"
MAX_MODEL_LEN = 8192   # context window vLLM will allocate
# -------------------------------------------------------------------------

# A Modal Volume is persistent storage that survives container restarts.
# We download the ~16 GB of weights into it once, then every future GPU
# container mounts the volume and reads weights from disk instead of
# re-downloading from HuggingFace.
WEIGHTS_VOL = modal.Volume.from_name("llm-weights", create_if_missing=True)
WEIGHTS_DIR = "/weights"


def weights_subdir(hf_id: str) -> str:
    """Keep the real `/` in the path. vLLM's loader runs the path through
    a HuggingFace validator that insists the tail looks like 'org/repo'.
    If you sanitize the slash (e.g. to '__'), you get HFValidationError."""
    return f"{WEIGHTS_DIR}/{hf_id}"


# Image for the vLLM serving container. Pinned versions are CRITICAL:
#   - vllm 0.8.5 is widely tested
#   - transformers needs an UPPER bound; vllm's setup.py only says
#     `transformers>=4.51.1` and pip will happily pick 5.x which removed
#     methods that vllm still calls. Cap at <4.56.
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
        # These two stop HF helpers from rejecting our local /weights path
        # because it doesn't look like a canonical HF repo URL.
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
)

# CPU-only image for the downloader. No vllm here — vllm is a huge install
# and we don't want to pay GPU rates while we wait for HF to send bytes.
download_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("llama-8b")


# --------------------------------------------------------------------------
# Step 1 of cloud lifecycle: download weights into the persistent volume.
# Runs on a cheap CPU container. You only do this once per model.
# --------------------------------------------------------------------------

@app.function(
    image=download_image,
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=60 * 60,
    secrets=[modal.Secret.from_name("hf-token")],   # Llama is a gated model
)
def download_weights(hf_id: str = HF_MODEL_ID) -> str:
    from huggingface_hub import snapshot_download
    target = weights_subdir(hf_id)
    print(f"[download] {hf_id} -> {target}")
    snapshot_download(
        repo_id=hf_id,
        local_dir=target,
        max_workers=8,
        # Only pull what vLLM needs for inference. Skips PyTorch .bin
        # mirrors, training-only files, etc.
        allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.model", "*.txt"],
    )
    WEIGHTS_VOL.commit()   # make the writes visible to future containers
    print(f"[download] {hf_id} done")
    return target


# --------------------------------------------------------------------------
# Step 2: the actual inference container. @app.cls must be at module scope
# (Modal can't import classes defined inside other functions).
# --------------------------------------------------------------------------

@app.cls(
    image=vllm_image,
    gpu=GPU,
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=20 * 60,
    scaledown_window=5 * 60,   # keep the container warm for 5 min after last call
)
@modal.concurrent(max_inputs=8)   # one container can serve up to 8 requests at once
class Llama:
    # Bare `str` / `int`, NOT strings. modal.parameter() needs real type
    # objects, which is why we can't use `from __future__ import annotations`.
    hf_model_id: str = modal.parameter(default=HF_MODEL_ID)
    dtype: str = modal.parameter(default=DTYPE)
    max_model_len: int = modal.parameter(default=MAX_MODEL_LEN)

    @modal.enter()
    def load(self):
        """Runs once when the container starts up. Loads weights from the
        mounted volume into GPU memory and builds vLLM's CUDA graphs.
        Cold start is roughly 30-90 seconds for an 8B model."""
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
    def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        seed: int = 0,
    ) -> str:
        """One inference call. Uses the model's chat template so you can
        pass plain system/user strings without thinking about Llama's
        special tokens."""
        from vllm import SamplingParams
        prompt = self.tokenizer.apply_chat_template(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
        )
        outputs = self.llm.generate([prompt], params)
        return outputs[0].outputs[0].text


# --------------------------------------------------------------------------
# Step 3: a local entrypoint so you can verify the whole pipeline with
# `modal run llama_app.py::smoke_test`.
# --------------------------------------------------------------------------

@app.local_entrypoint()
def smoke_test():
    runner = Llama()
    out = runner.generate.remote(
        system="You are a precise assistant.",
        user="Reply with exactly: HELLO FROM LLAMA",
        temperature=0.0,
        max_tokens=20,
        seed=0,
    )
    print(f"OUTPUT: {out!r}")
