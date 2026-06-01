import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { DropZone } from "../components/DropZone";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { uploadReference, searchReferences } from "../api/references";
import type { ReferenceSearchResult } from "../types/reference";

export function ReferencesPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ReferenceSearchResult[]>([]);

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const importMut = useMutation({
    mutationFn: async (file: File) => {
      setUploading(true);
      setUploadProgress(0);
      const result = await uploadReference(file, setUploadProgress);
      setUploading(false);
      return result;
    },
    onSuccess: (d) => { alert(`已导入：${d.title}（${d.chunk_count} 块）`); },
  });
  const searchMut = useMutation({ mutationFn: () => searchReferences({ query, top_k: 5 }), onSuccess: (d) => setResults(d.results) });

  return (
    <div className="space-y-6">
      <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>参考文库</h1>

      <Card className="p-4">
        <p className="text-sm mb-3" style={{ color: "var(--text-2)" }}>拖拽外部小说文件，作为写作风格参考</p>
        <DropZone
          onFile={(f) => importMut.mutate(f)}
          uploading={uploading}
          loading={importMut.isPending && !uploading}
          progress={uploadProgress}
          placeholder="拖拽 .txt 小说文件到此处，或点击选择"
        />
      </Card>

      <Card className="p-4">
        <p className="text-sm mb-3" style={{ color: "var(--text-2)" }}>搜索已导入的参考段落</p>
        <div className="flex gap-2">
          <Input value={query} onChange={setQuery} placeholder="搜索关键词" />
          <Button variant="ghost" onClick={() => searchMut.mutate()} loading={searchMut.isPending} disabled={!query}>搜索</Button>
        </div>
        {results.length > 0 && (
          <div className="mt-4 space-y-3">
            {results.map((r, i) => (
              <div key={i} className="p-3 rounded" style={{ background: "var(--bg-raised)" }}>
                <p className="text-xs mb-1" style={{ color: "var(--text-3)" }}>
                  {r.source}{r.chapter ? ` · ${r.chapter}` : ""}{r.relevance != null ? ` · 相关度 ${r.relevance.toFixed(2)}` : ""}
                </p>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-2)" }}>{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
