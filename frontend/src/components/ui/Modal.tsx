import { type ReactNode } from "react";

interface Props {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}

export function Modal({ open, title, onClose, children, wide = false }: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 backdrop-blur-sm"
        style={{ background: "rgba(8,6,4,0.72)" }}
        onClick={onClose}
      />
      <div
        className={`relative rounded-2xl w-full mx-4 animate-fade-in flex flex-col max-h-[92vh] overflow-hidden ${wide ? "max-w-2xl" : "max-w-md"}`}
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          boxShadow: "0 24px 80px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.2)",
        }}
      >
        {title && (
          <div
            className="flex items-center justify-between px-6 pt-5 pb-4 flex-shrink-0"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <h2 className="text-base font-semibold" style={{ color: "var(--text-1)" }}>{title}</h2>
            <button
              onClick={onClose}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-lg transition-colors duration-150"
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
        )}
        <div className="overflow-y-auto flex-1">
          {children}
        </div>
      </div>
    </div>
  );
}
