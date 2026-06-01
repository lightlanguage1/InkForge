import { useState, useRef, type DragEvent, type ChangeEvent } from "react";

interface Props {
  onFile: (file: File) => void;
  accept?: string;
  loading?: boolean;
  uploading?: boolean;
  progress?: number;
  placeholder?: string;
}

export function DropZone({ onFile, accept = ".txt", loading, uploading, progress, placeholder = "拖拽 .txt 文件到此处，或点击选择" }: Props) {
  const [hover, setHover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = loading || uploading;

  const handleFile = (file: File) => {
    if (file && !busy) onFile(file);
  };

  return (
    <div
      onClick={() => { if (!busy) inputRef.current?.click(); }}
      onDragOver={(e: DragEvent) => { e.preventDefault(); if (!busy) setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={(e: DragEvent) => { e.preventDefault(); setHover(false); handleFile(e.dataTransfer.files[0]); }}
      className="flex flex-col items-center justify-center gap-2 p-8 rounded-xl cursor-pointer transition-all duration-150 border-2 border-dashed text-center"
      style={{
        background: busy ? "var(--bg-raised)" : hover ? "rgba(200,151,90,0.06)" : "var(--bg-raised)",
        borderColor: busy ? "var(--border)" : hover ? "var(--accent)" : "var(--border)",
        cursor: busy ? "not-allowed" : "pointer",
        opacity: busy ? 0.7 : 1,
      }}
    >
      {uploading ? (
        <div className="flex flex-col items-center gap-3 w-full max-w-xs">
          <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-surface)" }}>
            <div className="h-full rounded-full transition-all duration-300" style={{ width: `${progress ?? 0}%`, background: "var(--accent)" }} />
          </div>
          <span className="text-xs" style={{ color: "var(--text-2)" }}>上传中 {progress ?? 0}%</span>
        </div>
      ) : loading ? (
        <div className="flex flex-col items-center gap-3">
          <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
          <span className="text-sm" style={{ color: "var(--text-2)" }}>解析中，请稍候...</span>
        </div>
      ) : (
        <>
          <div className="text-2xl" style={{ color: hover ? "var(--accent)" : "var(--text-3)" }}>
            {hover ? "📂" : "📁"}
          </div>
          <span className="text-sm" style={{ color: "var(--text-2)" }}>{placeholder}</span>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        disabled={busy}
        onChange={(e: ChangeEvent<HTMLInputElement>) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
      />
    </div>
  );
}
