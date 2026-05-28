# Why Modal is complaining about Anthropic (even though you're only using OpenAI)

## The cause

Modal resolves **every** secret in your app's `secrets=` list at **app-build time**, before any function runs and regardless of whether any function ever actually reads from it. The `modal.Secret.from_name("anthropic-api-key")` call isn't lazy — it's a lookup against your Modal workspace that has to succeed for the app graph to validate.

So when Modal builds the app:

1. It walks the `SECRETS` list attached to `modal.App(..., secrets=SECRETS)`.
2. For each entry, it asks the control plane: "does a secret with this name exist in environment `main`?"
3. The lookup for `anthropic-api-key` returns "no such secret," and the whole app crashes locally before a single container starts.

The fact that your trial only calls OpenAI is irrelevant — the crash happens during app construction, not during function execution. Modal is being defensive about typos: it would rather fail fast than spin up a container and have you discover a missing key 20 minutes into a run.

A second, subtler point: attaching secrets at the **app** level (`modal.App("my-app", secrets=SECRETS)`) means *every* function in the app inherits all three secrets. There's no way to opt out per-function, so any missing one takes down the whole app.

## The fix

Only list secrets you have actually created. Comment the rest out until you create them:

```python
import modal

SECRETS = [
    modal.Secret.from_name("openai-api-key"),
    # modal.Secret.from_name("anthropic-api-key"),   # uncomment after: modal secret create anthropic-api-key ANTHROPIC_API_KEY=...
    # modal.Secret.from_name("google-api-key"),      # uncomment after: modal secret create google-api-key GOOGLE_API_KEY=...
]

app = modal.App("my-app", secrets=SECRETS)
```

That's the whole change. Don't be defensive with secrets — list only what exists right now.

## Verifying and (later) re-enabling the others

Check what secrets actually exist in your workspace:

```bash
modal secret list
```

When you do get an Anthropic key, create the secret and then uncomment the line:

```bash
modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-...
```

If a secret with that name already exists and you want to overwrite it (e.g. you rotated the key), add `--force`:

```bash
modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-new... --force
```

## Optional refinement: scope secrets to the functions that need them

Since you're calling multiple providers as you grow this app, consider moving secrets off the `App` and onto individual `@app.function` decorators. That way a missing Anthropic secret only breaks the Anthropic-calling function, not the whole app:

```python
import modal

OPENAI_SECRET = modal.Secret.from_name("openai-api-key")
# ANTHROPIC_SECRET = modal.Secret.from_name("anthropic-api-key")
# GOOGLE_SECRET    = modal.Secret.from_name("google-api-key")

app = modal.App("my-app")   # no app-level secrets

@app.function(secrets=[OPENAI_SECRET])
def call_openai(prompt: str) -> str:
    import os, openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    ...

# When you have the key, uncomment the secret above and this function:
# @app.function(secrets=[ANTHROPIC_SECRET])
# def call_anthropic(prompt: str) -> str: ...
```

Important caveat: Modal still resolves every `Secret.from_name(...)` it encounters at module import time, even module-level constants you haven't attached to a function yet. So `OPENAI_SECRET = modal.Secret.from_name(...)` for a secret that doesn't exist would still fail. Keep missing ones commented out at the constructor call site, not just at the decorator.

## Summary

- **Cause:** `Secret.from_name(...)` is validated at app-build time. Listing a non-existent secret crashes the app even if no function uses it.
- **Fix:** Comment out `modal.Secret.from_name("anthropic-api-key")` (and `google-api-key` if you don't have that one either). Re-add them after running `modal secret create ...`.
- **Good habit going forward:** attach secrets at the function level rather than the app level, so a missing key only disables the function that needs it.
