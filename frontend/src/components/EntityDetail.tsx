import { Card } from "./ui/Card";

interface Props {
  data: Record<string, unknown>;
  onClose: () => void;
  title?: string;
}

export function EntityDetail({ data, onClose, title }: Props) {
  return (
    <Card className="w-96 h-full overflow-auto flex-shrink-0">
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <h3 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>
          {title || String(data.name || data.id || "")}
        </h3>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded-md text-lg leading-none transition-colors duration-150"
          style={{ color: "var(--text-3)" }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.color = "var(--text-1)";
            (e.currentTarget as HTMLElement).style.background = "var(--bg-raised)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.color = "var(--text-3)";
            (e.currentTarget as HTMLElement).style.background = "";
          }}
        >
          &times;
        </button>
      </div>
      <div className="p-4 space-y-3 text-sm">
        {Object.entries(data).map(([key, value]) => {
          if (key === "name" || key === "id") return null;
          return (
            <div key={key}>
              <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-3)" }}>{key}</span>
              <div className="mt-0.5">
                {typeof value === "string" ? (
                  <span style={{ color: "var(--text-2)" }}>{value}</span>
                ) : Array.isArray(value) ? (
                  <span style={{ color: "var(--text-2)" }}>{value.join(", ") || "—"}</span>
                ) : typeof value === "object" && value !== null ? (
                  <pre
                    className="text-xs p-2 rounded mt-1 overflow-auto max-h-32"
                    style={{ background: "var(--pre-bg)", border: "1px solid var(--border)", color: "var(--text-2)" }}
                  >
                    {JSON.stringify(value, null, 2)}
                  </pre>
                ) : (
                  <span style={{ color: "var(--text-2)" }}>{String(value ?? "—")}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
