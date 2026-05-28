# vLLM on Modal — deep dive

Read this when the user is past the basic template and needs more complex vLLM serving on Modal: multiple models, different GPU shapes, quantization, multi-GPU MoE serving.

## Table of contents

1. The three layers that interact
2. Pre-caching weights (do this once per model)
3. One class per GPU shape — and why
4. Sizing GPUs to models
5. Multi-GPU and MoE models
6. Quantization (FP8, MXFP4, AWQ)
7. Keeping containers warm vs. cold-starting
8. When to NOT self-host

## 1. The three layers that interact

Self-hosting an LLM on Modal involves three independently-evolving software layers, and most of the painful debugging is friction between them.

**Modal SDK** controls the container lifecycle, GPU allocation, secrets, volumes, and how your Python code gets shipped to the cloud. Updates can deprecate decorator arguments (`container_idle_timeout` → `scaledown_window`) or change class-parameter validation.

**vLLM** is the inference engine. It loads model weights into GPU memory, builds CUDA graphs, and serves generation requests. vLLM evolves fast and is fussy about its `transformers` and `torch` versions.

**transformers + huggingface_hub** is what vLLM uses for tokenizer loading and path validation. Major-version bumps here have broken vLLM repeatedly (e.g., transformers 5.x removing `all_special_tokens_extended`).

The way to navigate this: when something breaks, ask which layer is talking. The error message usually names it (`modal.exception.X`, `vllm.X`, `huggingface_hub.X`). Then check that layer's release notes for breaking changes.

## 2. Pre-caching weights (do this once per model)

Loading model weights from HuggingFace inside a GPU container is wasteful — you'd pay GPU-hour rates while the container downloads ~15-150GB from HF. Instead, cache weights once on a Modal volume using a cheap CPU container:

```python
@app.function(
    image=download_image,                # CPU-only, no vllm
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=60 * 60,
    secrets=[modal.Secret.from_name("hf-token")],
)
def download_weights(hf_id: str) -> str:
    from huggingface_hub import snapshot_download
    target = f"{WEIGHTS_DIR}/{hf_id}"     # KEEP the slash
    snapshot_download(
        repo_id=hf_id, local_dir=target,
        allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.model", "*.txt"],
    )
    WEIGHTS_VOL.commit()
    return target
```

A few practical notes:

- **`allow_patterns` matters.** Without it, snapshot_download pulls every file in the repo including readmes, GGUF variants, and training-only files. The pattern above gets the inference essentials and skips the rest.
- **Gated models need HF_TOKEN.** Llama and a few other model families require accepting a license on the HF model page. The user has to do this in a browser; Modal can't do it for them. After they accept, set HF_TOKEN as the `hf-token` Modal secret.
- **Bandwidth, not GPU, is the bottleneck.** Modal's CPU containers max out at ~300 MB/s pulling from HF (with `hf-transfer` enabled). A 70B model in BF16 (~140 GB) takes ~8-10 minutes.
- **Volumes persist.** Run the downloader once, then re-run as many GPU experiments as you want without re-downloading.

To pre-cache many models at once, use `.map()`:

```python
@app.local_entrypoint()
def download_all():
    hf_ids = ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct", ...]
    list(download_weights.map(hf_ids))   # runs in parallel
```

## 3. One class per GPU shape — and why

The natural impulse when you have 5 models on 4 different GPU shapes is to write one factory function that generates an `@app.cls` per shape. **That fails** with `LocalFunctionError: Modal can only import functions defined in global scope`.

Modal serializes the class decorator at app-build time and needs the class to be at module scope. The workaround is to write one class per GPU shape, all at module scope, parameterized by `modal.parameter()` for the model-specific bits:

```python
@app.cls(image=vllm_image, gpu="L40S", volumes={WEIGHTS_DIR: WEIGHTS_VOL},
         scaledown_window=5*60)
@modal.concurrent(max_inputs=8)
class VLLMRunner_L40S_x1:
    hf_model_id: str = modal.parameter()
    dtype: str = modal.parameter(default="bfloat16")
    max_model_len: int = modal.parameter(default=8192)
    def _n_gpus(self): return 1
    @modal.enter()
    def load(self): _vllm_load(self)   # shared helper at module scope
    @modal.method()
    def generate(self, ...): return _vllm_generate(self, ...)


@app.cls(image=vllm_image, gpu="H100", volumes={WEIGHTS_DIR: WEIGHTS_VOL},
         scaledown_window=5*60)
@modal.concurrent(max_inputs=8)
class VLLMRunner_H100_x1:
    # same body as above, different gpu= in the decorator
    ...
```

Then map shape → class with a plain dict:

```python
_RUNNER_BY_SHAPE = {
    ("L40S", 1):      VLLMRunner_L40S_x1,
    ("A100-80GB", 1): VLLMRunner_A100_x1,
    ("H100", 1):      VLLMRunner_H100_x1,
    ("H100", 2):      VLLMRunner_H100_x2,
}

def get_runner_for(model_spec):
    cls = _RUNNER_BY_SHAPE[(model_spec.gpu, model_spec.n_gpus)]
    return cls(hf_model_id=model_spec.hf_id, dtype=model_spec.dtype)
```

