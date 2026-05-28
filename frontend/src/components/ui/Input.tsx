interface Props {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  error?: string;
  type?: string;
}

export function Input({ label, value, onChange, placeholder, error, type = "text" }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-3)" }}>
          {label}
        </label>
      )}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md px-3 py-2 text-sm focus:outline-none transition-all duration-150"
        style={{
          background: error ? "rgba(200,80,80,0.08)" : "var(--bg-raised)",
          border: `1px solid ${error ? "rgba(200,80,80,0.4)" : "var(--border)"}`,
          color: "var(--text-1)",
          boxShadow: "inset 0 1px 2px rgba(0,0,0,0.08)",
        }}
        onFocus={(e) => {
          if (!error) {
            (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
            (e.currentTarget as HTMLElement).style.boxShadow = `0 0 0 2px rgba(200,151,90,0.12)`;
          }
        }}
        onBlur={(e) => {
          if (!error) {
            (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
            (e.currentTarget as HTMLElement).style.boxShadow = "inset 0 1px 2px rgba(0,0,0,0.08)";
          }
        }}
      />
      {error && <p className="text-xs mt-1" style={{ color: "#e07070" }}>{error}</p>}
    </div>
  );
}
