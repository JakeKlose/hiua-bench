# vLLM + Qwen 2.5 7B: `Qwen2Tokenizer has no attribute all_special_tokens_extended`

## Diagnosis

This is the classic vLLM / `transformers` version-pin mismatch.

Your image installs `vllm==0.8.5` but does **not** pin `transformers`. vLLM 0.8.5's `setup.py` declares the dependency as `transformers>=4.51.1` with **no upper bound**. When pip's resolver runs inside the Modal image build, it cheerfully grabs the newest `transformers` available on PyPI — which in 2026 is the 5.x line.

vLLM 0.8.5 was only ever tested against `transformers` 4.x. The 5.x release removed (or renamed) a number of tokenizer internals that vLLM still calls directly. One of those is `all_special_tokens_extended` on the slow tokenizer path used by Qwen2. When vLLM's `LLMEngine` warms up the tokenizer for `Qwen/Qwen2.5-7B-Instruct`, it reaches for that attribute and gets `AttributeError`. The crash happens during init, before a single token is generated, which matches your symptom ("crashes during tokenizer loading").

The same failure mode shows up for other tokenizers (Llama, Mistral) on the same vLLM/transformers combo — it's not Qwen-specific, you just happened to hit it on Qwen first.

A secondary issue worth flagging: `huggingface_hub` is also unpinned. The newer hub releases occasionally break vLLM's snapshot-download code paths. If you upper-bound `transformers` but leave `huggingface_hub` open, you may trade one dependency crash for another in a few weeks. Pin it now while you're already touching the image.

## Fix — corrected image definition

```python
vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04",
        add_python="3.11",
    )
    .pip_install(
        "vllm==0.8.5",
        "transformers>=4.51.1,<4.56",   # critical: keep transformers on the 4.x line vLLM was tested against
        "huggingface_hub>=0.24,<0.30",  # defensive upper bound on the hub client too
    )
)
```

That's the whole fix. Rebuild the image (Modal will rebuild automatically the next time you `modal run`), and the tokenizer will load cleanly.

## Why this keeps happening — and how to avoid the next one

The general rule for the vLLM + `transformers` + `torch` + `huggingface_hub` ecosystem: **always add upper bounds when you pin vLLM.** Open upper bounds will get you eventually. Every vLLM minor release was tested against a specific range of `transformers`; pip's resolver doesn't know that range and will happily pull something newer.

When you bump vLLM in the future:

1. Check the vLLM release notes for the version you're moving to.
2. Find the `transformers` range they tested against (usually mentioned in the changelog, otherwise inspect their `requirements.txt` on GitHub at that tag).
3. Pin both with explicit upper bounds in your `.pip_install(...)`.

If a Modal image build succeeds but the container crashes on first run with an `AttributeError` deep inside `transformers` or `tokenizers`, the version-pin mismatch should be your first hypothesis — not a bug in vLLM, not a corrupted weight download.

## Verification

After updating the image, re-run your smoke test. You should see vLLM's startup logs progress past the tokenizer-loading step (look for `Starting vLLM engine` → `Loading model weights` → `Capturing CUDA graphs`) and then accept a generation request.

If the smoke test still fails, the next things to check (in order):

1. Is the image actually rebuilt? Modal caches aggressively — confirm the build logs show `Collecting transformers<4.56` rather than skipping straight to "Using cached image".
2. Are weights laid out at `/weights/<org>/<name>/` with a real slash (not sanitized to `__`)? vLLM's loader runs the path through HF's repo-id validator and rejects sanitized paths with `HFValidationError`.
3. Is the GPU big enough? Qwen 2.5 7B at fp16 wants ~15 GB just for weights; an L40S (48 GB) or A100-40GB is comfortable, an L4 (24 GB) is tight once you add KV cache.
