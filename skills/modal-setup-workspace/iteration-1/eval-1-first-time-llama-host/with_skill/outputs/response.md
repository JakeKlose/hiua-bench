# Running Llama 3.1 8B Instruct on Modal — end to end

You're going to do this in five phases. Each phase is independent and verifiable, so if something breaks you'll know exactly which step to look at.

1. Install Modal and log in
2. Get a HuggingFace token and accept the Llama license
3. Create the Modal app file (`llama_app.py`)
4. Download the weights to Modal's cloud (one-time, ~10 min)
5. Run a smoke test, then call it from any Python script on your laptop

Expect ~$0.50–$2 of Modal credit burn end-to-end the first time. Modal gives new accounts ~$30 of free credit, which is plenty.

## Mental model before we start

There are two computers in this story:

- **Your laptop.** Runs the `modal` CLI and any Python scripts that *call* the model.
- **A Modal container in the cloud.** Spins up on demand with an L40S GPU attached. Loads the weights, runs vLLM, serves your request, then shuts down after 5 minutes of idle.

The Python file you'll write (`llama_app.py`) contains code for both. Functions decorated with `@app.function` or `@app.cls` run in the cloud. Functions decorated with `@app.local_entrypoint` run on your laptop. They share the source file but **nothing else** — no filesystems, no env vars, no Python packages.

Hold onto that and most of the weird errors stop being weird.

---

## Phase 1: Install Modal and authenticate

On your laptop, in whatever Python environment you want (a venv is nice but not required):

```bash
pip install modal
modal token new
```

`modal token new` opens a browser tab. Sign up or log in. When the tab closes, your local CLI is linked to your account. New accounts get free compute credit.

Sanity check by running their hello-world — save this as `hello.py`:

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

Then:

```bash
modal run hello.py
```

You should see `hello world from Modal!` after ~30 seconds (most of that is the first-ever container build). If that doesn't work, fix it before moving on — every later step assumes auth and the CLI are functioning.

---

## Phase 2: HuggingFace token + Llama license

Llama is a **gated model**. Meta requires you to accept their license on the HuggingFace website before HF will let you download the weights. Modal can't click the "accept" button for you.

1. Make a HuggingFace account if you don't have one: <https://huggingface.co/join>
2. Go to <https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct> and click "Agree and access repository". Approval is usually within minutes (sometimes ~1 hour).
3. Create an access token at <https://huggingface.co/settings/tokens>. Click "New token", give it a name like `modal-llama`, pick the **Read** role, and copy the token (it starts with `hf_...`). You only see it once.

Now tell Modal about the token by creating a Modal secret. A secret is just a key/value pair that gets injected as an environment variable inside your containers:

```bash
modal secret create hf-token HF_TOKEN=hf_your_token_here
```

The name `hf-token` is what we'll refer to from Python. The env var name inside the container will be `HF_TOKEN`. (If you mess up and need to overwrite it later, add `--force`.)

Quick check:

```bash
modal secret list
```

You should see `hf-token` in the list. If you don't, the download step will fail with a confusing 401 from HuggingFace, so verify now.

---

## Phase 3: The Modal app file

Save this as `llama_app.py`. I'll explain it after the code.

```python
"""
Llama 3.1 8B Instruct on Modal via vLLM.
"""

# IMPORTANT: do NOT add `from __future__ import annotations` here.
# Modal's parameter validator reads class type hints at decoration time
# and chokes if they've been turned into strings by the future import.

import modal

# ---------- Edit these if you want a different model / GPU ---------------
HF_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
GPU = "L40S"           # L40S handles 8B BF16 comfortably for ~$1.95/hr
DTYPE = "bfloat16"
MAX_MODEL_LEN = 8192
# -------------------------------------------------------------------------

WEIGHTS_VOL = modal.Volume.from_name("llm-weights", create_if_missing=True)
WEIGHTS_DIR = "/weights"


def weights_subdir(hf_id: str) -> str:
    # Keep the real `/` in the path. vLLM's loader runs the path through
    # a HuggingFace validator that insists the tail looks like 'org/repo'.
    return f"{WEIGHTS_DIR}/{hf_id}"


# Image for the vLLM serving container. Pinned versions are CRITICAL —
# vllm's setup.py allows transformers 5.x which removed methods vllm still
# calls, so we cap transformers below 4.56.
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
        # Stop HF from trying to validate our local /weights path against HF's repo URL format.
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
)

# Cheap CPU image just for downloading weights — no need to spin up a GPU
# while waiting for HuggingFace to send bytes.
download_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("llama-8b")


@app.function(
    image=download_image,
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=60 * 60,
    secrets=[modal.Secret.from_name("hf-token")],
)
def download_weights(hf_id: str = HF_MODEL_ID) -> str:
    from huggingface_hub import snapshot_download
    target = weights_subdir(hf_id)
    print(f"[download] {hf_id} -> {target}")
    snapshot_download(
        repo_id=hf_id,
        local_dir=target,
        max_workers=8,
        allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.model", "*.txt"],
    )
    WEIGHTS_VOL.commit()
    print(f"[download] {hf_id} done")
    return target


@app.cls(
    image=vllm_image,
    gpu=GPU,
    volumes={WEIGHTS_DIR: WEIGHTS_VOL},
    timeout=20 * 60,
    scaledown_window=5 * 60,
)
@modal.concurrent(max_inputs=8)
class Llama:
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
    def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        seed: int = 0,
    ) -> str:
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
```

