# Modal long run killed when laptop slept — diagnosis, prevention, recovery

## What actually happened

The error signature is unambiguous: `App state is APP_STATE_STOPPED` plus `local client disconnected` after roughly 40 minutes is Modal's standard pattern for **"the local CLI lost its connection, so Modal cancelled the run."**

You started the job with:

```bash
modal run modal_app.py::full_run --confirm yes
```

Plain `modal run` (without `--detach`) opens a streaming session between your laptop and Modal's control plane. While that session is alive, Modal forwards container logs to your terminal — and, crucially, **treats a client disconnect as a cancel signal**. The model is "you're watching it; if you walk away, you must want it stopped."

When you closed your laptop and went to dinner, macOS suspended the network within a minute or two. Modal's server saw the heartbeat from your CLI stop, waited out its grace period, and then transitioned the app to `APP_STATE_STOPPED`. All in-flight containers were torn down. The 40 minutes you saw is just how long the run survived between the suspend and the server-side timeout.

This is not a bug — it's the documented behavior of attached runs. It is also the single most common way long Modal jobs die.

## Prevention: always use `--detach` for anything over a few minutes

The one-flag fix:

```bash
modal run --detach modal_app.py::full_run --confirm yes
```

With `--detach`, Modal runs the app entirely on its own infrastructure. Your CLI prints the dashboard URL and exits. Closing your laptop, losing WiFi, killing your terminal — none of it touches the running job.

Useful companion commands while a detached run is in flight:

```bash
modal app list                       # find your running app's ID
modal app logs <app-id>              # re-attach to live logs from any machine
modal app stop <app-id>              # kill it on purpose
```

You can also just open the dashboard URL Modal printed at launch and watch progress there.

A few practical habits that go with `--detach`:

1. **Default to `--detach` for any run > ~5 minutes.** The cost of using it on a short run is zero; the cost of forgetting it on a long run is the entire run.
2. **Print the app ID at the start of your entrypoint** (or just copy it from the dashboard URL) so you can `modal app logs <id>` from your phone or another machine.
3. **Disable laptop sleep during attached runs** if you ever do leave one running — `caffeinate -dims` on macOS for the duration. But this is a backup; `--detach` is the real answer.
4. **Don't rely on Ctrl-C-to-pause semantics.** In an attached run, Ctrl-C kills the whole app the same way a disconnect does.

## Recovery: were your trials actually lost?

Probably not all of them — but **it depends entirely on how `full_run` was writing results**. Two scenarios:

### Scenario A: trials write to a `modal.Volume` and commit per-trial

If the function looks something like:

```python
results_vol = modal.Volume.from_name("my-results", create_if_missing=True)

@app.function(volumes={"/vol": results_vol})
def run_trial(...):
    ...
    with open(f"/vol/trial_{i}.jsonl", "a") as f:
        f.write(json.dumps(result) + "\n")
    results_vol.commit()    # <-- the key line
```

…then every trial that finished before the disconnect is **already saved**, and you can pull it back right now:

```bash
modal volume ls <your-volume-name>
modal volume get <your-volume-name> <path> ./recovered/
```

`modal volume ls` is the first thing to run. Look at file timestamps — anything dated before the crash is recoverable.

### Scenario B: results are accumulated in memory and written at the end

If `full_run` collected results in a Python list/dict in the orchestrator and only wrote the file at the end (a very common pattern), **those in-memory results died with the container** and there is nothing on the Modal side to recover. Modal does not snapshot container memory.

In this case the only "recovery" is to look in two places:

- **The Modal dashboard for the killed app.** Open it from `modal app list --all` or your dashboard history. Per-container logs are retained for a while after the app stops — if your trial function printed results (or even partial info like `trial 17 -> score 0.82`), you can scrape them from the logs. Not ideal, but better than zero. `modal app logs <app-id>` may also still return the historical logs depending on retention.
- **Any provider-side artifacts.** If your trials were API calls (OpenAI, Anthropic, Groq, etc.), the provider's own dashboard / usage logs / request history may have the responses you can reconstruct from.

### How to make recovery automatic next time

The skill calls this "flush per-trial" and it's worth adopting as a rule for any multi-hour Modal job:

```python
# Inside the per-trial code path, not the outer orchestrator:
with open(f"/vol/results/{trial_id}.json", "w") as f:
    json.dump(result, f)
results_vol.commit()    # cheap; do it every trial
```

Two reasons this matters beyond the laptop-sleep case:

- **Spot preemptions.** Modal occasionally preempts containers (especially for hot GPU classes like H100). Per-trial flush bounds your loss to one trial.
- **Resumability.** If trial files are named by trial ID, your entrypoint can on startup `os.listdir("/vol/results/")` and skip work that's already done — turning recovery into a re-run rather than a restart from zero.

## Concrete checklist for your next launch

1. Modify `full_run` so each trial's result is written to a `modal.Volume` and committed immediately after that trial completes. Name files by trial ID so re-runs can skip completed ones.
2. Add a skip-if-exists check at the top of the trial function so you can re-run safely without redoing finished trials.
3. Launch with `--detach`:
   ```bash
   modal run --detach modal_app.py::full_run --confirm yes
   ```
4. Grab the app ID from the printed dashboard URL. Stash it somewhere (paste it into a note).
5. Close laptop, go to dinner, sleep. Whenever you check back: `modal app logs <app-id>` or just refresh the dashboard.
6. After it finishes, pull results with `modal volume get <volname> results/ ./local-results/`.

## TL;DR

- **Cause:** `modal run` without `--detach` cancels the job when the local CLI disconnects. Laptop sleep = disconnect.
- **Prevention:** always `modal run --detach ...` for runs longer than a few minutes. Monitor via dashboard or `modal app logs <app-id>`.
- **Recovery:** check `modal volume ls` first — anything your code committed to a volume before the crash is still there. If `full_run` only wrote at the end, the in-memory results are gone, but the dashboard logs may contain enough to reconstruct partial data.
- **Architectural fix:** flush + commit results per-trial, key files by trial ID, and make the entrypoint skip already-completed trials. That turns a crash from "lose everything" into "resume where you left off."
