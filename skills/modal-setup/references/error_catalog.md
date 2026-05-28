# Modal error catalog

A grab-bag of Modal errors we've seen, with diagnosis steps. The SKILL.md body covers the most common ones; this is the long tail.

For each error, the format is: symptom → cause → fix.

## Build-time errors (before any function runs)

### `Secret 'foo-api-key' not found in environment 'main'`
Modal validates every secret in `SECRETS = [modal.Secret.from_name(...)]` at app-build time. Listing a secret you don't have crashes the app even if no function uses it.
**Fix:** Only list secrets you actually have. To overwrite an existing secret rather than create a new one, add `--force` to `modal secret create`.

### `Secret 'foo-api-key' already exists in environment 'main'`
`modal secret create` won't overwrite without `--force`.
**Fix:** `modal secret create foo-api-key FOO_KEY=value --force` or `modal secret delete foo-api-key` then re-create.

### `LocalFunctionError: Modal can only import functions defined in global scope`
You tried to wrap `@app.cls` or `@app.function` inside another function (factory pattern).
**Fix:** Move the decorated class/function to module scope. Duplicate it if you need variants for different GPU shapes.

### `AttributeError: 'str' object has no attribute '__name__'` from modal.parameter()
You have `from __future__ import annotations` at the top of a file with a class using `modal.parameter()`. Modal reads annotations as type objects, not strings.
**Fix:** Remove the `from __future__ import annotations` line.

### `InvalidError: No class parameter encoder implemented for type X`
`modal.parameter()` only supports basic types: `str`, `int`, `float`, `bool`, `bytes`. You used something fancier (Optional, custom dataclass, etc.).
**Fix:** Encode the value as a plain string or int, decode inside the class body.

## Container runtime errors

### `FileNotFoundError: [Errno 2] No such file or directory: '/root/something'`
The container can't see your laptop's filesystem. The file exists locally but not in the container.
**Fix:** Either bake the file into the image (`.add_local_file()`, `.add_local_dir()`) or load it locally in your entrypoint and pass the data as a function argument:
```python
@app.local_entrypoint()
def main():
    data = json.loads(Path("items.json").read_text())   # runs LOCALLY
    result = my_modal_function.remote(data=data)        # data ships over the wire
```

### `ImportError: No module named 'X'`
The package isn't in your image. Modal images are minimal — they only have what you `.pip_install(...)`.
**Fix:** Add the package to the image definition:
```python
image = modal.Image.debian_slim().pip_install("requests", "pandas")
```

### `huggingface_hub.errors.HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'`
You loaded weights from a path that doesn't look like a HF repo ID. Most commonly: you sanitized `/` in the model org/name to `__` when saving to a volume.
**Fix:** Keep the real `/` in the weights path: `/weights/Qwen/Qwen2.5-7B-Instruct/` not `/weights/Qwen__Qwen2.5-7B-Instruct/`.

## Dependency / version errors

### `Cannot install transformers==X and vllm==Y because these package versions have conflicting dependencies`
You over-pinned. vLLM has its own transformers requirement; your explicit pin conflicts.
**Fix:** Either bump one to match the other's range, or remove your explicit pin and let vLLM's range win.

### `AttributeError: Qwen2Tokenizer has no attribute all_special_tokens_extended` (or similar tokenizer attribute errors)
transformers 5.x removed methods that vLLM still calls. vLLM's `transformers>=4.51.1` requirement has no upper bound, so pip picks the latest 5.x.
**Fix:** Add an upper bound: `transformers>=4.51.1,<4.56`.

### vLLM `OSError: CUDA driver version is insufficient for CUDA runtime version`
The CUDA version in your image is newer than what Modal's GPU drivers support.
**Fix:** Use an older CUDA base image (e.g., `nvidia/cuda:12.4.0-devel-ubuntu22.04`).

### `ImportError: libcudnn.so.X: cannot open shared object file`
vLLM (or torch) was built against a different cuDNN version than what's in your image.
**Fix:** Let vLLM's pip install pull its own torch + cuDNN bundle (don't separately pin torch). The wheel pulls compatible NVIDIA library wheels automatically.

## Execution / lifecycle errors

### `Stopping app - local client disconnected. Use modal run --detach`
Your laptop disconnected mid-run (sleep, network blip, Ctrl-C). Modal treats client disconnect as a cancel signal.
**Fix:** Re-launch with `modal run --detach`. Track progress at the dashboard URL or via `modal app logs <app-id>`.

### `Runner interrupted due to worker preemption`
Modal preempted your container to reclaim capacity. Modal sometimes does this with serverless functions.
**Fix:** Either re-run (you may not be preempted again), or restructure the orchestrator to flush/commit per trial so partial progress is durable, OR use a Modal cluster/deployment with stronger guarantees if you're paying for it.

### `App state is APP_STATE_STOPPED`
You're trying to call a function in an app that's already shut down.
**Fix:** Re-launch the app (`modal run` it again). Apps don't persist across CLI invocations unless they're deployed via `modal deploy`.

### `modal.exception.OutputExpiredError: The output of this call has expired`
You held a `.spawn()` or async function call result longer than Modal's retention period.
**Fix:** Process function results promptly; don't sit on them. For very-long results, write to a volume instead of returning them.

## Modal v1 deprecation warnings (will become errors in v2)

These all still WORK but emit warnings:

- `container_idle_timeout` → `scaledown_window`
- `allow_concurrent_inputs=N` (on @app.cls) → `@modal.concurrent(max_inputs=N)` (separate decorator)
- `keep_warm=N` → `min_containers=N`
- `concurrency_limit=N` → `max_containers=N`

When you see these warnings, the fix is to rename and continue. Don't ignore them — they will break.

## Cost / billing errors

### "I just spent $X on a Modal run by accident"
Most surprise-spend incidents are one of:
- A container that was supposed to scale to zero but didn't (forgot to set `scaledown_window`, or hit `min_containers > 0`)
- A large model on an expensive GPU that ran much longer than expected (didn't estimate cost before launching)
- A bug that caused infinite retries (always set `retries=2` or `retries=3`, never leave unbounded)

**Prevention:** Set up Modal billing alerts in the dashboard. Always write a cost estimator and confirm spend before any multi-hour multi-GPU run.

## Diagnosis checklist

When something fails on Modal and you're not sure where to look:

1. **Read the full traceback, not just the last line.** Modal wraps errors and the root cause is often 3-5 frames up.
2. **Check which side the error is on.** Local CLI errors look different from in-container errors. The traceback header tells you (`File "/root/..."` = container; `File "/Users/..."` or `/opt/anaconda/...` = local).
3. **Check the Modal dashboard.** Failed runs are listed with full logs. Sometimes the local CLI shows only the tail; the dashboard shows everything.
4. **Try a smaller version.** Most Modal errors reproduce on a 1-second smoke test. Don't try to debug a 4-hour run; debug a 5-second one.
5. **Check Modal's status page** (status.modal.com) before assuming the bug is yours. Modal has rare outages and capacity issues.
