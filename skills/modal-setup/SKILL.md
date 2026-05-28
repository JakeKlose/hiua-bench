---
name: modal-setup
description: Help the user set up, debug, or build a Modal app from scratch — including first-time CLI install, secrets, volumes, and running their first function on Modal's serverless GPUs or CPUs. Use this skill whenever the user mentions Modal, modal.com, serverless GPU, vLLM hosting on Modal, "I want to run X on a cloud GPU", running an experiment that needs to fan out across containers, or asks about errors like LocalFunctionError, secret not found, FileNotFoundError inside a container, vLLM dependency conflicts, or pip resolver issues with transformers/vLLM. Also trigger if the user is debugging a Modal run that crashed mid-flight, or asks how to keep a long-running Modal job alive after their laptop sleeps. Be proactive — even if they don't explicitly say "Modal", reach for this skill if their problem looks like one of the well-known Modal first-time setup pitfalls (image rebuild surprises, container path mismatches, secret validation timing, vLLM/transformers version pinning, the @app.cls scope rule, or class parameter type validation).
---

# Modal Setup

A guide to setting up Modal — the serverless GPU/CPU platform — from a cold start, plus solutions to the painful errors that almost everyone hits the first time.

## Mental model: what Modal actually is

Modal is a serverless platform for Python. You write Python functions, decorate them with `@app.function(...)` or `@app.cls(...)`, and Modal runs them in containers on its infrastructure. The killer feature is that GPUs are first-class: you say `gpu="H100"` and a container with an H100 spins up for the duration of the call.

The mental model that helps with debugging: **your local laptop and the Modal container are two completely separate computers**. They share Python source code (Modal ships the relevant files when the app builds), but they do not share filesystem state, environment variables, or installed packages. Whenever something works locally but fails on Modal — or vice versa — start by asking "which computer is this code running on, and what does THAT computer have access to?"

## When to use this skill

Use it for:
- A user installing Modal for the first time and needing to get to "hello world"
- A user who has Modal working but is hitting one of the well-known errors below
- A user asking how to host their own LLM on Modal via vLLM
- A user designing a Modal app for an experiment that fans out across many containers
- Translating a "this works on my laptop" Python script into a Modal app

Do NOT use it for:
- Generic Python questions that have nothing to do with Modal
- Deploying to other serverless platforms (Lambda, Cloud Run, RunPod). The lessons here are Modal-specific even when the concepts are similar.

## Onboarding flow for a first-time Modal user

If the user is starting fresh, walk them through these in order. Don't skip ahead — each step depends on the previous one working.

### Step 1: Install the CLI and authenticate

```bash
pip install modal
modal token new
```

The second command opens a browser window asking them to log in (or sign up). After that, their local Modal CLI is linked to an account. They'll have a small free tier of compute credits to start.

### Step 2: First function — verify the install works

Have them save this as `hello.py`:

```python
import modal
app = modal.App("hello")

@app.function()
def greet(name: str) -> str:
    return f"hello {name} from Modal!"

@app.local_entrypoint()
def main():
    print(greet.remote("world"))
```

Then run it:

```bash
modal run hello.py
```

If they see `hello world from Modal!`, the install is good. If they see anything else, debug that before doing anything more complex.

### Step 3: Add a secret

Most real Modal apps need API keys. Secrets in Modal are key/value pairs that get injected as environment variables inside the container. Create one with:

```bash
modal secret create my-api-key MY_KEY=actual-value-here
```

Then use it in code:

```python
@app.function(secrets=[modal.Secret.from_name("my-api-key")])
def call_api():
    import os
    key = os.environ["MY_KEY"]
    # ...
```

**Important gotcha — see the "Common errors" section** about secret validation timing.

### Step 4: Add a volume (for files that should persist across runs)

Containers are ephemeral — anything written to the local filesystem disappears when the container exits. To persist data (model weights, downloaded datasets, output JSONL), use a volume:

```python
results_vol = modal.Volume.from_name("my-results", create_if_missing=True)

@app.function(volumes={"/vol": results_vol})
def write_output(data: str):
    with open("/vol/output.txt", "w") as f:
        f.write(data)
    results_vol.commit()   # makes the write visible to future runs
```

Pull files back to your laptop with:

```bash
modal volume ls my-results
modal volume get my-results output.txt .
```

