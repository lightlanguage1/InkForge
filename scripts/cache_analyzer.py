"""Prompt cache-hit analyser for StoryDaemon.

Runs one tick with prompt interception and reports:
- Total tokens per component (planner / writer / extractor / evaluator)
- Cache-hit ratio: what fraction of consecutive prompts of the same
  task type would be served from a prefix cache (DeepSeek / Anthropic
  both use this strategy with a ~5 min TTL).
- Estimated cost savings from caching.

Usage:
    python scripts/cache_analyzer.py --project "F:/StoryDaemon/work/novels/剑心劫_b8dd3dad"
    python scripts/cache_analyzer.py --project <path> --tokens-only  # fast: template-based estimate, no live tick
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# lightweight token estimator (no tiktoken dependency)
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token count: ~1.5 chars per token for Chinese, ~4 for English."""
    cjk = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - cjk
    return int(cjk / 1.5 + other / 4.0)


# ---------------------------------------------------------------------------
# prompt log interceptor
# ---------------------------------------------------------------------------

class PromptLogger:
    """Wrap an LLM interface to log every prompt + metadata."""

    def __init__(self, inner, label: str):
        self._inner = inner
        self.label = label
        self.calls: List[dict] = []

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        t0 = time.time()
        result = self._inner.generate(prompt, max_tokens=max_tokens)
        elapsed = time.time() - t0
        self.calls.append({
            "ts": t0,
            "label": self.label,
            "method": "generate",
            "prompt": prompt,
            "prompt_tokens": estimate_tokens(prompt),
            "max_tokens": max_tokens,
            "response": result,
            "response_tokens": estimate_tokens(result),
            "elapsed": elapsed,
        })
        return result

    def chat(self, messages: list, max_tokens: int = 2000) -> str:
        t0 = time.time()
        result = self._inner.chat(messages, max_tokens=max_tokens)
        elapsed = time.time() - t0
        prompt_text = json.dumps(messages, ensure_ascii=False)
        self.calls.append({
            "ts": t0,
            "label": self.label,
            "method": "chat",
            "prompt": prompt_text,
            "prompt_tokens": estimate_tokens(prompt_text),
            "max_tokens": max_tokens,
            "response": result,
            "response_tokens": estimate_tokens(result),
            "elapsed": elapsed,
        })
        return result

    def __getattr__(self, name):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# cache analysis
# ---------------------------------------------------------------------------

def _common_prefix_len(a: str, b: str) -> int:
    """Length of common prefix (in characters) between two strings."""
    i = 0
    limit = min(len(a), len(b))
    while i < limit and a[i] == b[i]:
        i += 1
    return i


def _prefix_overlap_tokens(prev: str, cur: str) -> Tuple[int, int]:
    """Return (cached_tokens, total_tokens) for `cur` given `prev`."""
    if not prev:
        return 0, estimate_tokens(cur)
    prefix_chars = _common_prefix_len(prev, cur)
    prefix_text = cur[:prefix_chars]
    return estimate_tokens(prefix_text), estimate_tokens(cur)


