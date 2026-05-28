"""
Call the deployed Llama 3.1 8B Instruct function from your laptop.

Prereqs:
    pip install modal
    modal token new       # one-time auth on this machine
    modal deploy llama_modal.py   # do this once (or whenever you change llama_modal.py)

Then just run:
    python llama_client.py
"""

import modal

# Look up the deployed class by (app_name, class_name). These must match
# what's in llama_modal.py exactly.
Llama = modal.Cls.from_name("llama-3-1-8b-instruct", "Llama")


def ask(prompt: str, system: str = "You are a helpful assistant.") -> str:
    # `()` constructs a handle to the remote class; `.generate.remote(...)`
    # ships the call to Modal and blocks until the answer comes back.
    return Llama().generate.remote(prompt=prompt, system=system)


if __name__ == "__main__":
    answer = ask("In one paragraph, what's the intuition behind attention in transformers?")
    print(answer)
