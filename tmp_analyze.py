import json, os, glob
from collections import Counter

tool_usage = Counter()
tool_ok = Counter()
tick_count = 0
total_tools = 0

for state_path in glob.glob("/app/work/users/*/novels/*_*/state.json"):
    proj = os.path.dirname(state_path)
    plans_dir = os.path.join(proj, "plans")
    if not os.path.exists(plans_dir):
        continue
    for pf in sorted(os.listdir(plans_dir)):
        tick_count += 1
        plan = json.load(open(os.path.join(plans_dir, pf)))
        tools = plan.get("execution", {}).get("actions_executed", [])
        for t in tools:
            tn = t.get("tool", "?")
            total_tools += 1
            tool_usage[tn] += 1
            if t.get("success"):
                tool_ok[tn] += 1

all_tools = [
    "character.generate", "character.update",
    "location.generate", "location.update",
    "relationship.create", "relationship.update",
    "faction.generate", "faction.update",
    "lore.extract", "lore.contradiction_check",
    "loop.create", "loop.resolve",
    "memory.search",
]

print("TOOL                         CALLS   OK   STATUS")
print("-" * 60)
for tn in all_tools:
    c = tool_usage.get(tn, 0)
    ok = tool_ok.get(tn, 0)
    bar = ">>>> USED" if c > 0 else "NEVER CALLED"
    print(f"{tn:<30} {c:>5} {ok:>4}  {bar}")

print()
print(f"Ticks analyzed: {tick_count}")
print(f"Total tool calls: {total_tools}")
print(f"Avg tools per tick: {total_tools / max(1, tick_count):.1f}")
print()
print("Call distribution:")
for tn, c in tool_usage.most_common():
    print(f"  {tn}: {c} ({c / total_tools * 100:.0f}%)")