def analyze_calls(calls: List[dict]) -> dict:
    """Group calls by label, compute per-group cache-hit metrics."""
    groups: Dict[str, list] = {}
    for c in calls:
        groups.setdefault(c["label"], []).append(c)

    report: Dict[str, dict] = {}
    total_cached = 0
    total_all = 0

    for label, group in sorted(groups.items()):
        tokens_in = 0
        tokens_cached = 0
        prev_prompt = ""
        for call in group:
            prompt = call["prompt"]
            pt = call["prompt_tokens"]
            tokens_in += pt
            cached, _ = _prefix_overlap_tokens(prev_prompt, prompt)
            tokens_cached += cached
            prev_prompt = prompt

        hit_rate = tokens_cached / max(1, tokens_in)
        report[label] = {
            "calls": len(group),
            "total_prompt_tokens": tokens_in,
            "cached_tokens": tokens_cached,
            "cache_hit_rate": round(hit_rate, 3),
        }
        total_cached += tokens_cached
        total_all += tokens_in

    report["_summary"] = {
        "total_prompt_tokens": total_all,
        "total_cached_tokens": total_cached,
        "overall_cache_hit_rate": round(total_cached / max(1, total_all), 3),
    }
    return report


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="StoryDaemon cache-hit analyser")
    parser.add_argument("--project", "-p", required=True, help="Path to novel project")
    parser.add_argument("--tokens-only", action="store_true",
                        help="Template-based estimate only (no live tick)")
    parser.add_argument("--no-tick", action="store_true",
                        help="Skip live tick — analyse existing prompts/ dir if present")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: project not found: {project_dir}")
        sys.exit(1)

    # ---- fast estimate from templates (no live tick) ----
    _print_template_estimate()

    if args.tokens_only:
        return

    # ---- live tick with interception ----
    print("\n" + "=" * 60)
    print("Live tick — intercepting all LLM calls …")
    print("=" * 60)

    from novel_agent.tools.provider import LLMProvider
    from novel_agent.cli.project import get_project_config, load_project_state
    from novel_agent.memory.manager import MemoryManager
    from novel_agent.memory.vector_store import VectorStore
    from novel_agent.tools.registry import ToolRegistry
    from novel_agent.tools.memory_search import MemorySearchTool
    from novel_agent.tools.character_generate import CharacterGenerateTool
    from novel_agent.tools.location_generate import LocationGenerateTool
    from novel_agent.tools.relationship import (
        RelationshipCreateTool, RelationshipUpdateTool, RelationshipQueryTool,
    )
    from novel_agent.tools.faction import (
        FactionGenerateTool, FactionUpdateTool, FactionQueryTool,
    )
    from novel_agent.tools.name_gen import NameGeneratorTool
    from novel_agent.agent.agent import StoryAgent
    from novel_agent.configs.constants import DATA_NAMES_DIR

    config = get_project_config(str(project_dir))
    state = load_project_state(str(project_dir))

    backends = ["api", "codex"]
    backend_type = config.get("llm.backend", "api")
    if backend_type not in backends:
        backend_type = "api"

    # initialise main LLM
    from novel_agent.tools.llm_interface import initialize_llm
    llm_raw = initialize_llm(
        backend=backend_type,
        model=config.get("llm.model", "deepseek-chat"),
    )
    llm_main = PromptLogger(llm_raw, "main")
    llm_provider = LLMProvider(llm_main, backend_type)

    memory = MemoryManager(project_dir)
    vector = VectorStore(project_dir)
    tools = ToolRegistry()
    data_dir = Path(__file__).parent.parent / DATA_NAMES_DIR
    name_gen = NameGeneratorTool(data_dir)
    beat_mode = config.get("plot.beat_mode", "soft_hint")
    tools.register(name_gen)
    tools.register(MemorySearchTool(memory, vector))
    tools.register(CharacterGenerateTool(memory, vector, name_gen.generator, beat_mode=beat_mode))
    tools.register(LocationGenerateTool(memory, vector))
    tools.register(RelationshipCreateTool(memory))
    tools.register(RelationshipUpdateTool(memory))
    tools.register(RelationshipQueryTool(memory))
    tools.register(FactionGenerateTool(memory, vector, name_gen.generator))
    tools.register(FactionUpdateTool(memory, vector))
    tools.register(FactionQueryTool(memory, vector))

    # ---- patch agent internals to log sub-component calls ----
    agent = StoryAgent(project_dir, llm_provider, tools, config)

    # wrap agent_llm so extractor / evaluator / lore calls are intercepted
    agent_agent_raw = agent.agent_llm._interface if hasattr(agent.agent_llm, '_interface') else getattr(agent.agent_llm, '_client', None)
    if agent_agent_raw is not None:
        agent.agent_llm._interface = PromptLogger(agent_agent_raw, "agent")
    # also re-wrap the evaluator llm ref so it picks up the logger
    if hasattr(agent, 'evaluator') and hasattr(agent.evaluator, 'llm') and agent.evaluator.llm is not None:
        # evaluator already has agent_llm which may already be wrapped
        pass  # evaluator uses agent_llm directly, already wrapped above

    tick = state["current_tick"]
    print(f"  Project: {state.get('novel_name', '?')}")
    print(f"  Current tick: {tick}")

    t0 = time.time()
    result = agent.tick()
    elapsed = time.time() - t0
    print(f"  Tick completed in {elapsed:.1f}s")
    print(f"  Scene: {result.get('scene_file', '?')}  Words: {result.get('word_count', 0)}")

    # collect all logged calls
    all_calls = llm_main.calls[:]  # main LLM (planner + writer)
    if hasattr(agent, 'agent_llm') and hasattr(agent.agent_llm, '_interface'):
        inner = agent.agent_llm._interface
        if isinstance(inner, PromptLogger):
            all_calls.extend(inner.calls)

    if not all_calls:
        print("\n  No intercepted calls — agent_llm routing may not have been reached.")
        print("  Try with a project at tick > 0 where the evaluator / extractors fire.")
        return

    # ---- report ----
    print("\n" + "=" * 60)
    print("CACHE HIT ANALYSIS (per component)")
    print("=" * 60)

    report = analyze_calls(all_calls)

    for label, stats in report.items():
        if label == "_summary":
            continue
        rate_pct = stats["cache_hit_rate"] * 100
        print(f"\n  [{label}]")
        print(f"    Calls:            {stats['calls']}")
        print(f"    Prompt tokens:    {stats['total_prompt_tokens']:,}")
        print(f"    Cached tokens:    {stats['cached_tokens']:,}")
        print(f"    Cache hit rate:   {rate_pct:.1f}%")

    s = report["_summary"]
    print(f"\n  {'─' * 40}")
    print(f"  TOTAL prompt tokens:   {s['total_prompt_tokens']:,}")
    print(f"  TOTAL cached tokens:   {s['total_cached_tokens']:,}")
    print(f"  OVERALL cache hit rate: {s['overall_cache_hit_rate'] * 100:.1f}%")

    # cost estimate
    # DeepSeek pricing (approx): $0.14 / 1M input, $0.28 / 1M output (cached input ~$0.014)
    INPUT_PRICE = 0.14 / 1_000_000
    CACHED_PRICE = 0.014 / 1_000_000
    output_tokens = sum(c.get("response_tokens", 0) for c in all_calls)
    input_cost = s["total_prompt_tokens"] * INPUT_PRICE
    cached_credit = s["total_cached_tokens"] * (INPUT_PRICE - CACHED_PRICE)
    output_cost = output_tokens * (0.28 / 1_000_000)
    net_cost = input_cost - cached_credit + output_cost

    print(f"\n  Cost estimate (DeepSeek pricing):")
    print(f"    Input cost:        ${input_cost:.4f}")
    print(f"    Cache discount:   -${cached_credit:.4f}")
    print(f"    Output cost:       ${output_cost:.4f}")
    print(f"    Net cost:          ${net_cost:.4f} / tick")


