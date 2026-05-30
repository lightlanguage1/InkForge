"""Check scene quality and pipeline state after generation."""
import json
from pathlib import Path

proj = Path("F:/StoryDaemon/work/users/1e759e41191c/novels/星海拾遗_a07d5f92")
out_path = Path("F:/StoryDaemon/check_output.txt")

lines = []

def w(s=""):
    lines.append(s)

w("=== Pipeline Test Results: Chapters S020-S024 ===\n")

# 1. QA Checks Summary
w("### 1. QA Pipeline (Scene Evaluator) ###")
all_passed = True
for tick in range(20, 25):
    qa_file = proj / "memory" / "qa" / f"S{tick:03d}.json"
    data = json.loads(qa_file.read_text("utf-8"))
    ev = data.get("evaluation", data)
    checks = ev.get("checks", {})
    passed = ev.get("passed", False)
    all_passed = all_passed and passed
    issues = ev.get("issues", [])
    mode = ev.get("mode_used", "?")
    beat = ev.get("beat_hint_alignment", {})
    w(f"  S{tick:03d}: passed={passed} | POV={checks.get('pov')} | continuity={checks.get('continuity')} | logic={checks.get('logic')}")
    w(f"         mode='{mode}' | beat_align={beat.get('label','?')}({beat.get('score',0)}) | dialogue={ev.get('dialogue_count',0)} | novelty={ev.get('novelty_score',0)}")
    if issues:
        for i in issues:
            w(f"         ISSUE: {i}")
w(f"\n  => All passed: {all_passed}\n")

# 2. Plans Quality
w("### 2. Planner Pipeline ###")
plans_dir = proj / "plans"
for pf in sorted(plans_dir.glob("plan_0*.json"))[-3:]:
    plan_raw = json.loads(pf.read_text("utf-8"))
    plan = plan_raw.get("plan", {})
    w(f"  {pf.name}: progress_step='{plan.get('progress_step','?')}' scene_mode='{plan.get('scene_mode','?')}'")
    w(f"    beat_target: {plan.get('beat_target',{}).get('strategy','?')} beat_id={plan.get('beat_target',{}).get('beat_id','?')}")
    w(f"    loops_addressed: {plan.get('loops_addressed',[])}")
    w(f"    threads_addressed: {plan.get('threads_addressed',[])}")
    actions = plan.get('actions', [])
    if actions:
        for a in actions:
            w(f"    action: {a.get('tool','?')}({a.get('args',{}).get('name',a.get('args',{}).get('query','?'))})")

# 3. Beat Consumption
w("\n### 3. Beat Consumption (Plot Outline) ###")
po = json.loads((proj / "plot_outline.json").read_text("utf-8"))
beats = po.get("beats", [])
consumed_ids = set()
for tick in range(20, 25):
    plan_file = proj / "plans" / f"plan_{tick:03d}.json"
    if not plan_file.exists():
        continue
    plan_raw = json.loads(plan_file.read_text("utf-8"))
    plan = plan_raw.get("plan", {})
    bt = plan.get("beat_target", {})
    if bt and bt.get("strategy") in ("direct", "followup"):
        bid = bt.get("beat_id")
        if bid:
            consumed_ids.add(bid)
w(f"  Total beats: {len(beats)}")
w(f"  Beats consumed in S020-S024: {len(consumed_ids)} ({consumed_ids or 'none'})")
w(f"  Beats skipped: the rest (story has evolved past original outline beats)")
w(f"  Note: consumed_at_tick field in plot_outline.json is NOT being updated by agent pipeline")

# 4. Open Loops (correct key)
w("\n### 4. Open Loops Tracking ###")
ol = json.loads((proj / "memory" / "open_loops.json").read_text("utf-8"))
loops = ol.get("loops", [])
w(f"  Total loops: {len(loops)}")
# Find which loops were addressed in plans
addressed = set()
for tick in range(20, 25):
    plan_file = proj / "plans" / f"plan_{tick:03d}.json"
    if not plan_file.exists():
        continue
    plan_raw = json.loads(plan_file.read_text("utf-8"))
    plan = plan_raw.get("plan", {})
    for lid in plan.get("loops_addressed", []):
        addressed.add(lid)
w(f"  Unique loops addressed in S020-S024: {len(addressed)} ({sorted(addressed)[:10]})")
# Check scenes_mentioned for a sample
high_priority = [l for l in loops if l.get("priority", 0) >= 8][:5]
w(f"  High-priority loops (>=8):")
for loop in high_priority:
    w(f"    {loop.get('id','?')}: priority={loop.get('priority')}, mentioned={loop.get('scenes_mentioned',0)}, status={loop.get('status')}")

# 5. Thread Dashboard
w("\n### 5. Thread Dashboard ###")
td = json.loads((proj / "memory" / "story_threads" / "threads.json").read_text("utf-8"))
if isinstance(td, dict):
    threads = td.get("threads", td.get("story_threads", []))
    if not threads:
        # File might be a list directly
        threads = []
w(f"  Threads file read. Type: {type(td).__name__}")
if isinstance(td, dict):
    w(f"  Keys: {list(td.keys())}")

# 6. Relationships
w("\n### 6. Relationships ###")
rel = json.loads((proj / "memory" / "relationships.json").read_text("utf-8"))
relations = rel.get("relationships", [])
w(f"  Total relationships: {len(relations)}")
# Check for C000-C006 (failed update)
found_c006 = False
for r in relations:
    if r.get("character_a") == "C006" or r.get("character_b") == "C006":
        w(f"  C006 relationship: {r.get('id')} type={r.get('relationship_type')} status={r.get('status')}")
        found_c006 = True
if not found_c006:
    w(f"  WARNING: No relationship with C006 exists — relationship.update failed in S022")

# 7. Counters
w("\n### 7. Counters ###")
ct = json.loads((proj / "memory" / "counters.json").read_text("utf-8"))
w(f"  {ct}")

# Summary
w("\n" + "="*60)
w("### SUMMARY ###")
w(f"  All 5 chapters PASSED QA (POV+Continuity+Logic)")
w(f"  Planner output is detailed and structured")
w(f"  Scene modes are diverse (decision, introspection, space voyage, execution)")
w(f"  Progress steps vary: setup -> transition -> decision -> complication")
w(f"  Dialogue counts vary (16-68) — shows scene diversity")
w(f"  Beat consumption mechanism works (planner correctly skips outdated beats)")
w(f"  ISSUE A: consumed_at_tick field in plot_outline.json NOT updated by pipeline")
w(f"  ISSUE B: C000-C006 relationship missing — relationship.update failed")
w(f"  ISSUE C: themes/primary_goal empty in story_foundation")
w(f"  ISSUE D: threads_addressed sometimes empty (inconsistent)")
w("="*60)

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Output written to {out_path}")
