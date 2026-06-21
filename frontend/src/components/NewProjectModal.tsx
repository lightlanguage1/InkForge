import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { Textarea } from "./ui/Textarea";
import { Modal } from "./ui/Modal";
import { Toggle } from "./ui/Toggle";
import { Checkbox } from "./ui/Checkbox";
import { getStylePresets, getCraftPresets, createStyleTemplate, createCraftTemplate } from "../api/templates";
import type { CreateProjectReq } from "../types/project";

/* ── Display constants ──────────────────────────────── */
const STEP_META = [
  { label: "故事基础", desc: "为你的故事起个响亮的名字，选定类型与主线前提" },
  { label: "世界设定", desc: "定义故事的世界观、基调与情节驱动模式" },
  { label: "写作技能", desc: "加载风格技能，让 AI 模仿你最爱的叙事腔调" },
  { label: "文风方法", desc: "选择文风与叙事框架，决定 AI 的写作方式" },
];
const STEP_ACCENT_COLORS = ["#c8975a", "#5a96c8", "#4daa85", "#c8975a"];
const GENRES = ["玄幻", "奇幻", "科幻", "悬疑", "言情", "武侠", "都市", "历史"];
const TONES = [
  { label: "轻松幽默", icon: "◎", desc: "轻快活泼" },
  { label: "严肃深沉", icon: "◈", desc: "厚重有力" },
  { label: "浪漫唯美", icon: "◇", desc: "细腻诗意" },
  { label: "黑暗压抑", icon: "●", desc: "沉郁悲怆" },
];

/* ── Types ──────────────────────────────────────────── */
export interface SkillItem {
  slug: string;
  name: string;
  tags: string[];
  source_novel: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (form: CreateProjectReq) => void;
  isLoading: boolean;
  skills: SkillItem[];
}

