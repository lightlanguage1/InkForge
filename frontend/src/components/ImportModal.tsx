import { useState } from "react";
import { Modal } from "./ui/Modal";
import { post } from "../api/client";
import { DropZone } from "./DropZone";

interface Entity {
  type: string;
  args: Record<string, unknown>;
}

interface Props {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onImported: () => void;
}

const TYPE_LABELS: Record<string, string> = { character: "角色", location: "地点", faction: "阵营" };

export function ImportModal({ open, projectId, onClose, onImported }: Props) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<"input" | "preview" | "done">("input");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [result, setResult] = useState<{ imported?: { name: string; tool: string }[]; total?: number; message?: string } | null>(null);
  const [error, setError] = useState("");

  const reset = () => { setText(""); setError(""); setEntities([]); setResult(null); setStep("input"); onClose(); };

  /** Step 1: 识别 */
  const handlePreview = async () => {
    if (!text.trim()) { setError("请粘贴文档内容"); return; }
    setLoading(true); setError("");
    try {
      const r = await post<{ preview: boolean; entities: Entity[] }>(
        `/v1/project/${projectId}/import`, { content: text, confirm: false }
      );
      if (r.entities?.length) {
        setEntities(r.entities);
        setStep("preview");
      } else {
        setError("未识别到可导入的实体");
      }
    } catch (e: any) { setError(e?.message || "识别失败"); }
    finally { setLoading(false); }
  };

  /** Step 2: 确认导入 */
  const handleConfirm = async () => {
    setLoading(true);
    try {
      const r = await post<{ preview: boolean; imported: { name: string; tool: string }[]; total: number; message: string }>(
        `/v1/project/${projectId}/import`, { confirm: true, entities }
      );
      setResult(r);
      setStep("done");
      if (r.imported?.length) onImported();
    } catch (e: any) { setError(e?.message || "导入失败"); }
    finally { setLoading(false); }
  };

  /** 编辑单个实体的字段 */
  const updateEntity = (idx: number, key: string, value: unknown) => {
    setEntities(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], args: { ...next[idx].args, [key]: value } };
      return next;
    });
  };

  /** 删除单个实体 */
  const removeEntity = (idx: number) => {
    setEntities(prev => prev.filter((_, i) => i !== idx));
  };

  return (
    <Modal open={open} onClose={reset} wide>
      <div className="p-5 space-y-3" style={{ maxHeight: "80vh", overflow: "auto" }}>
        <h2 className="font-semibold text-base" style={{ color: "var(--text-1)" }}>
          {step === "input" ? "导入设定" : step === "preview" ? `识别到 ${entities.length} 个实体` : "导入完成"}
        </h2>

        {step === "input" && (
          <>
            <p className="text-xs" style={{ color: "var(--text-3)" }}>
              粘贴 MD/TXT 文档，AI 自动识别角色、地点、阵营。
            </p>
            <DropZone accept=".md,.txt" onFile={async (file) => { setText(await file.text()); setError(""); }}
              placeholder="拖拽 .md/.txt 文件到这里，或点击选择" />
            <textarea value={text} onChange={e => setText(e.target.value)}
              placeholder="或直接粘贴内容..."
              rows={8}
              className="w-full text-sm px-3 py-2 rounded-lg outline-none resize-none"
              style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-1)" }}
            />
            {error && <p className="text-xs px-3 py-2 rounded" style={{ background: "rgba(248,113,113,0.1)", color: "#f87171" }}>{error}</p>}
            <div className="flex gap-2 justify-end">
              <button onClick={reset} className="px-4 py-2 rounded-lg text-xs" style={{ border: "1px solid var(--border)", color: "var(--text-3)" }}>取消</button>
              <button onClick={handlePreview} disabled={loading}
                className="px-4 py-2 rounded-lg text-xs font-medium" style={{ background: "var(--accent)", color: "var(--bg-base)", opacity: loading ? 0.5 : 1 }}>
                {loading ? "识别中…" : "开始识别"}
              </button>
            </div>
          </>
        )}

        {step === "preview" && (
          <>
            <p className="text-xs" style={{ color: "var(--text-3)" }}>确认并修改识别结果，勾选要导入的实体：</p>
            <div className="space-y-3 max-h-96 overflow-auto">
              {entities.map((e, idx) => (
                <div key={idx} className="p-3 rounded-lg" style={{ border: "1px solid var(--border)", background: "var(--bg-raised)" }}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ background: "var(--accent)", color: "var(--bg-base)" }}>
                      {TYPE_LABELS[e.type] || e.type}
                    </span>
                    <button onClick={() => removeEntity(idx)}
                      className="text-xs px-2 py-0.5 rounded" style={{ color: "#f87171", border: "1px solid rgba(248,113,113,0.3)" }}>删除</button>
                  </div>
                  {Object.entries(e.args).map(([key, val]) => (
                    <div key={key} className="flex gap-2 items-center mb-1.5">
                      <span className="text-xs flex-shrink-0" style={{ color: "var(--text-3)", width: 40 }}>{key}</span>
                      {Array.isArray(val) ? (
                        <input value={(val as string[]).join(", ")}
                          onChange={ev => updateEntity(idx, key, ev.target.value.split(/[,，]/).map(s => s.trim()).filter(Boolean))}
                          className="flex-1 text-xs px-2 py-1 rounded outline-none"
                          style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
                      ) : (
                        <input value={String(val ?? "")}
                          onChange={ev => updateEntity(idx, key, ev.target.value)}
                          className="flex-1 text-xs px-2 py-1 rounded outline-none"
                          style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
            {error && <p className="text-xs px-3 py-2 rounded" style={{ background: "rgba(248,113,113,0.1)", color: "#f87171" }}>{error}</p>}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setStep("input")} className="px-4 py-2 rounded-lg text-xs" style={{ border: "1px solid var(--border)", color: "var(--text-3)" }}>返回</button>
              <button onClick={handleConfirm} disabled={loading || entities.length === 0}
                className="px-4 py-2 rounded-lg text-xs font-medium" style={{ background: "#4daa85", color: "#fff", opacity: (loading || entities.length === 0) ? 0.5 : 1 }}>
                {loading ? "导入中…" : `确认导入 (${entities.length})`}
              </button>
            </div>
          </>
        )}

        {step === "done" && (
          <>
            {result?.imported && result.imported.length > 0 ? (
              <>
                <p className="text-xs" style={{ color: "#4daa85" }}>✅ 成功导入 {result.imported.length}/{result.total}：</p>
                <div className="max-h-48 overflow-auto space-y-1">
                  {result.imported.map((e, i) => (
                    <div key={i} className="text-xs px-3 py-1.5 rounded flex justify-between" style={{ background: "var(--bg-raised)" }}>
                      <span style={{ color: "var(--text-1)" }}>{e.name}</span>
                      <span style={{ color: "var(--text-3)" }}>{TYPE_LABELS[e.tool] || e.tool}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-xs" style={{ color: "var(--text-3)" }}>{result?.message || "无实体导入"}</p>
            )}
            <div className="flex justify-end">
              <button onClick={reset} className="px-4 py-2 rounded-lg text-xs" style={{ background: "var(--accent)", color: "var(--bg-base)" }}>完成</button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
