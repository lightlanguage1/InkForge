import { useState, useRef, type DragEvent, type ChangeEvent } from "react";

interface Props {
  onFile: (file: File) => void;
  accept?: string;
  loading?: boolean;
  progress?: number;
  placeholder?: string;
}

export function DropZone({ onFile, accept = ".txt", loading, progress, placeholder = "拖拽 .txt 文件到此处，或点击选择" }: Props) {
  const [hover, setHover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    if (file) onFile(file);
  };

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e: DragEvent) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={(e: DragEvent) => { e.preventDefault(); setHover(false); handleFile(e.dataTransfer.files[0]); }}
      className="flex flex-col items-center justify-center gap-2 p-8 rounded-xl cursor-pointer transition-all duration-150 border-2 border-dashed text-center"
      style={{
        background: hover ? "rgba(200,151,90,0.06)" : "var(--bg-raised)",
        borderColor: hover ? "var(--accent)" : "var(--border)",
      }}
    >
      {loading ? (
        <div className="flex flex-col items-center gap-3 w-full max-w-xs">
          {progress !== undefined ? (
            <>
              <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-surface)" }}>
                <div className="h-full rounded-full transition-all duration-300" style={{ width: `${progress}%`, background: "var(--accent)" }} />
              </div>
              <span className="text-xs" style={{ color: "var(--text-2)" }}>上传中 {progress}%</span>
            </>
          ) : (
            <>
              <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
              <span className="text-sm" style={{ color: "var(--text-2)" }}>处理中...</span>
            </>
          )}
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
        onChange={(e: ChangeEvent<HTMLInputElement>) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
      />
    </div>
  );
}