This is more verbose than the factory but it's the only way that works.

## 4. Sizing GPUs to models

A rough cheat sheet for VRAM requirements:

| Model size | BF16 VRAM | FP8 VRAM | Minimum GPU | Modal $/hr |
|-----------|-----------|----------|-------------|------------|
| 7B-8B     | ~16 GB    | ~10 GB   | L40S        | $1.95      |
| 13B       | ~26 GB    | ~14 GB   | L40S / A100-40GB | $1.95-2.10 |
| 30B       | ~65 GB    | ~35 GB   | A100-80GB   | $3.30      |
| 70B       | ~140 GB   | ~75 GB   | 2× H100 (BF16) / 1× H100 (FP8) | $5.50-11 |
| 120B      | —         | ~90 GB   | 1× H100     | $5.50      |
| 235B MoE  | —         | ~130 GB  | 2× H100     | $11        |
| 405B+     | —         | ~250 GB  | 4× H100     | $22        |
| 671B MoE  | —         | ~370 GB  | 8× H100     | $44        |

Rules of thumb:
- For a model in `dtype="bfloat16"`, multiply parameter count by 2 to estimate VRAM in bytes (so 70B → ~140 GB).
- For FP8, divide BF16 by ~1.9.
- Add ~10-20% for KV cache + activations.
- vLLM's `gpu_memory_utilization=0.90` leaves headroom; lower to 0.80 if you see OOM.

## 5. Multi-GPU and MoE models

For multi-GPU serving, set `gpu="H100:2"` (or `:4`, `:8`) in `@app.cls` and `tensor_parallel_size=N` in your vLLM init call. vLLM handles tensor parallelism automatically for most architectures.

MoE models (DeepSeek V3, Qwen3 235B, Mixtral) need special attention:
- **Active parameter count ≠ total parameter count.** DeepSeek V3 has 671B total but only 37B active per token. VRAM is sized by total, not active.
- **vLLM's MoE support has known issues** with very large models. DeepSeek V3 and R1 in particular have benefited from vLLM updates; check release notes before fighting setup.
- **Sometimes it's cheaper to use a hosted API.** Together, Fireworks, and DeepInfra all serve DeepSeek R1 for $3-7 per million tokens. Self-hosting on 8× H100 at $44/hr is only economical if you're driving >50 million tokens of inference, which is unusual at pilot scale.

When self-hosting an MoE giant doesn't fit the budget, use a hybrid approach: self-host the dense + small-MoE models for the reproducibility argument, use a hosted API for the giant MoEs with an explicit note in the methods section.

## 6. Quantization (FP8, MXFP4, AWQ)

Quantization reduces VRAM and speeds up inference at the cost of small accuracy losses. vLLM supports several formats:

- **BF16 (default).** No quantization. Highest fidelity. Use when VRAM fits.
- **FP8.** Modern (Hopper / H100+) GPUs have native FP8 support. ~1.9x smaller than BF16 with minimal quality loss. vLLM auto-detects FP8 if the model checkpoint is in that format (e.g., `Qwen/Qwen3-235B-A22B-Instruct-2507-tput`).
- **MXFP4.** OpenAI's GPT-OSS models ship in MXFP4. Requires recent vLLM (0.8+) and Hopper-or-newer GPUs.
- **AWQ / GPTQ.** Older 4-bit quantization formats. Smaller and faster than FP8 but more accuracy loss. Only use if VRAM is the binding constraint.

For pilot experiments where you care about result fidelity, prefer BF16 or FP8. Save aggressive quantization for production serving where throughput matters more than the last 1-2% of accuracy.

## 7. Keeping containers warm vs. cold-starting

vLLM containers take 30-180 seconds to cold-start (load weights, init CUDA graphs). For experiments that send many requests to the same model, you want the container to stay warm between requests. Two knobs control this:

- `scaledown_window=N`: after the last request, the container stays alive for N seconds before Modal scales it to zero. Default is short. Set to `5 * 60` or higher if you're sending requests every few minutes.
- `@modal.concurrent(max_inputs=N)`: how many requests one container handles in parallel. For a single vLLM container with batching, 4-8 is reasonable.

The right tradeoff depends on your access pattern. If you fan out 200 requests over 5 minutes, set `scaledown_window=5*60` and let one container handle them all. If you have one request every hour, the warm time is wasted GPU spend — better to cold-start each time.

For multi-model experiments, this matters a lot: 10 models × 30-second cold-start = 5 minutes of GPU time you can't recoup. Warming all containers up front (by sending dummy requests) and keeping them warm for the duration of the experiment is usually worth it.

## 8. When to NOT self-host

Self-hosting is the right call for:
- Reproducibility-load-bearing experiments where you need to document exact weights/sampling
- Models not available on hosted APIs
- High-volume serving where per-token API costs exceed GPU-hour costs

Use a hosted API instead when:
- The model is on a hosted API at reasonable cost AND your volume is low (most pilot experiments)
- You need a very large MoE model (V3, R1) and don't have multi-H100 budget
- You're prototyping and want zero infrastructure overhead

A reasonable hybrid pattern: self-host the dense models in your panel for the methods-section reproducibility claim, use a hosted API for the giants, document the split honestly.
