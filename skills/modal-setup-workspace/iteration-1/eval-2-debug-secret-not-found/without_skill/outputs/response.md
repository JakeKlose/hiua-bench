# Why Modal is complaining about Anthropic (and how to fix it)

## What's actually happening

The error is not coming from your application code at runtime — it's coming from Modal's **app initialization** on the client side, before any of your functions execute. Look closely at the message:

```
Stopping app - uncaught exception raised locally:
NotFoundError("Secret 'anthropic-api-key' not found in environment 'main'")
```

Two clues:

1. **"raised locally"** — this happened in your local Python process while Modal was constructing the app, not inside a remote container.
2. **"environment 'main'"** — Modal is looking up the secret by name in your current Modal *workspace environment* and not finding it.

The reason it cares about Anthropic even though this run only uses OpenAI is this line:

```python
app = modal.App("my-app", secrets=SECRETS)
```

By attaching `SECRETS` (which includes `modal.Secret.from_name("anthropic-api-key")`) to the **App itself**, you've told Modal: "every function in this app must have all three of these secrets mounted." `Secret.from_name(...)` is a lazy reference — it doesn't fail at import time, but as soon as you try to *use* the app (e.g. `modal run`, `modal deploy`, or `app.run()`), Modal resolves every referenced secret against your workspace. If even one of them doesn't exist in the environment, the whole app fails to start. It's an all-or-nothing check; Modal does not "skip the ones you didn't call."

So the OpenAI-only trial never even gets a chance to run, because Modal stops at the missing `anthropic-api-key` secret.

## How to fix it

You have three reasonable options, in order from cleanest to quickest.

### Option 1 (recommended): scope secrets per-function, not on the App

Don't put all provider secrets on the App. Attach only the secret(s) each function actually needs. This is the idiomatic Modal pattern and means a missing Anthropic key only breaks Anthropic functions.

```python
import modal

app = modal.App("my-app")  # no global secrets

OPENAI_SECRET = modal.Secret.from_name("openai-api-key")
ANTHROPIC_SECRET = modal.Secret.from_name("anthropic-api-key")
GOOGLE_SECRET = modal.Secret.from_name("google-api-key")

@app.function(secrets=[OPENAI_SECRET])
def run_openai_trial(prompt: str):
    import os
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    ...

@app.function(secrets=[ANTHROPIC_SECRET])
def run_anthropic_trial(prompt: str):
    ...

@app.function(secrets=[GOOGLE_SECRET])
def run_google_trial(prompt: str):
    ...
```

Now an OpenAI-only run won't even look at the Anthropic secret.

### Option 2: actually create the missing secret in Modal

If you *do* eventually want all three providers under one app, just create the secrets so the lookup succeeds. Either:

- **Web UI:** Modal dashboard → Secrets → New secret → name it exactly `anthropic-api-key` with key `ANTHROPIC_API_KEY`. (Also confirm you're in the `main` environment — the workspace selector is in the top nav.)
- **CLI:**
  ```bash
  modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-...
  modal secret create google-api-key   GOOGLE_API_KEY=...
  ```
- **List what you currently have**, to confirm the name and environment:
  ```bash
  modal secret list
  modal secret list --env main
  ```

Common gotchas here: the secret exists but in a different environment (e.g. you created it in `dev` but `modal run` is using `main`), or the name has a typo / different casing than what `from_name` expects. The name in `from_name("anthropic-api-key")` must match exactly.

### Option 3 (quick unblock for today): just remove the unused references

If you only need OpenAI right now and don't want to create the other secrets yet, drop them from the list. You can put them back when you actually need them.

```python
SECRETS = [
    modal.Secret.from_name("openai-api-key"),
]
app = modal.App("my-app", secrets=SECRETS)
```

## Recommendation

Go with **Option 1**. Attaching secrets at the App level is convenient but it couples every function to every provider's credentials, which is exactly the failure mode you just hit. Per-function `secrets=[...]` is more secure (each container only gets what it needs), makes failures local to the affected function, and lets you onboard new providers without breaking unrelated runs.

## Sanity-check checklist before re-running

- [ ] `modal secret list` shows every secret your code references by name
- [ ] The environment you're running in (`modal config show` or the `--env` flag) matches where the secrets live
- [ ] Secret *names* (e.g. `openai-api-key`) match `from_name(...)` exactly — these are Modal's secret identifiers, not the env-var keys
- [ ] Env-var *keys* inside each secret (e.g. `OPENAI_API_KEY`) match what your code reads with `os.environ[...]`