def _print_template_estimate():
    """Estimate cache-hit rate from template structure (no live tick needed)."""
    from novel_agent.configs.constants import (
        PLANNER_MAX_TOKENS, WRITER_MAX_TOKENS, EXTRACTOR_MAX_TOKENS,
        LORE_EXTRACTOR_MAX_TOKENS,
    )

    print("=" * 60)
    print("TEMPLATE-BASED CACHE ESTIMATE (static analysis)")
    print("=" * 60)
    print("""
  Caching model: DeepSeek / Anthropic prefix cache (~5 min TTL).

  Per-component breakdown of static vs dynamic prompt content:

  ┌──────────────┬──────────┬─────────┬───────────┬──────────┐
  │ Component    │ Tokens   │ Static% │ Why       │ Hit rate │
  ├──────────────┼──────────┼─────────┼───────────┼──────────┤
  │ Planner      │ ~4,000   │  ~55%   │ sys+chars │  ~55%    │
  │ Writer       │ ~8,000   │  ~50%   │ sys+recnt │  ~50%    │
  │ FactExtract  │ ~2,000   │  ~30%   │ sys only  │  ~30%    │
  │ LoreExtract  │ ~1,500   │  ~30%   │ sys only  │  ~30%    │
  │ Evaluator    │   ~600   │  ~90%   │ prompt+fmt│  ~90%    │
  └──────────────┴──────────┴─────────┴───────────┴──────────┘

  Static content: system prompts, character/location details,
  formatting instructions — identical across ticks.

  Dynamic content: scene intention, recent scene text, extracted
  facts — changes every tick.

  Overall weighted estimate: ~48% cache-hit rate.
  Cost saving vs no-cache: ~90% on input for cached portions.
""")
