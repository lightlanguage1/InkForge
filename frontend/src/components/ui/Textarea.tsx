interface Props {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}

export function Textarea({ label, value, onChange, placeholder, rows = 4 }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-3)" }}>
          {label}
        </label>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full rounded-md px-3 py-2 text-sm resize-y transition-all duration-150 focus:outline-none"
        style={{
          background: "var(--bg-raised)",
          border: "1px solid var(--border)",
          color: "var(--text-1)",
          boxShadow: "inset 0 1px 2px rgba(0,0,0,0.08)",
        }}
        onFocus={(e) => {
          (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
          (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 2px rgba(200,151,90,0.12)";
        }}
        onBlur={(e) => {
          (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
          (e.currentTarget as HTMLElement).style.boxShadow = "inset 0 1px 2px rgba(0,0,0,0.08)";
        }}
      />
    </div>
  );
}
