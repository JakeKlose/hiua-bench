# Diagnosing `Qwen2Tokenizer has no attribute all_special_tokens_extended` on Modal + vLLM

## TL;DR

This is a **`transformers` / `vllm` version mismatch**, not a Qwen-specific bug. `vllm==0.8.5` was built against an older `transformers` API. When pip resolves the dependency tree on the Modal image, `huggingface_hub` (and vLLM's own loose pins) pull in a newer `transformers` (>= 4.46) whose `PreTrainedTokenizerFast` / `Qwen2Tokenizer` surface no longer exposes `all_special_tokens_extended` in the way vLLM 0.8.5's tokenizer wrapper expects. vLLM crashes inside `get_tokenizer()` before the engine ever starts.

The fix is to pin a compatible `transformers` (and `tokenizers`) version into the image, and ideally upgrade vLLM to a version whose Qwen2 support is current.

---

## What's actually going wrong

1. `vllm==0.8.5` ships with `transformers>=4.45.0` as a *lower* bound but no firm upper bound.
2. `huggingface_hub` (unpinned in your `pip_install`) resolves to the latest, which in turn lets pip resolve `transformers` to >=4.46 / 4.47.
3. In newer `transformers`, `Qwen2Tokenizer` (slow) and `Qwen2TokenizerFast` had internals refactored. vLLM 0.8.5's `vllm/transformers_utils/tokenizer.py` calls `tokenizer.all_special_tokens_extended` on the returned object, but the slow `Qwen2Tokenizer` no longer carries that attribute directly (it was on `PreTrainedTokenizerBase` and got moved/renamed in the refactor).
4. Result: `AttributeError: Qwen2Tokenizer has no attribute all_special_tokens_extended` during `LLM(...)` / `AsyncLLMEngine.from_engine_args(...)` init, before any inference runs.

A secondary aggravator: when you let `huggingface_hub` float, it often pulls a version that requires a `tokenizers` >= 0.20, which silently upgrades `tokenizers` too. vLLM 0.8.5 was tested against `tokenizers==0.19.x`. That combination is where this specific `AttributeError` shows up most often.

You can confirm the diagnosis quickly by exec'ing into the built image:

```bash
modal shell <your_app>::<your_fn>
python -c "import transformers, tokenizers, vllm; print(transformers.__version__, tokenizers.__version__, vllm.__version__)"
```

You'll almost certainly see `transformers >= 4.46` paired with `vllm 0.8.5`.

---

## The fix

You have two good options. **Option A** (recommended) upgrades vLLM to a version that natively supports current `transformers` + Qwen2.5. **Option B** keeps vLLM 0.8.5 but pins the transformers stack it was built against.

### Option A (recommended): upgrade vLLM

Qwen2.5-7B is well-supported on recent vLLM (0.6.x is the original Qwen2.5 line; 0.8.x / 0.9.x continue support). Use a vLLM release that pins a known-good transformers internally, and pin transformers yourself for reproducibility:

```python
import modal

vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04",
        add_python="3.11",
    )
    .pip_install(
        "vllm==0.6.3.post1",        # known-good with Qwen2.5-7B
        "transformers==4.45.2",     # matches vllm 0.6.3's tested pin
        "tokenizers==0.20.3",
        "huggingface_hub==0.25.2",
        "torch==2.4.0",             # vllm 0.6.3 wants torch 2.4.x
    )
    .env({"VLLM_WORKER_MULTIPROC_METHOD": "spawn"})
)
```

If you want to stay on the 0.8.x line, this combination is known to work:

```python
.pip_install(
    "vllm==0.8.5.post1",
    "transformers==4.46.3",
    "tokenizers==0.20.3",
    "huggingface_hub==0.26.2",
)
```

### Option B: stay on vLLM 0.8.5, pin the rest

If you must keep `vllm==0.8.5` exactly:

```python
vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04",
        add_python="3.11",
    )
    .pip_install(
        "vllm==0.8.5",
        "transformers==4.45.2",
        "tokenizers==0.19.1",
        "huggingface_hub==0.24.7",
    )
)
```

The key is pinning `transformers`, `tokenizers`, AND `huggingface_hub` together. If you only pin one, pip will happily upgrade the others to satisfy transitive constraints and you'll land back in the same broken state.

---

## A few other things worth fixing while you're in the image

1. **CUDA base image.** vLLM only needs the *runtime* libs, not the full CUDA toolchain. Using `-devel` makes the image ~3 GB larger and slows cold starts. Switch to `nvidia/cuda:12.4.1-runtime-ubuntu22.04` unless you're compiling kernels.
2. **Flash-attention.** vLLM 0.6+/0.8+ wheels bundle FA2 for most common GPU/CUDA combos, so you usually don't need to install it separately. If you do, pin it explicitly (`flash-attn==2.6.3` for the 0.6.3 era).
3. **HF cache on a Modal Volume.** Add a `modal.Volume` mounted at `/root/.cache/huggingface` so the 15 GB Qwen2.5-7B weights download once, not on every cold start.
4. **GPU memory headroom.** Qwen2.5-7B in fp16 fits on a single A10G (24 GB), but with default `gpu_memory_utilization=0.9` and a long context you can OOM. Start the engine with `max_model_len=8192, gpu_memory_utilization=0.85` and tune up.

### Full revised module sketch

```python
import modal

vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .pip_install(
        "vllm==0.6.3.post1",
        "transformers==4.45.2",
        "tokenizers==0.20.3",
        "huggingface_hub==0.25.2",
        "torch==2.4.0",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("qwen25-7b")
hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

@app.cls(
    image=vllm_image,
    gpu="A10G",
    volumes={"/root/.cache/huggingface": hf_cache},
    timeout=60 * 30,
    scaledown_window=60 * 5,
)
class QwenServer:
    @modal.enter()
    def load(self):
        from vllm import LLM
        self.llm = LLM(
            model="Qwen/Qwen2.5-7B-Instruct",
            max_model_len=8192,
            gpu_memory_utilization=0.85,
            dtype="bfloat16",
        )

    @modal.method()
    def generate(self, prompt: str) -> str:
        from vllm import SamplingParams
        out = self.llm.generate(
            [prompt],
            SamplingParams(temperature=0.7, max_tokens=512),
        )
        return out[0].outputs[0].text
```

---

## How to verify the fix

After rebuilding, run a one-shot smoke test:

```python
@app.function(image=vllm_image)
def smoke():
    import transformers, tokenizers, vllm
    print("vllm", vllm.__version__)
    print("transformers", transformers.__version__)
    print("tokenizers", tokenizers.__version__)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
    print("has attr:", hasattr(tok, "all_special_tokens_extended"))
    print(tok.all_special_tokens_extended[:3])
```

If `has attr: True` prints, the tokenizer surface vLLM expects is intact and `LLM(...)` will initialize cleanly.

---

## Summary

- **Root cause:** unpinned dependencies caused pip to install a `transformers` version newer than what `vllm==0.8.5` was tested against; the `Qwen2Tokenizer` surface vLLM relies on (`all_special_tokens_extended`) is no longer present in the form it expects.
- **Fix:** pin `transformers`, `tokenizers`, and `huggingface_hub` together with your `vllm` version. Easiest path is `vllm==0.6.3.post1` + `transformers==4.45.2` + `tokenizers==0.20.3` + `huggingface_hub==0.25.2`.
- **Bonus cleanups:** switch base image to `cuda:12.4.1-runtime`, cache HF weights on a Modal Volume, lower `gpu_memory_utilization` to avoid OOM.