/* ── Component ──────────────────────────────────────── */
export function NewProjectModal({ open, onClose, onSubmit, isLoading, skills }: Props) {
  const [form, setForm] = useState<CreateProjectReq>({ name: "", genre: "", premise: "", setting: "", tone: "", primary_goal: "" });
  const [step, setStep] = useState(0);
  const [showCustomGenre, setShowCustomGenre] = useState(false);

  const accent = STEP_ACCENT_COLORS[step];

  function resetAndClose() {
    setStep(0);
    setForm({ name: "", genre: "", premise: "", setting: "", tone: "", primary_goal: "" });
    setShowCustomGenre(false);
    onClose();
  }

  function toggleGenre(g: string) {
    const current = (form.genre ?? "").split("、").filter(Boolean);
    const next = current.includes(g) ? current.filter(s => s !== g) : [...current, g];
    setForm({ ...form, genre: next.join("、") });
  }

  function toggleSkill(slug: string) {
    const current = form.skill_ids ?? [];
    setForm({
      ...form,
      skill_ids: current.includes(slug) ? current.filter(s => s !== slug) : [...current, slug],
    });
  }

  return (
    <Modal open={open} onClose={resetAndClose} wide>
      <div className="flex flex-col md:flex-row min-h-[420px]">

        {/* Left: step sidebar */}
        <div
          className="w-full md:w-52 flex-shrink-0 flex md:flex-col justify-between p-4 md:p-6 transition-colors duration-300 flex-row gap-3 md:border-r border-b md:border-b-0"
          style={{ background: "rgba(240,236,226,0.03)", borderColor: "rgba(240,236,226,0.06)" }}
        >
          <div>
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] mb-6" style={{ color: accent, opacity: 0.7 }}>
              步骤 {step + 1} / {STEP_META.length}
            </p>
            <span className="block font-display font-bold text-[88px] leading-none select-none -ml-1 mb-4" style={{ color: accent, opacity: 0.12 }}>
              {step + 1}
            </span>
            <h2 className="text-[17px] font-semibold text-parchment leading-tight tracking-tight">
              {STEP_META[step].label}
            </h2>
            <p className="text-[12px] mt-2 leading-relaxed" style={{ color: "var(--text-3)" }}>
              {STEP_META[step].desc}
            </p>
          </div>

          {/* Step dots + cancel */}
          <div className="space-y-4">
            <div className="flex gap-1.5">
              {STEP_META.map((_, i) => (
                <div
                  key={i}
                  className="h-1 rounded-full transition-all duration-300"
                  style={{
                    width: i === step ? "1.5rem" : "0.625rem",
                    background: i === step ? accent : i < step ? "rgba(240,236,226,0.3)" : "rgba(240,236,226,0.1)",
                  }}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={resetAndClose}
              className="flex items-center gap-1.5 text-[12px] transition-colors duration-150"
              style={{ color: "var(--text-3)" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-2)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-3)"; }}
            >
              <span className="text-[10px]">×</span>
              取消创建
            </button>
          </div>
        </div>

        {/* Right: form steps */}
        <div className="flex-1 overflow-y-auto">
          {step === 0 && (
            <StepBasics
              form={form} setForm={setForm}
              showCustomGenre={showCustomGenre} setShowCustomGenre={setShowCustomGenre}
              toggleGenre={toggleGenre} formGenre={form.genre ?? ""}
              onNext={() => setStep(1)}
              onSkip={() => onSubmit(form)}
              loading={isLoading}
            />
          )}
          {step === 1 && (
            <StepWorld
              form={form} setForm={setForm}
              onBack={() => setStep(0)}
              onNext={() => setStep(2)}
            />
          )}
          {step === 2 && (
            <StepSkills
              form={form} skills={skills}
              toggleSkill={toggleSkill}
              onBack={() => setStep(1)}
              onNext={() => setStep(3)}
            />
          )}
          {step === 3 && (
            <StepStyle
              form={form} setForm={setForm}
              onBack={() => setStep(2)}
              onCreate={() => onSubmit(form)}
              loading={isLoading}
            />
          )}
        </div>
      </div>
    </Modal>
  );
}

/* ── Step sub-panels ─────────────────────────────────── */

interface StepBasicsProps {
  form: CreateProjectReq;
  setForm: (f: CreateProjectReq) => void;
  showCustomGenre: boolean;
  setShowCustomGenre: (v: boolean) => void;
  toggleGenre: (g: string) => void;
  formGenre: string;
  onNext: () => void;
  onSkip: () => void;
  loading: boolean;
}

function StepBasics({ form, setForm, showCustomGenre, setShowCustomGenre, toggleGenre, formGenre, onNext, onSkip, loading }: StepBasicsProps) {
  const selectedGenres = formGenre.split("、").filter(Boolean);
  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div>
        <label className="block text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-3)" }}>
          项目名称 *
        </label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="起一个响亮的名字..."
          autoFocus
          className="w-full text-xl font-semibold bg-transparent border-0 border-b-2 px-0 py-2 focus:outline-none transition-colors"
          style={{ color: "var(--text-1)", borderBottomColor: "var(--border)", caretColor: "var(--accent)" }}
          onFocus={(e) => { e.currentTarget.style.borderBottomColor = "var(--accent)"; }}
          onBlur={(e) => { e.currentTarget.style.borderBottomColor = "var(--border)"; }}
        />
      </div>

      <div>
        <label className="block text-[11px] font-semibold uppercase tracking-wider mb-2.5" style={{ color: "var(--text-3)" }}>
          故事类型
        </label>
        <div className="flex flex-wrap gap-2">
          {GENRES.map((g) => (
            <GenrePill key={g} label={g} selected={selectedGenres.includes(g)} onSelect={() => toggleGenre(g)} />
          ))}
          <button
            type="button"
            onClick={() => setShowCustomGenre(!showCustomGenre)}
            className="px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-150"
            style={showCustomGenre
              ? { background: "rgba(240,236,226,0.1)", color: "var(--text-1)", border: "1px solid rgba(240,236,226,0.2)" }
              : { background: "transparent", color: "var(--text-3)", border: "1px dashed var(--border)" }
            }
          >
            + 自定义
          </button>
        </div>
        {showCustomGenre && (
          <input
            type="text"
            placeholder="输入自定义类型，多个用顿号分隔..."
            autoFocus
            className="mt-2 w-full text-sm px-3 py-2 rounded-lg focus:outline-none transition-colors"
            style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-1)", caretColor: "var(--accent)" }}
            onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const val = (e.target as HTMLInputElement).value.trim();
                if (val) {
                  const current = (form.genre ?? "").split("、").filter(Boolean);
                  setForm({ ...form, genre: [...current, val].join("、") });
                  (e.target as HTMLInputElement).value = "";
                }
              }
            }}
          />
        )}
      </div>

      <Textarea label="故事前提" value={form.premise ?? ""} onChange={(v) => setForm({ ...form, premise: v })}
        placeholder="一两句话描述故事的核心设定和冲突..." rows={3} />

      <div className="p-3 rounded-lg text-[11px] leading-relaxed" style={{ background: "rgba(200,151,90,0.06)", border: "1px solid rgba(200,151,90,0.15)", color: "var(--text-2)" }}>
        💡 <strong>提示：</strong>填得越详细，AI 生成的故事越真实。类型、前提和主角设定是必须的——如果留空，首次生成时 AI 会根据现有内容自动补全。
      </div>

      <div className="flex justify-end gap-2 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
        <Button variant="ghost" size="sm" onClick={onNext}>更多设定 →</Button>
        <Button size="sm" onClick={onSkip} loading={loading} disabled={!form.name}>创建</Button>
      </div>
    </div>
  );
}

