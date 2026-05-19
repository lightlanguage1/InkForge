"""Novel import engine — stratified iterative skill extraction.

Pipeline: parse → index → sample → batch-LLM-accumulate → audit → assemble.
Character dedup uses relationship-network overlap, not name similarity.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from ..configs.constants import SLUG_GENERATION_MAX_TOKENS
from .models import Skill, StyleProfile, NarrativePattern, CharacterArchetype

if TYPE_CHECKING:
    from .store import SkillStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BATCH_MAX_CHARS = 12000       # two chapters fit in ~8K tokens
REL_OVERLAP_THRESHOLD = 0.6   # merge only if ≥60% of relationships overlap
CONSENSUS_MIN = 1             # patterns / tags need ≥ this many confirmations

# ---------------------------------------------------------------------------
# Chapter parsing (no LLM)
# ---------------------------------------------------------------------------

def extract_chapters(text: str) -> List[str]:
    """Split text into chapters by Chinese chapter markers."""
    pattern = r'^第[一二三四五六七八九十百千零\d]+[章回节部分]'
    lines = text.split('\n')
    chapters: List[str] = []
    current: List[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(pattern, stripped) and current:
            chapters.append('\n'.join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chapters.append('\n'.join(current))
    return chapters or [text]


# ---------------------------------------------------------------------------
# Style statistics — full text (no LLM)
# ---------------------------------------------------------------------------

def analyze_style(chapters: List[str]) -> StyleProfile:
    """Compute style metrics on the FULL text."""
    all_text = '\n'.join(chapters)

    # Sentence stats
    sentences = re.split(r'[。！？.!?\n]+', all_text)
    sent_lens = [len(s.strip()) for s in sentences if len(s.strip()) > 2]
    avg_sent = sum(sent_lens) / len(sent_lens) if sent_lens else 0
    std_sent = (
        (sum((l - avg_sent) ** 2 for l in sent_lens) / len(sent_lens)) ** 0.5
        if sent_lens else 0
    )

    # Dialogue ratio — Chinese quotes 「」『』 "" ""
    dialogue_chars = 0
    for pat in [r'「([^」]*)」', r'『([^』]*)』', r'"([^"]*)"', r'""([^""]*)""']:
        dialogue_chars += sum(len(m) for m in re.findall(pat, all_text))
    dialogue_ratio = dialogue_chars / len(all_text) if all_text else 0

    # Bigram vocabulary richness
    bigrams = [
        all_text[i:i+2] for i in range(len(all_text)-1)
        if '一' <= all_text[i] <= '鿿' and '一' <= all_text[i+1] <= '鿿'
    ]
    vocab_richness = len(set(bigrams)) / len(bigrams) if bigrams else 0

    # Paragraph rhythm — single \n split, filter short lines
    paragraphs = [p.strip() for p in all_text.split('\n') if len(p.strip()) > 20]
    para_lens = [len(p) for p in paragraphs]
    avg_para = sum(para_lens) / len(para_lens) if para_lens else 0

    return StyleProfile(
        avg_sentence_length=round(avg_sent, 1),
        sentence_length_std=round(std_sent, 1),
        vocab_richness=round(vocab_richness, 4),
        dialogue_ratio=round(dialogue_ratio, 3),
        paragraph_length_avg=round(avg_para, 1),
    )


# ---------------------------------------------------------------------------
# Chapter index + stratified sampling (no LLM)
# ---------------------------------------------------------------------------

def _chapter_index(chapters: List[str]) -> List[dict]:
    """Per-chapter stats: dialogue_ratio, para_density, char_count."""
    index = []
    for ch in chapters:
        ch_len = max(1, len(ch))
        d_chars = 0
        for pat in [r'「([^」]*)」', r'『([^』]*)』', r'"([^"]*)"']:
            d_chars += sum(len(m) for m in re.findall(pat, ch))
        paragraphs = [p for p in ch.split('\n') if len(p.strip()) > 20]
        index.append({
            "dialogue_ratio": round(d_chars / ch_len, 4),
            "para_density": round(len(paragraphs) * 1000 / ch_len, 2),
            "char_count": ch_len,
        })
    return index


def _stratified_sample(
    chapters: List[str], index: List[dict], target: int = 15,
) -> List[int]:
    """Select chapter indices across 5 dialogue-density bins + ends."""
    n = len(chapters)
    if n <= target:
        return list(range(n))

    ratios = sorted(enumerate([idx["dialogue_ratio"] for idx in index]),
                    key=lambda x: x[1])
    bin_size = max(1, n // 5)
    selected: set = {0, 1, n - 2, n - 1}

    for b in range(5):
        start = b * bin_size
        end = start + bin_size if b < 4 else n
        bin_items = ratios[start:end]
        if not bin_items:
            continue
        step = max(1, len(bin_items) // 3)
        selected.update(bin_items[i][0] for i in range(0, len(bin_items), step)[:3])

    return sorted(selected)[:target + 4]


def _batch_chapters(
    chapters: List[str], indices: List[int], max_chars: int = BATCH_MAX_CHARS,
) -> List[str]:
    """Group selected chapters into LLM-friendly batches."""
    batches: List[str] = []
    buf: List[str] = []
    buf_len = 0
    for i in indices:
        ch = chapters[i]
        if buf and buf_len + len(ch) > max_chars:
            batches.append('\n\n'.join(buf))
            buf, buf_len = [ch], len(ch)
        else:
            buf.append(ch)
            buf_len += len(ch)
    if buf:
        batches.append('\n\n'.join(buf))
    return batches


# ---------------------------------------------------------------------------
# Accumulated state + merge (character dedup by relationship network)
# ---------------------------------------------------------------------------

def _empty_state() -> dict:
    return {"tags": {}, "patterns": [], "archetypes": []}


def _state_summary(state: dict) -> str:
    """Compact accumulated-state summary for batch context window."""
    lines = []
    tags = sorted(
        [(t, c) for t, c in state["tags"].items() if c >= 2],
        key=lambda x: -x[1],
    )
    if tags:
        lines.append(f"标签: {', '.join(t for t, _ in tags[:10])}")

    patterns = sorted(
        [p for p in state["patterns"] if p.get("confirmations", 1) >= 2] or state["patterns"],
        key=lambda p: -p.get("confirmations", 1),
    )[:8]
    if patterns:
        lines.append(f"模式({len(state['patterns'])}):")
        for p in patterns:
            lines.append(f"- [{p.get('type','?')}] {p.get('template','')}")

    if state["archetypes"]:
        parts = []
        for a in state["archetypes"][:15]:
            rels = a.get("relationship_patterns", [])
            rel_str = ""
            if rels:
                targets = [f"{r.get('with','?')}({r.get('type','?')})" for r in rels[:4]]
                rel_str = " → " + ", ".join(targets)
            parts.append(f"{a.get('name','?')}({a.get('role','?')}){rel_str}")
        lines.append(f"角色({len(state['archetypes'])}): {'; '.join(parts)}")
    return "\n".join(lines) if lines else "(暂无)"


def _converged(history: List[int]) -> bool:
    """True when the last 3 batches each added ≤ 2 new items."""
    return len(history) >= 3 and all(h <= 2 for h in history[-3:])


# -- tag merge --

def _merge_tags(state: dict, new_tags: list) -> dict:
    for t in new_tags:
        if isinstance(t, str):
            state["tags"][t] = state["tags"].get(t, 0) + 1
    return state


# -- pattern merge --

def _merge_patterns(state: dict, new_patterns: list) -> dict:
    existing = {p["template"] for p in state["patterns"]}
    for p in new_patterns:
        if not isinstance(p, dict) or not p.get("template"):
            continue
        tmpl = p["template"]
        if tmpl in existing:
            for ep in state["patterns"]:
                if ep["template"] == tmpl:
                    ep["confirmations"] = ep.get("confirmations", 1) + 1
                    if len(p.get("example", "")) > len(ep.get("example", "")):
                        ep["example"] = p["example"]
                        ep["description"] = p.get("description", ep["description"])
                    break
        else:
            p["confirmations"] = 1
            state["patterns"].append(p)
            existing.add(tmpl)
    return state


# -- character merge (name + relationship-network) --

def _rel_key(rel: dict) -> tuple:
    """Normalize relationship into comparable key."""
    return (rel.get("with", ""), rel.get("type", ""))


def _relationship_overlap(a: dict, b: dict) -> float:
    """Jaccard similarity of two characters' relationship networks."""
    rels_a = {_rel_key(r) for r in a.get("relationship_patterns", [])}
    rels_b = {_rel_key(r) for r in b.get("relationship_patterns", [])}
    if not rels_a and not rels_b:
        return 0.0
    intersection = rels_a & rels_b
    return len(intersection) / len(rels_a | rels_b)


