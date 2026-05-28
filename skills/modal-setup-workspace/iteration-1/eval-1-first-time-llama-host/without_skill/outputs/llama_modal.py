"""
Llama 3.1 8B Instruct served on Modal with vLLM.

Deploy with:
    modal deploy llama_modal.py

Then call the deployed function from your laptop using llama_client.py.

You can also test the function directly from the CLI:
    modal run llama_modal.py
"""

import modal

# ---------------------------------------------------------------------------
# Image: a container with CUDA + vLLM + the HF libraries needed to download
# and run Llama 3.1 8B Instruct. We bake the weights into the image so cold
# starts don't have to re-download ~16 GB every time.
# ---------------------------------------------------------------------------

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
        timeout=60 * 30,  # 30 min to download
    )
)

app = modal.App("llama-3-1-8b-instruct", image=image)


# ---------------------------------------------------------------------------
# The class is a Modal "function" that holds state (the loaded model) across
# requests. @modal.enter() runs once per container; @modal.method() exposes
# the call to the outside world.
# ---------------------------------------------------------------------------

@app.cls(
    gpu="A10G",                  # 24 GB; plenty for an 8B model in bf16
    scaledown_window=60 * 5,     # keep the container warm for 5 min after the last call
    timeout=60 * 10,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class Llama:
    @modal.enter()
    def load(self):
        from vllm import LLM, SamplingParams  # noqa: F401  (SamplingParams used below)

        # vLLM loads the model into GPU memory once, here.
        self.llm = LLM(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            dtype="bfloat16",
            gpu_memory_utilization=0.90,
            max_model_len=8192,
            enforce_eager=False,
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

        # Llama 3.1 Instruct expects the official chat template.
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        # vLLM has chat() in recent versions; we use it directly so we don't
        # have to format the chat template by hand.
        sampling = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        outputs = self.llm.chat(messages, sampling_params=sampling)
        return outputs[0].outputs[0].text


# ---------------------------------------------------------------------------
# `modal run llama_modal.py` will execute this local entrypoint, which is the
# fastest way to smoke-test the deployment before you call it from your laptop.
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(prompt: str = "Explain what a transformer is in two sentences."):
    print(Llama().generate.remote(prompt))