interface StepWorldProps {
  form: CreateProjectReq;
  setForm: (f: CreateProjectReq) => void;
  onBack: () => void;
  onNext: () => void;
}

function StepWorld({ form, setForm, onBack, onNext }: StepWorldProps) {
  return (
    <div className="p-6 space-y-5 animate-fade-in">
      {/* 主角设定 */}
      <div className="p-4 rounded-xl" style={{ background: "rgba(200,151,90,0.04)", border: "1px solid rgba(200,151,90,0.1)" }}>
        <p className="text-[11px] font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--accent)" }}>
          👤 主角设定 <span className="font-normal normal-case" style={{ color: "var(--text-3)" }}>（可选 — 不填则 AI 自主创作）</span>
        </p>
        <div className="space-y-3">
          <Input label="主角姓名/简述" value={form.protagonist ?? ""}
            onChange={(v) => setForm({ ...form, protagonist: v })}
            placeholder="沈青鸿，外冷内热的核爆仙尊，曾是原书天命女主…" />
          <Textarea label="主角核心目标" value={form.primary_goal ?? ""}
            onChange={(v) => setForm({ ...form, primary_goal: v })}
            placeholder="主角最想达成的一件事——主线剧情的核心驱动力…" rows={2} />
        </div>
      </div>

      <Input label="背景设定" value={form.setting ?? ""} onChange={(v) => setForm({ ...form, setting: v })}
        placeholder="古代仙侠世界 / 近未来都市 / 架空大陆..." />

      <div>
        <label className="block text-[11px] font-semibold uppercase tracking-wider mb-2.5" style={{ color: "var(--text-3)" }}>
          故事基调
        </label>
        {/* Quick presets */}
        <div className="grid grid-cols-2 gap-2 mb-2">
          {TONES.map((t) => (
            <ToneCard key={t.label} tone={t} selected={form.tone === t.label}
              onSelect={() => setForm({ ...form, tone: form.tone === t.label ? "" : t.label })} />
          ))}
        </div>
        {/* Custom tone input */}
        <textarea
          rows={2}
          value={TONES.some(t => t.label === form.tone) ? "" : form.tone}
          onChange={e => setForm({ ...form, tone: e.target.value })}
          placeholder="或自定义基调，例：宏大冷峻的太空歌剧，孤独感与求知欲交织…"
          className="w-full text-sm rounded-xl px-3 py-2 resize-none"
          style={{
            background: "var(--bg-raised)", border: "1px solid var(--border)",
            color: "var(--text-1)", outline: "none", lineHeight: 1.6,
            borderColor: form.tone && !TONES.some(t => t.label === form.tone) ? "var(--accent)" : "var(--border)",
          }}
          onFocus={e => (e.currentTarget.style.borderColor = "var(--accent)")}
          onBlur={e => {
            if (!form.tone || TONES.some(t => t.label === form.tone))
              e.currentTarget.style.borderColor = "var(--border)";
          }}
        />
      </div>

      <Input label="主题（逗号分隔）" value={form.themes ?? ""} onChange={(v) => setForm({ ...form, themes: v })}
        placeholder="复仇 / 成长 / 爱情 / 救赎..." />

      <div
        className="flex items-center justify-between p-4 rounded-xl cursor-pointer transition-all duration-150"
        style={form.use_plot_first
          ? { background: "rgba(200,151,90,0.08)", border: "1px solid rgba(200,151,90,0.2)" }
          : { background: "var(--bg-raised)", border: "1px solid var(--border)" }
        }
        onClick={() => setForm({ ...form, use_plot_first: !form.use_plot_first })}
      >
        <div className="flex-1 mr-4">
          <p className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>情节优先模式</p>
          <p className="text-[11px] mt-0.5 leading-relaxed" style={{ color: "var(--text-3)" }}>
            AI 先生成情节节拍，再按照节拍写作，叙事推进力更强
          </p>
        </div>
        <Toggle checked={form.use_plot_first ?? false} onChange={(v) => setForm({ ...form, use_plot_first: v })} />
      </div>

      <div className="flex justify-between pt-3" style={{ borderTop: "1px solid var(--border)" }}>
        <Button variant="ghost" size="sm" onClick={onBack}>← 返回</Button>
        <Button variant="ghost" size="sm" onClick={onNext}>选择技能 →</Button>
      </div>
    </div>
  );
}

