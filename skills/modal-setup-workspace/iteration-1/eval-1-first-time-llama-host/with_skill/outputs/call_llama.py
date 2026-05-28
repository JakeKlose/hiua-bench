"""
Call the Modal-hosted Llama from a regular Python script on your laptop.

Run this AFTER `modal run llama_app.py::smoke_test` has succeeded once.

  python call_llama.py

This script does NOT use `modal run`. It uses `modal.Cls.from_name(...)` to
get a handle to the already-deployed app from any Python process — so you
can drop this same pattern into a Jupyter notebook, a CLI tool, a Flask
server, whatever.
"""

import modal

# Look up the class by (app name, class name) — these must match what's in
# llama_app.py: `app = modal.App("llama-8b")` and `class Llama:`.
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