def _name_overlap(a: str, b: str) -> bool:
    """True if two name strings likely refer to same character."""
    if a == b:
        return True
    if a in b or b in a:
        return True
    parts_a = {p for p in a.replace("/", " ").replace("、", " ").split() if p}
    parts_b = {p for p in b.replace("/", " ").replace("、", " ").split() if p}
    if parts_a & parts_b:
        return True


def _mutually_referenced(a: dict, b: dict) -> bool:
    """True if A's relationship network references B (or vice versa).

    If A lists B as a relationship target, A and B cannot be the same person.
    This is a hard merge-block — pure deterministic logic, works for any language.
    """
    a_name = a.get("name", "").split("/")[0]
    b_name = b.get("name", "").split("/")[0]
    for rel in a.get("relationship_patterns", []):
        if _name_overlap(rel.get("with", ""), b_name):
            return True
    for rel in b.get("relationship_patterns", []):
        if _name_overlap(rel.get("with", ""), a_name):
            return True
    return False


def _merge_allowed(a: dict, b: dict) -> bool:
    """Block merge only when both are high-confidence proper names with no name
    overlap AND insufficient relationship-network evidence of same identity.

    Two verified real names with no shared components are almost always different
    people.  But one exception: same person operating under a completely different
    name (e.g. reincarnation / alias).  In that case the relationship networks
    will be nearly identical.  Require >= 0.8 Jaccard to override the name block.
    Pure deterministic logic, works for any language.
    """
    if not (a.get("name_type") == "proper" and a.get("name_confidence") == "high"
            and b.get("name_type") == "proper" and b.get("name_confidence") == "high"
            and not _name_overlap(a["name"], b["name"])):
        return True
    return _relationship_overlap(a, b) >= 0.8