### What each piece is doing

- **`modal.Volume`** — persistent disk in the cloud. We download the ~16 GB of Llama weights into it once. Every future GPU container mounts the volume and reads weights from disk instead of re-downloading from HuggingFace.
- **`vllm_image`** — the container image that gets built (once, cached forever) the first time you run anything. CUDA + Python + vLLM + transformers. The version pins matter — vLLM is fussy and pip's resolver will happily pick incompatible versions if you don't constrain it.
- **`download_image`** — a separate, much smaller image used only for the downloader. No GPU, no vLLM. This saves money: at ~$2/hr for an L40S vs cents/hr for a CPU container, you do NOT want a GPU spinning while HuggingFace dribbles weights to you.
- **`download_weights`** — the downloader function. Runs once per model, on a CPU container, with your HF token attached so it can pull the gated Llama weights.
- **`Llama` class** — the actual inference server. The `@modal.enter()` method runs once when the container boots; that's where vLLM loads weights into GPU memory. The `@modal.method()` is what you call from outside.
- **`scaledown_window=5*60`** — after your last request, the container stays warm for 5 minutes before Modal shuts it down. Subsequent calls within that window are fast (~1–2 s). Cold-start is 30–90 s.
- **`@modal.concurrent(max_inputs=8)`** — vLLM batches requests internally, so one container can handle 8 in-flight requests at once.
- **`smoke_test`** — runs on your laptop, makes one remote call to verify everything's wired up.

### Why the comments insist on certain things

- **No `from __future__ import annotations`.** If you add that, your `hf_model_id: str = modal.parameter(...)` annotations become strings at runtime, and Modal's validator raises `AttributeError: 'str' object has no attribute '__name__'`. Subtle and confusing.
- **`@app.cls` at module scope.** If you ever try to wrap `Llama` inside a function (e.g. a factory like `def make_runner(gpu): @app.cls(gpu=gpu) class R: ...`), Modal raises `LocalFunctionError`. It needs to see the class at import time.
- **The `transformers` upper bound.** Without `<4.56`, pip picks transformers 5.x → vLLM 0.8.5 crashes with `Qwen2Tokenizer has no attribute all_special_tokens_extended`. This is the single most common gotcha in the vLLM-on-Modal ecosystem.
- **`HF_HUB_OFFLINE=1`.** Once we've cached weights locally, we don't want HF helpers reaching out to huggingface.co and complaining that `/weights/meta-llama/Llama-3.1-8B-Instruct` doesn't look like a canonical HF repo URL.

---

## Phase 4: Download the weights (one-time)

From your laptop, in the directory containing `llama_app.py`:

```bash
modal run llama_app.py::download_weights
```

What happens:

1. Modal uploads your source file.
2. Modal builds `download_image` (a couple minutes the first time, cached after).
3. A CPU container starts, mounts the volume, pulls ~16 GB from HuggingFace at ~300 MB/s, commits the volume.
4. Takes roughly 5–10 minutes total.

If you see a 401 / GatedRepoError, the most likely cause is that you haven't accepted the Llama license yet on the HF website, or the token doesn't have read access to gated repos.

Verify the weights landed:

```bash
modal volume ls llm-weights meta-llama/Llama-3.1-8B-Instruct
```

You should see a bunch of `.safetensors`, `tokenizer.json`, `config.json`, etc.

---

## Phase 5: Smoke test, then call from your laptop

The smoke test:

```bash
modal run llama_app.py::smoke_test
```

What happens:

1. Modal builds `vllm_image` (the heavy one — takes 5–10 min the FIRST time, then it's cached forever).
2. An L40S container spins up, mounts the volume, vLLM loads the weights into GPU RAM and warms CUDA graphs (~60 s).
3. vLLM runs your one prompt (~1 s).
4. You see `OUTPUT: 'HELLO FROM LLAMA'` printed.
5. The container sits idle for 5 minutes, then shuts down.

First-call total: roughly 3–8 minutes. Subsequent calls within the 5-minute warm window: ~1–2 seconds.

### Calling it from any Python script

Now the actual point of the exercise — calling Llama from a regular script on your laptop without using `modal run`. Save this as `call_llama.py`:

```python
import modal

# Look up the class by (app name, class name) — these strings must match
# `modal.App("llama-8b")` and `class Llama:` in llama_app.py.
Llama = modal.Cls.from_name("llama-8b", "Llama")


def ask(system: str, user: str, **kwargs) -> str:
    runner = Llama()
    return runner.generate.remote(system=system, user=user, **kwargs)


if __name__ == "__main__":
    answer = ask(
        system="You are a helpful tutor for graduate-level ML students.",
        user="In two sentences, what is the difference between BF16 and FP16 for LLM inference?",
        temperature=0.2,
        max_tokens=256,
    )
    print(answer)
```

For `modal.Cls.from_name` to work, the app needs to have been seen by Modal at least once — which `modal run llama_app.py::smoke_test` already accomplished. Run it:

```bash
python call_llama.py
```

You can now drop those three lines (`import modal`, `Llama = modal.Cls.from_name(...)`, `runner.generate.remote(...)`) into Jupyter, a CLI tool, a Flask handler — anywhere you can run Python.

---

## Useful CLI commands for day-to-day

```bash
modal app list                          # see running apps
modal app logs <app-id>                 # tail logs from a running app
modal app stop <app-id>                 # force-stop an app
modal volume ls llm-weights             # see what's in your weights volume
modal secret list                       # see your secrets
modal run --detach llama_app.py::foo    # run detached (survives laptop sleep / Ctrl-C)
```

The `--detach` flag is important if you ever kick off a longer job — without it, closing your laptop or losing WiFi will signal Modal to kill the run.

---

## Cost expectations

- L40S GPU: **~$1.95/hr** while a container is alive (i.e. actively serving or within the 5-minute scaledown window).
- CPU container for downloads: cents/hr.
- Storage in volumes: free up to ~50 GB on the free tier.

For exploratory use, you'll burn through pennies. If you forget to ever stop calling the model and the container scales up and stays warm forever, you'd see ~$45/day worst case — but `scaledown_window=5*60` plus Modal's autoscaling means in practice you only pay for the seconds your code is actively using GPU plus the warm-window tail.

---

## Common first-time errors and what they mean

| Error | Cause | Fix |
|-------|-------|-----|
| `Secret 'hf-token' not found in environment 'main'` | You haven't created the secret yet, or named it differently. | `modal secret create hf-token HF_TOKEN=hf_xxx` |
| `GatedRepoError` / 401 from HF | Haven't accepted Llama license on HF website, or token lacks read access. | Visit the model page in a browser, click Agree. |
| `AttributeError: 'str' object has no attribute '__name__'` | You added `from __future__ import annotations`. | Remove that import. |
| `LocalFunctionError: Modal can only import functions defined in global scope` | You wrapped `@app.cls` inside a function. | Move the class to module scope. |
| `Qwen2Tokenizer has no attribute all_special_tokens_extended` (or similar transformers-version error) | Pip resolved transformers to a too-new major. | Add `<4.56` upper bound on transformers in the image. |
| `HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'` | You sanitized the `/` out of the local weights path. | Keep the slash: `/weights/meta-llama/Llama-3.1-8B-Instruct`. |
| `FileNotFoundError: /root/foo.json` in a Modal function | The container can't see your laptop's filesystem. | Read the file in `@app.local_entrypoint` and pass the parsed data as an argument. |
| `App state is APP_STATE_STOPPED` mid-run | Your laptop disconnected and Modal interpreted it as a cancel. | Use `modal run --detach` for anything longer than a few minutes. |

If you hit something not on that list, the trick is to look at which layer the error comes from (`modal.*`, `vllm.*`, `huggingface_hub.*`, `transformers.*`) and check that layer's release notes — most weirdness is one of those four moving incompatibly with another.

---

## What you've got at the end of this

- A Modal app called `llama-8b` that hosts Llama 3.1 8B Instruct on an L40S behind vLLM.
- A persistent `llm-weights` volume containing the weights — downloaded once, reused forever.
- A Python interface (`call_llama.py`) you can import from anywhere.
- Total monthly cost while not actively calling it: **$0** (the container auto-scales to zero).

If you ever want to try a bigger model (say 70B), the same file works — change `HF_MODEL_ID` to `meta-llama/Llama-3.3-70B-Instruct`, change `GPU` to `"H100:2"`, re-run `download_weights`, then `smoke_test`. The class structure stays the same.
