"""
OPTIONAL: Self-host an open-weights model on Modal GPUs via vLLM.

Use this if (a) you want to run models not on Groq's free tier
(e.g., DeepSeek V3, Qwen 235B), and (b) you have Modal GPU credits.

This template is NOT required for the free or OSS pipelines — it's a reference
for paper-stage scaling. Adapts the existing modal_app.py adapter pattern.

Cost on Modal (rough):
  A100-80GB:  ~$3.30/hour
  H100:       ~$5.50/hour
  H200:       ~$6.50/hour

A 70B model in BF16 needs ~140 GB VRAM (2x H100 or 1x H200). A 70B model in
FP8 needs ~70 GB (1x H100 or 1x A100-80GB). Use FP8 for the pilot.

Throughput for a 70B FP8 model on a single H100 with vLLM: ~30-80 tokens/sec
of generation, ~500-2000 tokens/sec of prefill. Per trial (action + recall,
~1400 tokens total): roughly 30-60 seconds. For 504 trials: ~4-8 hours on
one H100, or ~1-2 hours with 4-way parallelism.

To use this:
1. Run `python self_host_template.py download_weights` once to cache the
   weights to a Modal volume.
2. Edit modal_app.py to add a 'modal_self_hosted' provider that calls the
   `generate` Modal function below.

This file is a stub, not a turnkey solution — vLLM/Modal configurations
shift, and you'll likely need to adjust the gpu type, image, and volume
paths to your situation.
"""

import modal

VOL = modal.Volume.from_name("hiua-llm-weights", create_if_missing=True)
WEIGHTS_DIR = "/weights"

# vLLM-on-Modal image. Pin vllm and the CUDA/torch versions because vLLM is
# sensitive to combinations.
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.11")
    .pip_install("vllm==0.6.4", "huggingface_hub", "hf-transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("hiua-self-host", image=vllm_image)


@app.function(
    gpu="H100",
    timeout=4 * 60 * 60,
    volumes={WEIGHTS_DIR: VOL},
    secrets=[modal.Secret.from_name("huggingface-secret")],  # HF_TOKEN
)
def download_weights(model_id: str = "meta-llama/Llama-3.3-70B-Instruct"):
    """Run once to cache weights to the Modal volume."""
    from huggingface_hub import snapshot_download
    local_dir = f"{WEIGHTS_DIR}/{model_id.replace('/', '_')}"
    snapshot_download(
        repo_id=model_id, local_dir=local_dir,
        max_workers=8, allow_patterns=["*.json", "*.safetensors", "tokenizer*"],
    )
    VOL.commit()
    print(f"Cached {model_id} to {local_dir}")


@app.cls(
    gpu="H100",
    volumes={WEIGHTS_DIR: VOL},
    timeout=20 * 60,
    container_idle_timeout=5 * 60,
    allow_concurrent_inputs=10,
)
class VLLMRunner:
    model_id: str = modal.parameter()

    @modal.enter()
    def load(self):
        from vllm import LLM, SamplingParams
        local_dir = f"{WEIGHTS_DIR}/{self.model_id.replace('/', '_')}"
        self.llm = LLM(
            model=local_dir, dtype="bfloat16",
            gpu_memory_utilization=0.90, max_model_len=8192,
        )
        self.sampling = SamplingParams  # alias for use in generate()

    @modal.method()
    def generate(self, system: str, user: str, seed: int = 0, temperature: float = 0.7) -> str:
        from vllm import SamplingParams
        # Use the model's chat template
        prompt = self.llm.get_tokenizer().apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True,
        )
        params = SamplingParams(
            temperature=temperature, max_tokens=2048, seed=seed,
        )
        out = self.llm.generate([prompt], params)
        return out[0].outputs[0].text


# To integrate into modal_app.py, add this provider branch in call_model:
#
#     if provider == "modal_self_hosted":
#         runner = VLLMRunner(model_id=model_id)
#         return runner.generate.remote(system=system, user=user, seed=seed, temperature=temperature)
#
# Then add ModelSpecs with provider="modal_self_hosted" and the HuggingFace
# model_id. Pricing for cost estimator: ignore (GPU-hours not token-based).