def _merge_relationships(existing: list, incoming: list) -> list:
    """Merge relationship lists, dedup by 'with' key."""
    result = list(existing)
    targets = {r.get("with", "") for r in result}
    for r in incoming:
        target = r.get("with", "")
        if not target:
            continue
        if target not in targets:
            result.append(r)
            targets.add(target)
        else:
            for er in result:
                if er.get("with") == target:
                    if len(r.get("dynamic", "")) > len(er.get("dynamic", "")):
                        er["dynamic"] = r["dynamic"]
                        er["type"] = r.get("type", er.get("type"))
                    break
    return result


ROLE_ORDER = {"minor": 0, "supporting": 1, "love_interest": 2,
              "mentor": 3, "antagonist": 4, "protagonist": 5}


def _dynamic_threshold(archetypes: list) -> float:
    """Compute merge threshold from the overlap distribution of current chars.

    Uses mean + 1.5σ of non-zero pairwise relationship overlaps, clamped
    to [0.5, 0.9].  Sparse networks → lower threshold; dense → higher.
    """
    values = []
    for i in range(len(archetypes)):
        for j in range(i + 1, len(archetypes)):
            v = _relationship_overlap(archetypes[i], archetypes[j])
            if v > 0:
                values.append(v)
    if not values:
        return 0.6  # fallback
    mean = sum(values) / len(values)
    if len(values) < 2:
        return max(0.5, min(0.9, mean + 0.3))
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    threshold = mean + 1.5 * (variance ** 0.5)
    return max(0.5, min(0.9, threshold))


def _suspicious_pairs(archetypes: list, threshold: float | None = None) -> list:
    """Return top-10 character pairs by relationship overlap, above threshold."""
    if threshold is None:
        threshold = _dynamic_threshold(archetypes)
    pairs = []
    for i in range(len(archetypes)):
        for j in range(i + 1, len(archetypes)):
            v = _relationship_overlap(archetypes[i], archetypes[j])
            if v >= threshold:
                pairs.append((v, archetypes[i]["name"], archetypes[j]["name"]))
    pairs.sort(key=lambda x: -x[0])
    return pairs[:6]


