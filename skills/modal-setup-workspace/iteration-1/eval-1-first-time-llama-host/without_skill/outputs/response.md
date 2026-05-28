# Running Llama 3.1 8B Instruct on Modal — End-to-End

This walkthrough gets you from zero to a working `python script.py` on your laptop that calls a Llama 3.1 8B Instruct model running on a cloud GPU. Total setup time is ~30 minutes (most of which is waiting for the model weights to download into the container image once).

## How the pieces fit together

- **Modal** runs your Python functions in containers on its GPU fleet. You write a normal Python file, decorate a class/function with `@app.cls(gpu="A10G", ...)`, and `modal deploy` ships it. From your laptop, you import a tiny stub and call `.remote(...)` — Modal handles auth, scheduling, GPU provisioning, and cold-start lifecycle.
- **vLLM** is the inference engine that actually loads the model and serves tokens. It's much faster than vanilla `transformers.generate` and is the standard choice for self-hosting open models.
- **Hugging Face** is where the weights live. Llama 3.1 is gated, so you'll request access and create an access token; Modal stores that token as a Secret and uses it to download the weights once at image-build time.

The two files you'll end up with are `llama_modal.py` (server) and `llama_client.py` (laptop).

---

## Step 1 — Get access to the Llama 3.1 weights on Hugging Face

1. Make a Hugging Face account at https://huggingface.co/join if you don't have one.
2. Go to https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct and click **"Agree and access repository"**. Fill out the Meta form (name, affiliation — "Stanford" is fine). Approval is usually automatic within a few minutes, occasionally a few hours.
3. Create an access token at https://huggingface.co/settings/tokens. Click **"New token"**, name it something like `modal-llama`, choose token type **"Read"** (or fine-grained with read access to gated repos). Copy the token — it starts with `hf_...`. You'll only see it once.

## Step 2 — Install Modal and authenticate

In a terminal on your laptop:

```bash
# Use a fresh virtualenv if you like
python -m venv .venv && source .venv/bin/activate

pip install modal
modal token new
```

`modal token new` opens a browser window. Sign up (free tier gives you $30/mo of compute credits, which is way more than enough for personal use) and click "Approve" to link the CLI. You're now authenticated on this machine; no more token juggling.

## Step 3 — Store your HF token as a Modal Secret

Modal Secrets are environment variables that get injected into your containers. The HF libraries automatically read `HF_TOKEN`, so name the variable exactly that.

```bash
modal secret create huggingface-secret HF_TOKEN=hf_your_token_here
```