### Step 5: Add a GPU

If they need a GPU (common for LLMs, training, image gen):

```python
@app.function(gpu="H100", image=modal.Image.debian_slim().pip_install("torch"))
def gpu_thing():
    import torch
    print(torch.cuda.is_available())
```

Common GPU options as of mid-2026: `L40S` ($1.95/hr), `A100-40GB` ($2.10/hr), `A100-80GB` ($3.30/hr), `H100` ($5.50/hr), `H200` ($6.50/hr). For multi-GPU, write `gpu="H100:2"` etc. See Modal's pricing page for current rates.

## Common errors and how to fix them

These are the errors I've seen people hit most often. For each, the fix matters less than understanding **why** it happens — knowing the cause lets you solve variants you haven't seen yet.

### "Secret 'foo-api-key' not found in environment 'main'"

**Cause:** Modal resolves every secret in your app's SECRETS list at app-build time, before any function runs. Listing a secret you don't actually have crashes the entire app even if no function ever uses it.

**Fix:** Don't be defensive with secrets. Only list the ones you have. If you want to support multiple providers, comment the unused ones out:

```python
SECRETS = [
    modal.Secret.from_name("groq-api-key"),
    # modal.Secret.from_name("anthropic-api-key"),   # uncomment when you have one
    # modal.Secret.from_name("openai-api-key"),
]
```

To overwrite an existing secret (instead of creating a new one), add `--force`:

```bash
modal secret create my-key MY_KEY=new-value --force
```

### "FileNotFoundError: [Errno 2] No such file or directory: '/root/items.json'"

**Cause:** Your code is running inside a Modal container, which can't see your laptop's filesystem. The file exists at `/Users/you/project/items.json` locally, but the container is a fresh Linux box that has none of those files.

**Fix:** Either (a) bake the file into the container image, or (b) load the file locally in your `@app.local_entrypoint` and pass the parsed data as a function argument:

```python
@app.local_entrypoint()
def main(path: str = "items.json"):
    # runs LOCALLY on your laptop
    data = json.loads(Path(path).read_text())
    # send the parsed data to Modal — gets serialized over the wire
    result = my_modal_function.remote(data=data)
```

Option (a) is cleaner for files that change rarely. Option (b) is better for files you edit between runs.

### "LocalFunctionError: Modal can only import functions defined in global scope"

**Cause:** You tried to define a Modal class or function inside another function. Modal serializes your decorators at app-build time and needs them at module scope so they can be referenced by name. Factory-function patterns that try to dynamically create `@app.cls` classes will fail.

**Fix:** Write each class explicitly at module scope. If you have N variants (e.g., one per GPU type), define N classes. It's more verbose than a factory but it's the only way that works:

```python
# Don't do this:
def make_runner(gpu): ...   # @app.cls inside fails

# Do this:
@app.cls(gpu="H100")
class RunnerH100: ...

@app.cls(gpu="A100-80GB")
class RunnerA100: ...
```

### "AttributeError: 'str' object has no attribute '__name__'" (from modal.parameter())

**Cause:** You wrote `from __future__ import annotations` at the top of a file that contains a class using `modal.parameter()`. Future-annotations makes Python store all type hints as strings at runtime; Modal's parameter validator reads them at decoration time and needs real type objects.

**Fix:** Remove the `from __future__ import annotations` line from that file. (You can still use modern type syntax like `list[str]` on Python 3.9+ without the import.)

### vLLM dependency hell — "Qwen2Tokenizer has no attribute all_special_tokens_extended"

**Cause:** vLLM's setup.py says `transformers>=4.51.1` with no upper bound. Pip's resolver happily picks the latest transformers (5.x in 2026), but vLLM was only ever tested against 4.x. The newer transformers removed methods that vLLM still calls.

**Fix:** Always add an upper bound when pinning vLLM:

```python
.pip_install(
    "vllm==0.8.5",
    "transformers>=4.51.1,<4.56",   # critical
)
```

The same pattern applies to any ML library that depends on `transformers`, `torch`, or `huggingface_hub`. Open upper bounds get you bit eventually.

### vLLM: "HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'"

**Cause:** You downloaded weights to a path like `/weights/Qwen__Qwen2.5-7B-Instruct/` (using underscores to avoid the slash), but vLLM's loader runs the path through HuggingFace's `try_to_load_from_cache` helper, which insists the path tail looks like a valid HF repo ID.