interface StepSkillsProps {
  form: CreateProjectReq;
  skills: SkillItem[];
  toggleSkill: (slug: string) => void;
  onBack: () => void;
  onNext: () => void;
}

function StepSkills({ form, skills, toggleSkill, onBack, onNext }: StepSkillsProps) {
  const selected = form.skill_ids ?? [];
  return (
    <div className="p-6 space-y-4 animate-fade-in">
      <p className="text-xs leading-relaxed" style={{ color: "var(--text-3)" }}>
        选择写作风格技能，影响 AI 的笔法与叙事风格。可以多选，留空也没关系。
      </p>

      {skills.length === 0 ? (
        <div className="text-center py-8 rounded-xl" style={{ background: "var(--bg-raised)", border: "1px dashed var(--border)" }}>
          <div className="text-xl mb-2 w-10 h-10 rounded-xl mx-auto flex items-center justify-center" style={{ background: "var(--bg-surface)", color: "var(--text-3)" }}>◆</div>
          <p className="text-sm font-medium" style={{ color: "var(--text-2)" }}>暂无可用技能</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-3)" }}>创建项目后可在「技能管理」页面导入</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-52 overflow-auto">
          {skills.map((s) => {
            const isSelected = selected.includes(s.slug);
            return (
              <div
                key={s.slug}
                className="flex items-start gap-3 p-3.5 rounded-xl cursor-pointer transition-all duration-150"
                style={isSelected
                  ? { background: "rgba(200,151,90,0.08)", border: "1px solid rgba(200,151,90,0.2)" }
                  : { background: "var(--bg-raised)", border: "1px solid var(--border)" }
                }
                onClick={() => toggleSkill(s.slug)}
              >
                <div className="mt-0.5"><Checkbox checked={isSelected} /></div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[13px]" style={{ color: isSelected ? "var(--accent)" : "var(--text-1)" }}>{s.name}</p>
                  <p className="text-[11px] mt-0.5 truncate" style={{ color: "var(--text-3)" }}>
                    {s.source_novel} · {(s.tags ?? []).slice(0, 3).join(" / ")}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected.length > 0 && (
        <p className="text-xs font-medium" style={{ color: "var(--accent)" }}>已选 {selected.length} 个技能</p>
      )}

      <div className="flex justify-between pt-3" style={{ borderTop: "1px solid var(--border)" }}>
        <Button variant="ghost" size="sm" onClick={onBack}>← 返回</Button>
        <Button size="sm" onClick={onNext} disabled={!form.name}>下一步 →</Button>
      </div>
    </div>
  );
}

/* ── Presentational atoms ───────────────────────────── */

function GenrePill({ label, selected, onSelect }: { label: string; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-150"
      style={selected
        ? { background: "var(--accent)", color: "var(--bg-base)", border: "1px solid var(--accent)" }
        : { background: "transparent", color: "var(--text-2)", border: "1px solid var(--border)" }
      }
      onMouseEnter={(e) => { if (!selected) { (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)"; (e.currentTarget as HTMLElement).style.color = "var(--accent)"; } }}
      onMouseLeave={(e) => { if (!selected) { (e.currentTarget as HTMLElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLElement).style.color = "var(--text-2)"; } }}
    >
      {label}
    </button>
  );
}

function ToneCard({ tone, selected, onSelect }: { tone: { label: string; icon: string; desc: string }; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="flex items-center gap-2.5 p-3 rounded-xl text-left transition-all duration-150"
      style={selected
        ? { background: "rgba(200,151,90,0.1)", border: "1px solid rgba(200,151,90,0.3)" }
        : { background: "var(--bg-raised)", border: "1px solid var(--border)" }
      }
    >
      <span className="text-base leading-none" style={{ color: selected ? "var(--accent)" : "var(--text-3)" }}>{tone.icon}</span>
      <div>
        <p className="text-[13px] font-semibold" style={{ color: selected ? "var(--accent)" : "var(--text-1)" }}>{tone.label}</p>
        <p className="text-[11px] mt-0.5" style={{ color: "var(--text-3)" }}>{tone.desc}</p>
      </div>
    </button>
  );
}

function StepStyle({ form, setForm, onBack, onCreate, loading }: {
  form: CreateProjectReq; setForm: (f: CreateProjectReq) => void;
  onBack: () => void; onCreate: () => void; loading: boolean;
}) {
  const qc = useQueryClient();
  const { data: presetsS } = useQuery({ queryKey: ["stylePresets"], queryFn: getStylePresets });
  const { data: presetsC } = useQuery({ queryKey: ["craftPresets"], queryFn: getCraftPresets });
  const [createType, setCreateType] = useState<"style" | "craft" | null>(null);
  const styles = presetsS?.templates ?? [];
  const crafts = presetsC?.templates ?? [];

  function group(label: string, emoji: string, items: any[], current: string, type: "style" | "craft", field: "style_id" | "craft_id") {
    return (
      <div>
        <div className="flex items-center gap-2 mb-1">
          <p className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>{emoji} {label}</p>
          <button onClick={() => setCreateType(type)}
            className="text-[10px] border-0 cursor-pointer px-2 py-0.5 rounded-full"
            style={{ background: "rgba(200,151,90,0.08)", color: "var(--text-3)" }}>＋ 自定义</button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setForm({ ...form, [field]: "" })}
            className="text-[12px] px-4 py-2 rounded-xl border-0 cursor-pointer transition-all"
            style={{ background: !current ? "var(--accent)" : "var(--bg-surface)", color: !current ? "var(--bg-base)" : "var(--text-3)", border: !current ? "1px solid var(--accent)" : "1px solid var(--border)" }}>默认</button>
          {items.map(t => (
            <button key={t.id} onClick={() => setForm({ ...form, [field]: t.id })}
              className="text-[12px] px-4 py-2 rounded-xl border-0 cursor-pointer transition-all"
              style={{ background: current === t.id ? "var(--accent)" : "var(--bg-surface)", color: current === t.id ? "var(--bg-base)" : "var(--text-3)", border: current === t.id ? "1px solid var(--accent)" : "1px solid var(--border)" }}>{t.name}</button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      {group("文风 — 怎么写", "🎨", styles, form.style_id ?? "", "style", "style_id")}
      {group("写作方法 — 什么框架", "📐", crafts, form.craft_id ?? "", "craft", "craft_id")}
      <div className="flex gap-3 pt-3 justify-end" style={{ borderTop: "1px solid var(--border)" }}>
        <button onClick={onBack} className="text-sm px-4 py-2 rounded-lg border-0 cursor-pointer" style={{ background: "transparent", color: "var(--text-3)" }}>← 上一步</button>
        <Button size="sm" onClick={onCreate} loading={loading} disabled={!form.name}>创建项目</Button>
      </div>

      {createType && (
        <CreateTemplateModal type={createType} onClose={() => setCreateType(null)}
          onCreated={() => { qc.invalidateQueries({ queryKey: [createType === "style" ? "stylePresets" : "craftPresets"] }); setCreateType(null); }} />
      )}
    </div>
  );
}

function CreateTemplateModal({ type, onClose, onCreated }: {
  type: "style" | "craft"; onClose: () => void; onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [snippet, setSnippet] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!name.trim() || !snippet.trim()) return;
    setSaving(true);
    const fn = type === "style" ? createStyleTemplate : createCraftTemplate;
    await fn({ name, description: desc, prompt_snippet: snippet });
    setSaving(false); onCreated();
  };
  return (
    <div className="fixed inset-0 z-[20000] flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-[460px] max-w-[95vw] max-h-[80vh] overflow-auto rounded-2xl p-6"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "0 24px 64px rgba(0,0,0,0.5)" }}>
        <h3 className="font-semibold mb-4" style={{ color: "var(--text-1)" }}>
          {type === "style" ? "🎨 新建文风模板" : "📐 新建写作方法模板"}
        </h3>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="模板名称"
          className="w-full text-sm px-3 py-2 rounded-lg mb-3 outline-none"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
        <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="简短描述"
          className="w-full text-sm px-3 py-2 rounded-lg mb-3 outline-none"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
        <textarea value={snippet} onChange={e => setSnippet(e.target.value)} rows={8}
          placeholder="Prompt 文本（注入 AI 写作指令）"
          className="w-full text-sm px-3 py-2 rounded-lg mb-4 outline-none resize-none"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-1)", fontFamily: "monospace" }} />
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="text-sm px-4 py-2 rounded-lg border-0 cursor-pointer" style={{ background: "transparent", color: "var(--text-3)" }}>取消</button>
          <button onClick={save} disabled={saving || !name.trim() || !snippet.trim()}
            className="text-sm px-4 py-2 rounded-lg border-0 cursor-pointer font-medium disabled:opacity-30"
            style={{ background: "var(--accent)", color: "var(--bg-base)" }}>{saving ? "保存中…" : "创建"}</button>
        </div>
      </div>
    </div>
  );
}