def _merge_archetypes(state: dict, new_archetypes: list) -> dict:
    """Merge by name overlap OR relationship-network overlap.

    Filters: non-entities skipped; low-confidence + no-relationship
    characters go to _pending pool instead of formal archetype list.
    """
    threshold = _dynamic_threshold(state["archetypes"] + new_archetypes)
    state.setdefault("_pending", [])

    for a in new_archetypes:
        if not isinstance(a, dict) or not a.get("name"):
            continue

        # Skip non-entities (items / concepts mistaken for characters)
        if a.get("is_entity") is False:
            continue

        # Low-confidence + no relationships → pending pool for rescue sampling
        if (a.get("name_confidence") == "low"
                and not a.get("relationship_patterns")
                and a.get("name_type") != "proper"):
            state["_pending"].append({"name": a["name"].split("/")[0], "text_hint": ""})
            continue

        idx = -1
        # 1. Name-based match
        for ei, ea in enumerate(state["archetypes"]):
            if _name_overlap(a["name"], ea["name"]):
                idx = ei
                break

        # 2. Relationship-network match
        if idx < 0 and a.get("relationship_patterns"):
            best = 0.0
            for ei, ea in enumerate(state["archetypes"]):
                if not ea.get("relationship_patterns"):
                    continue
                if _mutually_referenced(a, ea):
                    continue
                overlap = _relationship_overlap(a, ea)
                if overlap > best:
                    best, idx = overlap, ei
            if best < threshold:
                idx = -1

        if idx >= 0:
            ea = state["archetypes"][idx]
            ea["traits"] = list(set(ea.get("traits", [])) | set(a.get("traits", [])))
            ea["relationship_patterns"] = _merge_relationships(
                ea.get("relationship_patterns", []), a.get("relationship_patterns", []),
            )
            incoming_name = a["name"].split("/")[0]
            if incoming_name not in ea.get("aliases", []) and incoming_name != ea["name"].split("/")[0]:
                ea.setdefault("aliases", []).append(incoming_name)
            if "/" in a.get("name", "") and (
                "/" not in ea.get("name", "")
                or a["name"].count(",") > ea["name"].count(",")
            ):
                ea["name"] = a["name"]
            # Upgrade confidence / name_type
            for field in ["name_confidence", "is_entity"]:
                if a.get(field) and not ea.get(field):
                    ea[field] = a[field]
            nt_a = a.get("name_type", "")
            nt_ea = ea.get("name_type", "")
            if nt_ea == "descriptor" and nt_a in ("alias", "proper"):
                ea["name_type"] = nt_a
            elif nt_ea == "alias" and nt_a == "proper":
                ea["name_type"] = "proper"
            if ROLE_ORDER.get(a.get("role", ""), 0) > ROLE_ORDER.get(ea.get("role", ""), 0):
                ea["role"] = a["role"]
            if ea.get("arc_type") == "static" and a.get("arc_type", "static") != "static":
                ea["arc_type"] = a["arc_type"]
        else:
            a.setdefault("aliases", [])
            a.setdefault("name_type", "proper")
            a.setdefault("name_confidence", "medium")
            a.setdefault("is_entity", True)
            state["archetypes"].append(a)
    return state


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

def _batch_prompt(batch: str, state_summary: str, novel_name: str) -> str:
    """Build the per-batch extraction prompt."""
    is_first = state_summary == "(暂无)"
    header = (
        f'你是小说技法分析师。分析《{novel_name}》的以下文本，提取写作技法。\n\n'
        if is_first else
        f'继续分析《{novel_name}》的新文本段。\n'
        f'已发现内容（不要重复，只补充新发现）:\n{state_summary}\n\n---\n\n新材料:\n'
    )
    return header + (
        f'{batch}\n\n'
        '提取（只提取这段中确实出现的）:\n'
        '1. style_tags: 3-5个风格标签（中文2-4字）\n'
        '2. patterns: 1-3个叙事技法，各含type/template/description/example\n'
        '   type: scene_structure|transition|tension_arc|dialogue_pattern|'
        'pov_pattern|erotic_style|emotional_rhythm|pacing|description\n'
        '3. characters: 0-5个新出现的角色，各含:\n'
        '   name: "原名/化名/绰号"格式。无法推断真名则不提取。\n'
        '   name_type: proper(专名/真名)|alias(化名/别名)|descriptor(描述性称呼)\n'
        '   name_confidence: high(原文明确写出真名)|medium(有固定称呼但不确定是否真名)|low(完全推断的)\n'
        '   role: protagonist|antagonist|supporting|mentor|love_interest|minor\n'
        '   traits: 3-5个性格特质(非外貌), arc_type: growth|fall|redemption|static|tragic\n'
        '   relationship_patterns: [{"with":"对方原名","type":"关系","dynamic":"权力动态"}]\n'
        '   is_entity: 确认该角色是具有意识的人物(非物品/招式/地名/概念)\n'
        '返回JSON: {"style_tags":[...],"patterns":[...],"characters":[...]}，只返回JSON。'
    )