**Fix:** Lay out weights at `/weights/<org>/<name>/` with a real slash. Don't sanitize the slash to anything else.

```python
def weights_subdir(hf_id: str) -> str:
    return f"/weights/{hf_id}"   # keep the slash
```

### "container_idle_timeout is deprecated" / "allow_concurrent_inputs is deprecated"

**Cause:** Modal v1 renamed several decorator arguments. Both still work but emit deprecation warnings.

**Fix:**
- `container_idle_timeout=...` → `scaledown_window=...`
- `allow_concurrent_inputs=N` → decorate the class with `@modal.concurrent(max_inputs=N)` separately

### "App state is APP_STATE_STOPPED" or "local client disconnected"

**Cause:** You ran a long Modal job with `modal run` (not `--detach`). Modal interprets local client disconnect as a cancel signal and kills the workers. Closing your laptop, losing WiFi, or hitting Ctrl-C all qualify.

**Fix:** For any run expected to take more than a few minutes, use `--detach`:

```bash
modal run --detach my_app.py::long_running_function
```

This frees Modal to keep running on its infrastructure regardless of your local terminal. Track progress at the dashboard URL Modal prints when the run starts. Re-attach to live logs anytime with `modal app logs <app-id>`.

## A working template

For the most common case — hosting a single open-weights LLM via vLLM — see `scripts/vllm_app_template.py`. It bakes in every lesson above (pinned versions, module-scope classes, correct path layout, scaledown_window, no future annotations) and is meant to be copied and modified.

To use it: copy the file to the user's project, change `HF_MODEL_ID` and `GPU` at the top, run `modal run vllm_app_template.py::download_weights` once to cache the weights, then `modal run vllm_app_template.py::smoke_test` to verify serving works.

## Patterns for larger Modal apps

Once the basics work, the most common scaling patterns are:

**Fan-out via .map().** If you have N independent jobs (trials, files to process, prompts to send), use `my_function.map(payloads)` to run them in parallel containers. Modal handles container spin-up and result collection. Concurrency is capped by `max_containers` on the function decorator — set this based on the rate limits of whatever upstream service the job calls.

**Per-provider concurrency.** When fanning out to many different APIs (each with its own rate limit), give each provider its own Modal function with its own `max_containers` cap, rather than one shared function. This stops one slow/rate-limited provider from blocking others.

**Resilience: flush per-trial.** If you write results to a volume from inside a long-running orchestrator, flush + commit after every trial (not every 50), so preemption costs you at most one trial rather than 49. Volume commits are cheap compared to losing minutes of work.

**Cost estimation before launch.** Before running a multi-hour multi-model job, write a dry-run function that computes expected GPU-hours per model and total $ spend. Confirm with the user before the real launch. This costs nothing and prevents bill surprises.

## Quick reference: Modal CLI commands

- `modal token new` — first-time auth
- `modal secret create NAME KEY=value [--force]` — create/overwrite a secret
- `modal secret list` — list your secrets
- `modal volume ls VOL_NAME [path]` — list files in a volume
- `modal volume get VOL_NAME path/in/volume local/path` — download from a volume
- `modal volume rm VOL_NAME path -r` — delete a path in a volume
- `modal run path.py::entrypoint [--arg val]` — run an entrypoint (blocks)
- `modal run --detach path.py::entrypoint` — run detached (survives disconnect)
- `modal app list` — list running apps
- `modal app logs APP_ID` — stream logs from a (possibly detached) app
- `modal app stop APP_ID` — kill a running app

## When to read references/

- `references/vllm_deep_dive.md` — Full walkthrough of self-hosting an LLM on Modal via vLLM, including weight caching, GPU class patterns, and multi-GPU MoE serving. Read this if the user is specifically setting up vLLM and needs more than the template provides.
- `references/error_catalog.md` — Extended catalog of Modal errors with diagnosis steps. Read this if the user hits an error not covered in the SKILL.md body.

## A note on dependency hell

The Modal + vLLM + transformers + torch ecosystem moves fast. The version pins that work today may not work in six months. When helping a user, treat any specific version number as best-known-good rather than canonical. If the user is running into version conflicts, the first move is to find the pinned-version combination that vLLM's release notes recommend for their target model — then enforce upper bounds defensively.
