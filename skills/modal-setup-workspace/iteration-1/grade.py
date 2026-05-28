"""Grade each response against its assertions. Outputs grading.json per run."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent

def read_all_text(run_dir: Path) -> str:
    """Read all .md and .py files in the run's outputs directory, concat."""
    out_dir = run_dir / "outputs"
    if not out_dir.exists():
        return ""
    parts = []
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.suffix in (".md", ".py", ".txt"):
            try:
                parts.append(p.read_text())
            except Exception:
                pass
    return "\n\n".join(parts).lower()


# Grading rules: assertion text -> (regex pattern or list of patterns to OR over, evidence-extractor)
# Each rule returns (passed: bool, evidence: str)

def check_assertion(assertion_text: str, text: str) -> tuple[bool, str]:
    """Programmatic check for a specific assertion. Returns (passed, evidence)."""
    a = assertion_text.lower()
    t = text  # already lowercased

    # Eval 1 assertions
    if "modal token new" in a:
        passed = "modal token new" in t
        return passed, "'modal token new' " + ("found" if passed else "MISSING")

    if "license on huggingface" in a or "gated model" in a:
        # Look for license acceptance language
        patterns = [r"accept.{0,30}license", r"agree.{0,30}access", r"gated", r"license.{0,30}meta", r"request access", r"meta\.com.{0,30}llama"]
        for p in patterns:
            if re.search(p, t):
                return True, f"matched '{p}'"
        return False, "no license-acceptance language found"

    if "hf_token" in a and "hf-token" in a.replace("_", "-"):
        # HF token + hf-token Modal secret
        has_token = bool(re.search(r"hf[_-]token|huggingface[_-]token|huggingface.secret", t))
        has_secret = bool(re.search(r"secret\s+create\s+(hf-token|huggingface)", t)) or "modal.secret.from_name" in t and ("hf-token" in t or "huggingface" in t)
        passed = has_token and has_secret
        return passed, f"HF_TOKEN={has_token}, hf-token secret={has_secret}"

    if "transformers" in a and ("upper bound" in a or "<4.5" in a):
        # Look for transformers pin with upper bound
        pin = re.search(r'transformers[^"\']*[<,]\s*4\.\d', t)
        passed = bool(pin)
        return passed, "matched: " + (pin.group(0) if pin else "no transformers upper-bound pin found")

    if "scaledown_window" in a and "container_idle_timeout" in a:
        has_sd = "scaledown_window" in t
        has_old = "container_idle_timeout" in t
        # Pass if scaledown_window is used (deprecated one is OK to mention as deprecated)
        passed = has_sd
        return passed, f"scaledown_window={has_sd}, container_idle_timeout={has_old}"

    if "real org/name slash" in a or "sanitized __" in a:
        # Look for the path layout — should NOT use double underscores
        has_double_underscore_path = bool(re.search(r"/weights/\w+__\w", t))
        has_slash_path = bool(re.search(r"/weights/[\w-]+/[\w.-]+", t)) or "real slash" in t or "keep the slash" in t
        passed = (not has_double_underscore_path) and has_slash_path
        return passed, f"slash-layout={has_slash_path}, double-underscore-layout={has_double_underscore_path}"

    if "weight download" in a and "cpu container" in a:
        # Look for separate download function with CPU image
        has_split = bool(re.search(r"download.*image|cpu.image|debian_slim.*download|snapshot_download", t))
        # Strict: should NOT colocate weight download with GPU container
        passed = has_split
        return passed, "weight-download-split=" + str(has_split)

    if "smoke test" in a and "verifies" in a:
        # Look for a smoke_test or single-call verification
        passed = bool(re.search(r"smoke[_ ]?test|hello[_ ]world|verify.*works|single.*inference|first.*inference", t))
        return passed, "smoke-test reference found" if passed else "no smoke test mentioned"

    # Eval 2 assertions
    if "validates all secrets" in a and "app-build" in a:
        patterns = [r"build.?time", r"app.?build", r"at startup", r"eagerly", r"upfront", r"upfront validation", r"validated.*before", r"resolve.{0,30}all.*secret", r"all secrets.*resolved", r"every secret"]
        for p in patterns:
            if re.search(p, t):
                return True, f"matched '{p}'"
        return False, "no build-time validation language"

    if "comment out" in a or "remove the unused" in a:
        passed = bool(re.search(r"comment[\- ]?out|remove.*unused|only list|drop.*secret", t))
        return passed, "fix language " + ("found" if passed else "MISSING")

    if "shows the corrected code" in a:
        # Should have a corrected version showing only openai-api-key
        # Look for code block with openai but without anthropic (or with anthropic commented)
        passed = bool(re.search(r'#\s*modal\.secret\.from_name\("anthropic', t)) or bool(re.search(r'secrets\s*=\s*\[\s*[^\]]*openai[^\]]*\]', t) and not re.search(r'secrets\s*=\s*\[[^\]]*anthropic[^\]]*\]', t))
        return passed, "corrected code " + ("shown" if passed else "not clearly shown")

    if "does not suggest creating placeholder" in a:
        # Primary fix should NOT be "create placeholder secrets". It's OK to mention as a workaround.
        placeholder_primary = bool(re.search(r"primary.{0,30}fix.{0,100}placeholder|first.{0,30}fix.{0,100}placeholder", t))
        # If placeholder is mentioned but not as primary, that's fine
        passed = not placeholder_primary
        return passed, "placeholder not pushed as primary" if passed else "placeholder pushed as primary fix"

    # Eval 3 assertions
    if "transformers version mismatch" in a and ("5.x" in a or "removed" in a):
        patterns = [r"transformers\s*5", r"version.{0,30}mismatch", r"removed.{0,50}method", r"removed.{0,50}attribute", r"transformers.{0,30}4\.x", r"transformers.{0,30}newer", r"open.{0,30}upper bound"]
        for p in patterns:
            if re.search(p, t):
                return True, f"matched '{p}'"
        return False, "no transformers-version-mismatch diagnosis"

    if "upper bound on transformers" in a:
        passed = bool(re.search(r'transformers[^"\']*<\s*4\.\d', t))
        return passed, "transformers upper bound " + ("present" if passed else "MISSING")

    if "shows corrected pip_install" in a:
        passed = bool(re.search(r'pip_install[^)]*transformers', t))
        return passed, "corrected pip_install " + ("shown" if passed else "not shown")

    if "explains why" in a and ("open upper bound" in a or "setup.py" in a):
        patterns = [r"open.{0,30}upper bound", r"setup\.py", r"no upper", r"resolver.{0,30}pick", r"vllm.{0,30}require", r"major version"]
        for p in patterns:
            if re.search(p, t):
                return True, f"matched '{p}'"
        return False, "no explanation of WHY this happens"

    if "does not recommend downgrading vllm" in a:
        # Should NOT recommend downgrading vLLM (e.g., vllm==0.6) as the primary fix
        downgrade_primary = bool(re.search(r"vllm==0\.[0-7]", t))
        passed = not downgrade_primary
        return passed, ("downgrade NOT suggested" if passed else "vllm downgrade suggested")

    # Eval 4 assertions
    if "modal run" in a and "without --detach" in a and "ties app lifecycle" in a:
        patterns = [r"local.{0,30}disconnect", r"foreground", r"client.{0,30}disconnect", r"tied.{0,30}local", r"lifecycle.{0,30}local", r"interpret.{0,30}cancel"]
        for p in patterns:
            if re.search(p, t):
                return True, f"matched '{p}'"
        return False, "no disconnect-causes-stop diagnosis"

    if "re-launch with modal run --detach" in a or "primary fix:" in a and "--detach" in a:
        passed = "--detach" in t
        return passed, "--detach " + ("recommended" if passed else "NOT recommended")

    if "tracking progress" in a or "track progress" in a or "modal app logs" in a:
        passed = "modal app logs" in t or "dashboard" in t or "app.modal.com" in t
        return passed, "progress tracking " + ("explained" if passed else "MISSING")

    if "wrote+committed to a volume" in a or "volume.*per-trial" in a or "modal volume get" in a:
        passed = ("volume" in t and "commit" in t) or "modal volume get" in t
        return passed, "volume recovery " + ("explained" if passed else "MISSING")

    if "per-trial flush" in a or "per.trial" in a or "flush" in a:
        passed = bool(re.search(r"flush.{0,50}per.?trial|per.?trial.{0,50}(commit|flush|write|durable)|commit.{0,30}per", t))
        return passed, "per-trial flush pattern " + ("mentioned" if passed else "MISSING")

    return False, f"NO RULE MATCHED for assertion: {assertion_text[:60]}"


for eval_dir in sorted(ROOT.glob("eval-*")):
    if not eval_dir.is_dir():
        continue
    meta = json.loads((eval_dir / "eval_metadata.json").read_text())
    for cond in ("with_skill", "without_skill"):
        run_dir = eval_dir / cond
        if not run_dir.exists():
            continue
        text = read_all_text(run_dir)
        expectations = []
        for assertion in meta["assertions"]:
            passed, evidence = check_assertion(assertion["text"], text)
            expectations.append({
                "text": assertion["text"],
                "passed": passed,
                "evidence": evidence,
            })
        grading = {
            "eval_id": meta["eval_id"],
            "condition": cond,
            "expectations": expectations,
            "pass_count": sum(1 for e in expectations if e["passed"]),
            "total": len(expectations),
        }
        (run_dir / "grading.json").write_text(json.dumps(grading, indent=2))
        print(f"{eval_dir.name}/{cond}: {grading['pass_count']}/{grading['total']}")