def _audit_cleanup_prompt(archetypes: list, tags: list, novel_name: str) -> str:
    """R1: cleanup prompt — tags dedup + descriptor merge + high-overlap merging."""
    threshold = _dynamic_threshold(archetypes)
    pairs = _suspicious_pairs(archetypes, threshold)

    suspect_lines = []
    normal_lines = []
    for a in archetypes:
        is_suspect = (
            a.get("name_type") == "descriptor"
            or a.get("name_confidence") == "low"
            or not a.get("relationship_patterns")
        )
        name_in_pairs = any(
            a["name"].split("/")[0] in (p[1].split("/")[0], p[2].split("/")[0])
            for p in pairs
        )
        if is_suspect or name_in_pairs:
            rels = a.get("relationship_patterns", [])
            rel_str = "; ".join(f'{r.get("with","?")}({r.get("type","?")})' for r in rels[:6])
            suspect_lines.append(
                f'{a["name"]} | type={a.get("name_type","?")} | conf={a.get("name_confidence","?")} | '
                f'role={a.get("role","?")} | traits={", ".join(a.get("traits",[])[:5])} | '
                f'arc={a.get("arc_type","?")} | rels={{{rel_str}}}'
            )
        else:
            normal_lines.append(
                f'{a["name"]} | type={a.get("name_type","?")} | role={a.get("role","?")} | '
                f'traits={", ".join(a.get("traits",[])[:2])} | arc={a.get("arc_type","?")} | '
                f'rel_count={len(a.get("relationship_patterns",[]))}'
            )

    pair_lines = "\n".join(f"  {v:.2f} | {a} ↔ {b}" for v, a, b in pairs) if pairs else "  (无)"

    return (
        f'审核《{novel_name}》- 清理轮:\n\n'
        f'标签({len(tags)}个): {", ".join(tags)}\n\n'
        f'可疑合并对(重叠≥{threshold:.2f}):\n{pair_lines}\n\n'
        f'待审查角色({len(suspect_lines)}个):\n' + "\n".join(suspect_lines) + '\n\n'
        f'其他角色({len(normal_lines)}个):\n' + "\n".join(normal_lines) + '\n\n'
        '任务: 1)标签近义合并去重 2)descriptor角色合并或删除 3)高重叠对合并\n'
        '返回JSON: {{"tags":["去重后的标签"],'
        '"merge_pairs":[["角色A","角色B"],...],"remove":["要删除的角色名",...]}}\n'
        'merge_pairs: 需要合并的角色对(第一个保留，第二个合并进去)\n'
        'remove: descriptor角色且无法合并的，放入此列表删除\n'
        '只返回JSON'
    )


def _audit_fix_prompt(audited: list, novel_name: str) -> str:
    """R2: fix prompt — only return patches for wrong roles/traits/arcs.

    The output is a lightweight patch list, not full character objects.
    This avoids token overflow and reconstruction failures.
    """
    char_lines = []
    for a in audited:
        char_lines.append(
            f'{a.get("name","?")} | role={a.get("role","?")} | '
            f'traits={", ".join(a.get("traits",[]))} | arc={a.get("arc_type","?")}'
        )

    return (
        f'审核《{novel_name}》角色列表，找出需要修正的条目:\n\n'
        + "\n".join(char_lines) + '\n\n'
        '返回JSON: {{"fixes":[\n'
        '  {{"name":"角色名","role":"修正后的role(为空则不修正)","traits":["替换后的traits(为空则不修正)"],'
        '"arc_type":"修正后的arc_type(为空则不修正)"}}\n'
        ']}}\n\n'
        '规则:\n- 只列出需要修正的角色，不需要修正的不要列\n'
        '- role/traits/arc_type 哪个需要修正就填哪个，正确的留空字符串\n'
        '- traits 如要修正，给出完整替换列表；如不修正，给空数组\n'
        '- 没有需要修正的角色则返回空fixes数组\n'
        '- 只返回JSON'
    )


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(response: str) -> dict:
    """Extract JSON object from LLM response, with basic repair."""
    match = re.search(r'\{[\s\S]*\}', response)
    if not match:
        return {}
    raw = match.group(0)
    raw = re.sub(r',\s*([]}])', r'\1', raw)        # trailing comma
    raw = re.sub(r"'([^']*)'", r'"\1"', raw)        # single → double quotes
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("JSON parse failed: %.200s", raw)
        return {}


# ---------------------------------------------------------------------------
# ---- Rescue sampling --------------------------------------------------------

