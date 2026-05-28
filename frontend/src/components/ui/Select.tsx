interface Props {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}

export function Select({ label, value, onChange, options }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-3)" }}>
          {label}
        </label>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md px-3 py-2 text-sm transition-all duration-150 focus:outline-none"
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
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} style={{ background: "var(--bg-surface)", color: "var(--text-1)" }}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
