import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { Spinner } from "../components/ui/Spinner";
import { compile, summarize, generateTitles } from "../api/compile";
import { getStatus } from "../api/status";
import { PageHelp } from "../components/PageHelp";

const EXT: Record<string, string> = { markdown: "md", html: "html", prose: "txt" };
const MIME: Record<string, string> = { markdown: "text/markdown", html: "text/html", prose: "text/plain" };

function downloadFile(content: string, format: string, projectId: string) {
  const ext = EXT[format] ?? "txt";
  const mime = MIME[format] ?? "text/plain";
  const blob = new Blob([content], { type: mime + ";charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${projectId}.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

export function CompilePage() {
  const { id } = useParams<{ id: string }>();
  const [format, setFormat] = useState("markdown");
  const [content, setContent] = useState("");
  const [titles, setTitles] = useState<string[]>([]);

  const compileMut = useMutation({ mutationFn: () => compile(id!, { format }), onSuccess: (d) => setContent(d.content) });
  const summaryMut = useMutation({ mutationFn: () => summarize(id!), onSuccess: (d) => setContent(d.content) });
  const titleMut = useMutation({ mutationFn: () => generateTitles(id!, { count: 10 }), onSuccess: (d) => setTitles(d.titles) });
  const { data: status } = useQuery({ queryKey: ["status", id], queryFn: () => getStatus(id!), enabled: !!id });
  const hasScenes = (status?.scene_count ?? 0) > 0;

  return (
    <div className="space-y-6">
      <PageHelp>编译导出 — 将完整故事导出为多种格式（Markdown / HTML / TXT）。支持 AI 自动生成书名建议。</PageHelp>
      <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>编译导出</h1>
      <Card className="p-4">
        <div className="flex gap-3 items-end">
          <Select label="格式" value={format} onChange={setFormat}
            options={[{ value: "markdown", label: "Markdown" }, { value: "html", label: "HTML" }, { value: "prose", label: "纯文本" }]} />
          <Button onClick={() => compileMut.mutate()} loading={compileMut.isPending} disabled={!hasScenes}>编译</Button>
          <Button variant="ghost" onClick={() => summaryMut.mutate()} loading={summaryMut.isPending}>摘要</Button>
          <Button variant="ghost" onClick={() => titleMut.mutate()} loading={titleMut.isPending}>起名</Button>
        </div>
        {!hasScenes && <p className="text-xs mt-2" style={{ color: "var(--text-3)" }}>暂无场景可编译，请先生成内容</p>}
      </Card>

      {titles.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2" style={{ color: "var(--text-1)" }}>书名建议</h3>
          <div className="grid grid-cols-2 gap-1">
            {titles.map((t, i) => <p key={i} className="text-sm" style={{ color: "var(--text-2)" }}>{i + 1}. {t}</p>)}
          </div>
        </Card>
      )}

      {(compileMut.isPending || summaryMut.isPending) ? <Spinner /> : (
        content && (
          <Card className="p-4">
            <div className="flex justify-between mb-2">
              <h3 className="font-semibold" style={{ color: "var(--text-1)" }}>输出</h3>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(content)}>复制</Button>
                <Button size="sm" onClick={() => downloadFile(content, format, id!)}>
                  下载 .{EXT[format] ?? "txt"}
                </Button>
              </div>
            </div>
            <pre className="text-sm whitespace-pre-wrap p-4 rounded-lg max-h-96 overflow-auto"
              style={{ background: "var(--pre-bg)", border: "1px solid var(--border)", color: "var(--text-2)" }}>{content}</pre>
          </Card>
        )
      )}
    </div>
  );
}