def _rescue_batches(
    state: dict, chapters: List[str],
    sampled_indices: set, max_rescue: int = 3,
) -> List[str]:
    """Backfill: search unsampled chapters for pending-pool character names."""
    pending = state.get("_pending", [])
    if not pending:
        return []
    pending_names = {p["name"] for p in pending if len(p["name"]) >= 2}
    if not pending_names:
        return []

    candidates = []
    for i, ch in enumerate(chapters):
        if i in sampled_indices:
            continue
        score = sum(1 for name in pending_names if name in ch)
        if score > 0:
            candidates.append((score, i))

    if not candidates:
        return []

    candidates.sort(key=lambda x: -x[0])
    rescue_idx = [i for _, i in candidates[:max_rescue * 2]]
    return _batch_chapters(chapters, sorted(rescue_idx))[:max_rescue]


# ---- Final audit (LLM review after assembly) ----
# ---------------------------------------------------------------------------

def _final_audit(archetypes: list, tags: list, novel_name: str, llm) -> tuple:
    """LLM outputs patch instructions → code applies them to original objects.

    Characters are NEVER reconstructed by the LLM — only mutated in-place
    via merge/remove/fix instructions.  Deterministic cleanup as safety net.
    """
    if not archetypes:
        return [], tags

    # Work on a mutable copy of the originals
    audited = [{**a} for a in archetypes]  # shallow copy

    # -- R1: Merge + remove instructions --
    r1_prompt = _audit_cleanup_prompt(audited, tags, novel_name)
    try:
        r1 = _extract_json(llm.generate(r1_prompt, max_tokens=2500))
        if r1:
            # Apply tag dedup
            if isinstance(r1.get("tags"), list) and r1["tags"]:
                tags = r1["tags"]

            # Apply merges: merge_pairs = [["A", "B"], ...] → merge B into A
            for pair in r1.get("merge_pairs", []) or []:
                if len(pair) == 2:
                    _apply_merge(audited, pair[0], pair[1])

            # Apply removals
            for name in r1.get("remove", []) or []:
                audited = [a for a in audited
                           if not _name_overlap(a.get("name", ""), name)]

            logger.info("Audit R1: %d→%d chars, %d tags",
                         len(archetypes), len(audited),
                         len(tags) if isinstance(tags, list) else 0)
    except Exception as e:
        logger.warning("Audit R1 failed: %s", e)

    # -- R2: Field-level fixes (role/traits/arc_type only) --
    try:
        r2 = _extract_json(llm.generate(_audit_fix_prompt(audited, novel_name),
                                        max_tokens=1000))
        if r2 and r2.get("fixes"):
            for fix in r2["fixes"]:
                name = fix.get("name", "")
                for a in audited:
                    if _name_overlap(a.get("name", ""), name):
                        if fix.get("role"):
                            a["role"] = fix["role"]
                        if fix.get("traits"):
                            a["traits"] = fix["traits"]
                        if fix.get("arc_type"):
                            a["arc_type"] = fix["arc_type"]
                        break
            logger.info("Audit R2: %d fixes applied", len(r2["fixes"]))
    except Exception as e:
        logger.warning("Audit R2 failed: %s", e)

    # -- Deterministic cleanup --
    for a in audited:
        a.setdefault("name_type", "proper")
        a.setdefault("name_confidence", "medium")
        a.setdefault("aliases", [])
        a.setdefault("traits", [])
        a.setdefault("relationship_patterns", [])
        a.setdefault("role", "supporting")
        a.setdefault("arc_type", "static")

    # Remove descriptors
    before = len(audited)
    audited = [a for a in audited if a.get("name_type") != "descriptor"]
    if len(audited) < before:
        logger.info("Audit cleanup: removed %d descriptors", before - len(audited))

    # Force-merge high-overlap pairs
    threshold = _dynamic_threshold(audited)
    to_merge = []
    for i in range(len(audited)):
        for j in range(i + 1, len(audited)):
            if (_relationship_overlap(audited[i], audited[j]) >= threshold
                    and _merge_allowed(audited[i], audited[j])
                    and not _mutually_referenced(audited[i], audited[j])):
                to_merge.append((i, j))
    merged = set()
    for i, j in reversed(sorted(to_merge)):
        if i not in merged and j not in merged:
            _apply_merge_dict(audited[i], audited[j])
            merged.add(j)
    audited = [a for idx, a in enumerate(audited) if idx not in merged]

    # Tag dedup fallback
    if isinstance(tags, list) and len(tags) > 20:
        tags = _dedup_tags(tags)

    return _build_archetype_list(audited), tags


