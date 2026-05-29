import { Card } from "./ui/Card";

const LABELS: Record<string, string> = {
  type: "类型", created_at: "创建时间", updated_at: "更新时间",
  first_name: "名", family_name: "姓", title: "头衔", nicknames: "昵称",
  role: "角色", description: "描述", backstory: "背景故事",
  status: "状态", status_name: "状态",
  physical_traits: "外貌特征", age: "年龄", appearance: "外貌", distinctive_features: "特征",
  personality: "性格", core_traits: "核心特质", fears: "恐惧", desires: "渴望", flaws: "缺陷",
  relationships: "关系", character_id: "角色ID", relationship_type: "关系类型",
  current_state: "当前状态", location_id: "位置", emotional_state: "情绪状态",
  physical_state: "身体状态", emotion: "情绪", dominant: "主情绪",
  valence: "效价", arousal: "唤醒度", intensity: "强度",
  inventory: "物品", goals: "目标", beliefs: "信念", emotion_history: "情绪历史",
  history: "历史记录", tick: "幕", scene_id: "场景ID", summary: "摘要", changes: "变化",
  appearance_ticks: "出场幕数", last_scene_tick: "最后出场幕", pov_count: "POV次数",
  metadata: "元数据", source_scene_id: "来源场景", importance: "重要度",
  category: "分类", tags: "标签", content: "内容", lore_type: "类型",
  resolution_note: "解决说明", immediate_goals: "即时目标", arc_goal: "弧线目标",
  story_goal: "故事目标", word_count: "字数", pov_character_id: "POV角色",
  characters_present: "出场角色", key_events: "关键事件",
  tension_level: "张力等级", tension_category: "张力类别",
  open_loops_created: "新增线索", open_loops_resolved: "已解决线索",
  atmosphere: "氛围", significance: "意义", sensory_details: "感官细节",
  features: "特征", connections: "连接", connection_type: "连接类型",
};

const SKIP = new Set(["name", "id", "full_name", "suggestion_evidence", "suggestion_confidence"]);

function labelOf(key: string): string { return LABELS[key] || key.replace(/_/g, " "); }
function renderValue(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return v.length === 0 ? "—" : v.map(x => typeof x === "object" ? JSON.stringify(x) : String(x)).join("、");
  return "—";
}
function isSimple(v: unknown) { return typeof v === "string" || typeof v === "number" || typeof v === "boolean" || Array.isArray(v); }

function flattenObject(obj: Record<string, unknown>, prefix = ""): [string, unknown][] {
  const result: [string, unknown][] = [];
  for (const [k, v] of Object.entries(obj)) {
    if (SKIP.has(k)) continue;
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (v === null || v === undefined) continue;
    if (isSimple(v)) { result.push([fullKey, v]); continue; }
    if (typeof v === "object" && !Array.isArray(v)) {
      const entries = Object.entries(v as Record<string, unknown>);
      if (entries.every(([, sv]) => isSimple(sv) || sv === null) && entries.length > 0) {
        for (const [sk, sv] of entries) {
          if (sv === null || sv === undefined) continue;
          result.push([`${labelOf(k)} › ${LABELS[sk] || sk}`, sv]);
        }
      } else { result.push([k, v]); }
    } else { result.push([k, v]); }
  }
  return result;
}

interface Props {
  data: Record<string, unknown>;
  onClose: () => void;
  title?: string;
}

export function EntityDetail({ data, onClose, title }: Props) {
  const fields = flattenObject(data);
  return (
    <Card className="w-96 h-full overflow-y-auto overflow-x-hidden flex-shrink-0 flex flex-col">
      <div className="px-4 py-3 flex items-center justify-between flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <h3 className="font-semibold text-sm truncate mr-2" style={{ color: "var(--text-1)" }}>{title || String(data.name || data.id || "")}</h3>
        <button onClick={onClose} className="w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-md text-lg leading-none transition-colors duration-150" style={{ color: "var(--text-3)" }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = "var(--text-1)"; (e.currentTarget as HTMLElement).style.background = "var(--bg-raised)"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = "var(--text-3)"; (e.currentTarget as HTMLElement).style.background = ""; }}
        >&times;</button>
      </div>
      <div className="p-4 space-y-3 text-sm">
        {fields.map(([key, value]) => (
          <div key={key}>
            <span className="text-xs font-medium tracking-wide" style={{ color: "var(--text-3)" }}>{labelOf(key)}</span>
            <div className="mt-0.5" style={{ color: "var(--text-2)", overflowWrap: "break-word", wordBreak: "break-word" }}>
              {typeof value === "object" && value !== null && !Array.isArray(value)
                ? <pre className="text-xs p-2 rounded mt-1 max-h-32 overflow-y-auto" style={{ background: "var(--pre-bg)", border: "1px solid var(--border)", color: "var(--text-2)", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{JSON.stringify(value, null, 2)}</pre>
                : <span>{renderValue(value)}</span>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
