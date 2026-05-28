import type { WritingTheme } from "../../types/theme";

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  theme: WritingTheme;
}

export function ThemedTextarea({ label, value, onChange, placeholder, rows = 4, theme: t }: Props) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1.5 transition-colors duration-300" style={{ color: t.text3 }}>
        {label}
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full rounded-md px-3 py-2 text-sm resize-none focus:outline-none transition-all duration-300"
        style={{
          background: t.preBg,
          border: `1px solid ${t.cardBorder}`,
          color: t.text,
          boxShadow: "inset 0 1px 2px rgba(0,0,0,0.08)",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = t.accent;
          e.currentTarget.style.boxShadow = `0 0 0 2px ${t.accent}22`;
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = t.cardBorder;
          e.currentTarget.style.boxShadow = "inset 0 1px 2px rgba(0,0,0,0.08)";
        }}
      />
    </div>
  );
}