def _apply_merge(audited: list, keep_name: str, absorb_name: str) -> None:
    """Merge absorb into keep in-place.  Absorb removed from list."""
    keep = absorb = None
    for a in audited:
        if _name_overlap(a.get("name", ""), keep_name) and keep is None:
            keep = a
        elif _name_overlap(a.get("name", ""), absorb_name) and absorb is None:
            absorb = a
    if keep is None or absorb is None:
        return
    if not _merge_allowed(keep, absorb):
        return
    _apply_merge_dict(keep, absorb)
    audited.remove(absorb)


def _apply_merge_dict(keep: dict, absorb: dict) -> None:
    """Merge absorb's data into keep (mutates keep in-place)."""
    keep["traits"] = list(set(keep.get("traits", [])) | set(absorb.get("traits", [])))
    keep["relationship_patterns"] = _merge_relationships(
        keep.get("relationship_patterns", []),
        absorb.get("relationship_patterns", []),
    )
    absorb_name = absorb["name"].split("/")[0]
    if absorb_name not in keep.get("aliases", []):
        keep.setdefault("aliases", []).append(absorb_name)
    if ROLE_ORDER.get(absorb.get("role", ""), 0) > ROLE_ORDER.get(keep.get("role", ""), 0):
        keep["role"] = absorb["role"]
    if keep.get("arc_type") == "static" and absorb.get("arc_type", "static") != "static":
        keep["arc_type"] = absorb["arc_type"]


def _dedup_tags(tags: list) -> list:
    """Simple dedup: remove tags that are substrings or share ≥2 chars."""
    result = []
    for t in tags:
        dup = False
        for r in result:
            if t in r or r in t:
                dup = True
                break
            if len(set(t) & set(r)) >= 2 and len(t) >= 3 and len(r) >= 3:
                dup = True
                break
        if not dup:
            result.append(t)
    return result[:20]


def _build_archetype_list(raw: list) -> list:
    """Convert raw archetype dicts to CharacterArchetype objects."""
    result = []
    for a in raw:
        a.setdefault("role", "supporting")
        a.setdefault("traits", [])
        a.setdefault("arc_type", "static")
        a.setdefault("relationship_patterns", [])
        a.setdefault("name_type", "")
        a.setdefault("aliases", [])
        try:
            result.append(CharacterArchetype(**a))
        except Exception:
            continue
    return result


# ===========================================================================
# SkillImporter
# ===========================================================================

