import { useState } from "react";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { Textarea } from "./ui/Textarea";
import { Modal } from "./ui/Modal";
import { Toggle } from "./ui/Toggle";
import { Checkbox } from "./ui/Checkbox";
import type { CreateProjectReq } from "../types/project";

/* ── Display constants ──────────────────────────────── */
const STEP_META = [
  { label: "故事基础", desc: "为你的故事起个响亮的名字，选定类型与主线前提" },
  { label: "世界设定", desc: "定义故事的世界观、基调与情节驱动模式" },
  { label: "写作技能", desc: "加载风格技能，让 AI 模仿你最爱的叙事腔调" },
];
const STEP_ACCENT_COLORS = ["#c8975a", "#5a96c8", "#4daa85"];
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
  const [form, setForm] = useState<CreateProjectReq>({ name: "", genre: "", premise: "", setting: "", tone: "" });
  const [step, setStep] = useState(0);
  const [showCustomGenre, setShowCustomGenre] = useState(false);

  const accent = STEP_ACCENT_COLORS[step];

  function resetAndClose() {
    setStep(0);
    setForm({ name: "", genre: "", premise: "", setting: "", tone: "" });
    setShowCustomGenre(false);
    onClose();
  }

  function selectGenre(g: string) {
    setForm({ ...form, genre: g });
    setShowCustomGenre(false);
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
      <div className="flex min-h-[420px]">

        {/* Left: step sidebar */}
        <div
          className="w-52 flex-shrink-0 flex flex-col justify-between p-6 transition-colors duration-300"
          style={{ background: "rgba(240,236,226,0.03)", borderRight: "1px solid rgba(240,236,226,0.06)" }}
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
              selectGenre={selectGenre}
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
  selectGenre: (g: string) => void;
  onNext: () => void;
  onSkip: () => void;
  loading: boolean;
}

function StepBasics({ form, setForm, showCustomGenre, setShowCustomGenre, selectGenre, onNext, onSkip, loading }: StepBasicsProps) {
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
            <GenrePill key={g} label={g} selected={form.genre === g} onSelect={() => selectGenre(g)} />
          ))}
          <button
            type="button"
            onClick={() => { setShowCustomGenre(!showCustomGenre); if (!showCustomGenre) setForm({ ...form, genre: "" }); }}
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
            value={GENRES.includes(form.genre ?? "") ? "" : (form.genre ?? "")}
            onChange={(e) => setForm({ ...form, genre: e.target.value })}
            placeholder="输入自定义类型..."
            autoFocus
            className="mt-2 w-full text-sm px-3 py-2 rounded-lg focus:outline-none transition-colors"
            style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-1)", caretColor: "var(--accent)" }}
            onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
          />
        )}
      </div>

      <Textarea label="故事前提" value={form.premise ?? ""} onChange={(v) => setForm({ ...form, premise: v })}
        placeholder="一两句话描述故事的核心设定和冲突..." rows={3} />

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
      <Input label="背景设定" value={form.setting ?? ""} onChange={(v) => setForm({ ...form, setting: v })}
        placeholder="古代仙侠世界 / 近未来都市 / 架空大陆..." />

      <div>
        <label className="block text-[11px] font-semibold uppercase tracking-wider mb-2.5" style={{ color: "var(--text-3)" }}>
          故事基调
        </label>
        <div className="grid grid-cols-2 gap-2">
          {TONES.map((t) => (
            <ToneCard key={t.label} tone={t} selected={form.tone === t.label}
              onSelect={() => setForm({ ...form, tone: form.tone === t.label ? "" : t.label })} />
          ))}
        </div>
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
  onCreate: () => void;
  loading: boolean;
}

function StepSkills({ form, skills, toggleSkill, onBack, onCreate, loading }: StepSkillsProps) {
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
        <Button size="sm" onClick={onCreate} loading={loading} disabled={!form.name}>创建项目</Button>
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
