import type { WritingTheme } from "../../types/theme";

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  theme: WritingTheme;
}

export function ThemedSelect({ label, value, onChange, options, theme: t }: Props) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1.5 transition-colors duration-300" style={{ color: t.text3 }}>
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md px-3 py-2 text-sm focus:outline-none transition-all duration-300"
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
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} style={{ background: t.cardBg, color: t.text }}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