class SkillImporter:
    """Import a novel into a Skill via stratified iterative LLM extraction.

    Pipeline: parse → style stats → index → sample → batch-extract-accumulate
    → genre/themes → audit → assemble.
    """

    def __init__(self, llm_interface, store: SkillStore):
        self.llm = llm_interface
        self.store = store

    def import_novel(self, file_path: str, name: str = None) -> Skill:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        novel_name = name or path.stem
        text = path.read_text(encoding='utf-8')
        chapters = extract_chapters(text)
        slug = self._generate_slug(novel_name, text[:5000])

        logger.info("Importing '%s': %d chapters, %.1fM chars",
                     novel_name, len(chapters), len(text) / 1e6)

        # -- Phase 1: Style stats --
        style = analyze_style(chapters)
        logger.info("Style: avg_sent=%.1f, dialogue=%.3f, para_avg=%.0f",
                     style.avg_sentence_length, style.dialogue_ratio,
                     style.paragraph_length_avg)

        # -- Phase 2: Index + sample --
        index = _chapter_index(chapters)
        selected = _stratified_sample(chapters, index)
        batches = _batch_chapters(chapters, selected)
        logger.info("Sampled %d/%d chapters → %d batches",
                     len(selected), len(chapters), len(batches))

        # -- Phase 3: Batch LLM extraction --
        state = _empty_state()
        gain_history: List[int] = []
        total_calls = 0

        for bi, batch in enumerate(batches):
            summary = _state_summary(state)
            try:
                data = _extract_json(
                    self.llm.generate(_batch_prompt(batch, summary, novel_name),
                                      max_tokens=2000)
                )
                if not data:
                    continue

                prev_tags, prev_pats, prev_chars = (
                    len(state["tags"]), len(state["patterns"]),
                    len(state["archetypes"]),
                )
                state = _merge_tags(state, data.get("style_tags", []))
                state = _merge_patterns(state, data.get("patterns", []))
                state = _merge_archetypes(state, data.get("characters", []))

                new_ttl = (len(state["tags"]) - prev_tags
                           + len(state["patterns"]) - prev_pats
                           + len(state["archetypes"]) - prev_chars)
                gain_history.append(new_ttl)

                new_names = [state["archetypes"][i]["name"]
                             for i in range(prev_chars, len(state["archetypes"]))]
                logger.info("Batch %d/%d: +%dT +%dP +%dC %s | total %dT %dP %dC",
                             bi + 1, len(batches),
                             len(state["tags"]) - prev_tags,
                             len(state["patterns"]) - prev_pats,
                             len(state["archetypes"]) - prev_chars,
                             new_names,
                             len(state["tags"]), len(state["patterns"]),
                             len(state["archetypes"]))
                total_calls += 1
                if _converged(gain_history):
                    logger.info("Converged after %d/%d batches", bi + 1, len(batches))
                    break
            except Exception as e:
                logger.warning("Batch %d/%d failed: %s", bi + 1, len(batches), e)

        # -- Phase 3b: Rescue sampling (backfill missed chapters) --
        if state.get("_pending"):
            rescue = _rescue_batches(state, chapters, set(selected))
            if rescue:
                logger.info("Rescue: %d batches for pending chars", len(rescue))
                for bi, batch in enumerate(rescue):
                    summary = _state_summary(state)
                    try:
                        data = _extract_json(
                            self.llm.generate(
                                _batch_prompt(batch, summary, novel_name),
                                max_tokens=2000,
                            )
                        )
                        if data:
                            state = _merge_archetypes(state, data.get("characters", []))
                            total_calls += 1
                    except Exception as e:
                        logger.warning("Rescue batch %d failed: %s", bi + 1, e)

        # -- Phase 4: Genre / themes --
        genre, themes = "", []
        try:
            g_prompt = (
                f'小说《{novel_name}》的分析摘要:\n{_state_summary(state)}\n\n'
                '判断流派和主题。返回JSON: {{"genre":"流派","themes":["主题1",...]}}'
            )
            g_data = _extract_json(self.llm.generate(g_prompt, max_tokens=500))
            if g_data:
                genre, themes = g_data.get("genre", ""), g_data.get("themes", [])
            total_calls += 1
            logger.info("Genre: %s, themes: %s", genre, themes)
        except Exception as e:
            logger.warning("Genre extraction failed: %s", e)

        # -- Phase 5: Audit + assemble --
        all_tags = [t for t, _ in sorted(state["tags"].items(), key=lambda x: -x[1])]
        archetypes, all_tags = _final_audit(
            state["archetypes"], all_tags, novel_name, self.llm,
        )
        total_calls += 1
        style.style_tags = all_tags

        total_batches = max(1, len(gain_history))
        patterns = []
        for p in state["patterns"]:
            confs = p.pop("confirmations", 1)
            if confs < CONSENSUS_MIN:
                continue
            p.setdefault("type", "scene_structure")
            p.setdefault("template", "")
            p.setdefault("description", "")
            p.setdefault("example", "")
            p["frequency"] = round(confs / total_batches, 2)
            try:
                patterns.append(NarrativePattern(**p))
            except Exception:
                continue

        skill = Skill(
            id=str(uuid.uuid4())[:8],
            name=novel_name, slug=slug,
            source_novel=novel_name, source_file=str(path),
            tags=all_tags, style_profile=style,
            patterns=patterns, character_archetypes=archetypes,
            genre=genre, themes=themes,
            word_count=sum(len(ch) for ch in chapters),
            chapter_count=len(chapters),
        )

        self.store.save_skill(skill)
        logger.info("Imported '%s': %d tags, %d patterns, %d characters",
                     skill.name, len(all_tags), len(patterns), len(archetypes))
        return skill

    def _generate_slug(self, novel_name: str, sample: str) -> str:
        prompt = (
            f'Novel title: "{novel_name}"\n\nOpening:\n{sample}\n\n'
            'Short English slug (2-4 lowercase words, hyphen-separated). '
            'Return ONLY the slug.'
        )
        try:
            slug = self.llm.generate(prompt, max_tokens=SLUG_GENERATION_MAX_TOKENS)
            return re.sub(r'[^a-z0-9-]', '', slug.strip().lower().replace(" ", "-")).strip("-") or ""
        except Exception as e:
            logger.warning("Slug failed: %s", e)
            return ""
