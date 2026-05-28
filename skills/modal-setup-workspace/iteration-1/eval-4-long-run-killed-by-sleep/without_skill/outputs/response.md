# Your Modal run died because your laptop fell asleep, not because Modal failed

## What actually happened

The errors you saw — `local client disconnected` and `App state is APP_STATE_STOPPED` — are the classic fingerprint of a foreground `modal run` invocation where the **local client** (your laptop) went away. Here is the chain of events:

1. `modal run modal_app.py::full_run` runs the function on Modal's cloud, but the **driver process lives on your laptop**. The local CLI holds an open gRPC stream to the Modal control plane, streams logs back to your terminal, and — critically — owns the App's lifecycle.
2. When you closed the lid, macOS suspended the process (or the network) after a short grace period. Modal's server stopped receiving heartbeats from the client.
3. Modal treats `modal run` as an **ephemeral / interactive** App. When the client disappears, the server tears the App down: `APP_STATE_STOPPED`. Any container that was mid-trial is killed; any function still in the queue is cancelled.
4. Your terminal, when it woke up, reconnected, saw the App had been stopped server-side, and printed the disconnect error.

This is by design. `modal run` is meant for interactive development — Ctrl-C should kill the job. It is the wrong entry point for a 3-hour unattended sweep.

## Can you recover the partial results? Maybe — depends on where you wrote them

The trials themselves are gone (the containers were killed). But any **side effects that completed before the kill** persisted, because Modal Volumes, Dicts, Queues, cloud buckets, and W&B/MLflow runs all live on the server side, not in your driver process.

Check, in roughly this order:

1. **Modal Volume / NetworkFileSystem.** If your trial code did something like `vol.commit()` or wrote to a mounted `modal.Volume`, the files are still there. Mount the volume locally and copy them out:
   ```bash
   modal volume ls <volume-name>
   modal volume get <volume-name> <remote-path> <local-path>
   ```
   Note that writes are only durable after `volume.commit()` — uncommitted writes from killed containers are lost. If you only committed at the end of the run, you have nothing.

2. **Modal Dict / Queue.** If you used `modal.Dict` or `modal.Queue` as a results store, the entries that were `.put()` before the kill are still there. Look them up by name:
   ```python
   import modal
   d = modal.Dict.from_name("trial-results")
   for k in d.keys(): print(k, d[k])
   ```

3. **External stores.** S3/GCS uploads, a Postgres/SQLite-on-volume write, W&B/MLflow logging — all of those completed-before-the-kill records survive. Check your experiment tracker first; that is usually the fastest way to inventory what got through.

4. **Modal app logs.** Even if you wrote nothing durable, the stdout from completed trials is retained in the Modal dashboard for a while. Find the dead App in the web UI (Apps -> Stopped) and you can at least scrape printed metrics out of the logs as a last resort:
   ```bash
   modal app list --json | grep <app-name>
   modal app logs <app-id>
   ```

5. **Local terminal scrollback.** Embarrassing but real — if your terminal kept history, the streamed logs up to disconnect are sitting in your scrollback buffer.

If none of the above apply, the trials are gone and the lesson is that long runs need a results sink that is committed per-trial, not at the end.

## How to make sure this never happens again

There are two independent fixes. Do **both**.

### Fix 1: Detach the run from your laptop

Use `modal run --detach` (or the equivalent `modal.runner.deploy_app` / scheduled function pattern). With `--detach`, the App keeps running on Modal even if your client disconnects; closing your laptop, losing wifi, or Ctrl-C-ing the terminal no longer kills it.

```bash
modal run --detach modal_app.py::full_run --confirm yes
```

You will get an App ID printed immediately. You can then:

- Stream logs from anywhere: `modal app logs <app-id>`
- List running apps: `modal app list`
- Stop it deliberately: `modal app stop <app-id>`

For something you re-run regularly, promote it from `modal run` to `modal deploy` and either call it via `Function.lookup(...).remote()` or schedule it with `modal.Period` / `modal.Cron`. Deployed functions are fully decoupled from any client.

### Fix 2: Make trials individually durable (so disconnects are survivable)

Even with `--detach`, things still die — preemptions, OOMs, bad code in trial 47. Design so that losing the driver never costs you completed work:

- **Write each trial's result the moment it finishes**, to a Modal Volume (with `commit()`), a Dict, or an external store. Never accumulate in an in-memory list that only persists at the end.
- **Make the run idempotent / resumable.** Before launching trial `i`, check whether its result already exists; if so, skip. This turns any crash into a cheap restart.
- **Use `Function.map` or `Function.spawn`** instead of a Python `for` loop in the driver. `.map` parallelizes server-side and returns results as they complete, so the server — not your laptop — owns the iteration. `.spawn` returns a `FunctionCall` object you can poll later from a fresh process.
- **Set per-function `timeout=`, `retries=`, and `max_containers=`** so individual trial failures don't take the whole sweep down.

A minimal resumable pattern:

```python
import modal
app = modal.App("sweep")
vol = modal.Volume.from_name("sweep-results", create_if_missing=True)
results = modal.Dict.from_name("sweep-results-dict", create_if_missing=True)

@app.function(volumes={"/out": vol}, timeout=60*60, retries=2)
def run_trial(cfg):
    key = cfg["id"]
    if key in results:        # idempotent skip
        return results[key]
    out = do_work(cfg)
    results[key] = out        # durable the instant it returns
    vol.commit()
    return out

@app.local_entrypoint()
def full_run():
    cfgs = [...]
    for r in run_trial.map(cfgs, order_outputs=False):
        print(r)
```

Run it with `modal run --detach modal_app.py::full_run`. Now you can close your laptop, the App keeps running, every trial commits as it finishes, and if anything ever does die mid-sweep you re-invoke the same command and it resumes from where it stopped.

### Bonus: prevent the laptop sleep itself

Belt-and-suspenders for the times you forget `--detach`:

- `caffeinate -i -s modal run ...` on macOS prevents idle/system sleep for the duration of the command.
- Or in System Settings -> Battery -> Options, enable "Prevent automatic sleeping on power adapter when the display is off" (only useful with the lid open or an external display).
- Closing the lid still suspends regardless — only `--detach` truly fixes that case.

## TL;DR

- **Cause:** `modal run` (without `--detach`) is a foreground command tethered to your laptop. Lid-close suspended the client, Modal saw the disconnect, and stopped the App.
- **Recovery:** check Modal Volumes (`modal volume get`), Dicts, your experiment tracker (W&B/MLflow), external buckets, and the App's retained logs in the dashboard. Anything written and committed before the kill is still there; in-memory results are not.
- **Prevention:** always launch long runs with `modal run --detach` (or `modal deploy` + schedule), persist each trial's result the moment it completes, and make the entrypoint idempotent so re-runs resume rather than restart.