(You can also do this through the web UI at https://modal.com/secrets if you'd rather not paste a token into your shell history.)

The name `huggingface-secret` is what we reference in code below — keep it consistent.

## Step 4 — Write the server file

Save the following as **`llama_modal.py`**. The comments explain what each piece does; you shouldn't have to change anything to get a first call working.

```python
"""
Llama 3.1 8B Instruct served on Modal with vLLM.
"""

import modal

MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
MODEL_REVISION = "main"  # pin to a commit SHA in production for reproducibility


def download_model():
    """Runs at image build time to pre-download the weights into the image."""
    from huggingface_hub import snapshot_download
    snapshot_download(
        MODEL_NAME,
        revision=MODEL_REVISION,
        ignore_patterns=["*.pt", "*.bin"],  # vLLM only needs the safetensors
    )


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.6.3",
        "huggingface_hub[hf_transfer]==0.26.2",
        "transformers==4.45.2",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})  # faster downloads
    .run_function(
        download_model,
        secrets=[modal.Secret.from_name("huggingface-secret")],
        timeout=60 * 30,
    )
)

app = modal.App("llama-3-1-8b-instruct", image=image)


@app.cls(
    gpu="A10G",                  # 24 GB; plenty for an 8B model in bf16
    scaledown_window=60 * 5,     # keep the container warm 5 min after last call
    timeout=60 * 10,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class Llama:
    @modal.enter()
    def load(self):
        from vllm import LLM
        self.llm = LLM(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            dtype="bfloat16",
            gpu_memory_utilization=0.90,
            max_model_len=8192,
        )

    @modal.method()
    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
    ) -> str:
        from vllm import SamplingParams
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        sampling = SamplingParams(
            temperature=temperature, top_p=top_p, max_tokens=max_tokens
        )
        outputs = self.llm.chat(messages, sampling_params=sampling)
        return outputs[0].outputs[0].text


@app.local_entrypoint()
def main(prompt: str = "Explain what a transformer is in two sentences."):
    print(Llama().generate.remote(prompt))
```

A few things worth understanding:

- **Why the class?** Modal classes let you do expensive setup (loading 16 GB of weights into VRAM) once per container in `@modal.enter()`, then handle many requests cheaply via `@modal.method()`. A bare function would re-load the model every call.
- **Why bake weights into the image?** The `.run_function(download_model, ...)` line runs once when Modal builds the image and stores the weights as part of the container image layer. Subsequent cold starts skip the download entirely — you go from ~5 min cold start to ~30 seconds.
- **GPU choice.** `A10G` (24 GB) is the cheapest GPU that comfortably runs an 8B model in bfloat16. If you want longer context or faster decoding, swap to `"L4"`, `"A100"`, or `"H100"`. Modal's pricing page lists per-second rates.
- **`scaledown_window`** controls how long Modal keeps a container alive after the last request. Higher = fewer cold starts, more cost. 5 minutes is a reasonable default for interactive use; set it to 0 if you only ever do one-off calls.

## Step 5 — Deploy and smoke-test

From the directory containing `llama_modal.py`:

```bash
# Build the image (downloads the weights once, takes ~10-20 min).
# Subsequent deploys are near-instant because the image is cached.
modal deploy llama_modal.py
```

You'll see Modal stream build logs, then output a URL for the deployed app and a list of the functions/classes it registered. The class is now live and callable.

Run a quick end-to-end smoke test:

```bash
modal run llama_modal.py
# Or with a custom prompt:
modal run llama_modal.py --prompt "Write a haiku about gradient descent."
```

The first invocation will cold-start a GPU container (~30s once weights are baked in). You should see the generated text printed to your terminal. If you immediately run it again, it'll reuse the warm container and respond in a second or two.

## Step 6 — Call it from a Python script on your laptop

Save this as **`llama_client.py`**:

```python
import modal

# Look up the deployed class by (app_name, class_name). These must match
# what's in llama_modal.py exactly.
Llama = modal.Cls.from_name("llama-3-1-8b-instruct", "Llama")


def ask(prompt: str, system: str = "You are a helpful assistant.") -> str:
    return Llama().generate.remote(prompt=prompt, system=system)


if __name__ == "__main__":
    answer = ask("In one paragraph, what's the intuition behind attention in transformers?")
    print(answer)
```

Then:

```bash
python llama_client.py
```

That's the full loop. `modal.Cls.from_name(...)` resolves to the deployed class; `.generate.remote(...)` sends the call over the network. You can call `ask(...)` from anywhere in your codebase, in notebooks, in scripts, in scheduled jobs — the only requirement is that the laptop has the `modal` package installed and is authenticated via `modal token new`.

---

## Useful variations

- **Batch / parallel calls.** Use `.map(...)` to fan out:
  ```python
  prompts = ["Q1", "Q2", "Q3"]
  for ans in Llama().generate.map(prompts):
      print(ans)
  ```
  Modal will scale up multiple containers automatically (subject to a default concurrency cap you can raise with `@app.cls(max_containers=...)`).

- **OpenAI-compatible HTTP endpoint.** If you'd rather hit an HTTP endpoint with the OpenAI Python SDK, Modal has a vLLM-OpenAI example you can copy: https://modal.com/docs/examples/vllm_inference. It uses `@modal.asgi_app()` to expose vLLM's built-in OpenAI server, and then you point `openai.OpenAI(base_url=...)` at the Modal URL.

- **Quick iteration.** While editing the function body (not the image), `modal serve llama_modal.py` gives you a hot-reloading dev loop — saved files redeploy in seconds.

- **Cost sanity check.** An A10G runs roughly $0.001/sec on Modal. A typical short request keeps the GPU busy for a couple seconds, and the 5-minute keep-warm costs about $0.30 per idle stretch. Free credits cover thousands of calls per month at this scale.

## Common gotchas

- **403 from Hugging Face on first deploy.** Means your token doesn't have access to the gated repo yet. Re-check that the Meta form on the model card was approved (you'll get an email) and that the token in `huggingface-secret` is the right one.
- **`modal: command not found`.** Make sure your virtualenv is active, or use `python -m modal ...` instead.
- **Out-of-memory on load.** If you bumped `max_model_len` very high or switched to a smaller GPU, drop `gpu_memory_utilization` to `0.85` or shrink `max_model_len`.
- **Forgetting to redeploy.** `python llama_client.py` always talks to whatever's currently deployed. If you change `llama_modal.py`, re-run `modal deploy llama_modal.py` before the client will see the change.

## Recap of every command you'll type

```bash
# One-time setup
pip install modal
modal token new
modal secret create huggingface-secret HF_TOKEN=hf_your_token_here

# Deploy (re-run whenever llama_modal.py changes)
modal deploy llama_modal.py

# Smoke test from the CLI
modal run llama_modal.py --prompt "hello"

# Use from your laptop
python llama_client.py
```

That's it. You now have a self-hosted Llama 3.1 8B endpoint that costs pennies per call and that you can import into any Python project.
