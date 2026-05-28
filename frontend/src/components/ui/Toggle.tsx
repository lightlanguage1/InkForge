interface Props {
  checked: boolean;
  onChange: (v: boolean) => void;
}

export function Toggle({ checked, onChange }: Props) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="relative w-10 h-6 rounded-full transition-colors duration-200 flex-shrink-0"
      style={{ background: checked ? "var(--accent)" : "var(--bg-raised)", border: "1px solid var(--border)" }}
    >
      <span
        className="absolute top-1 w-4 h-4 rounded-full shadow-sm transition-all duration-200"
        style={{
          background: checked ? "var(--bg-base)" : "var(--text-3)",
          left: checked ? "1.25rem" : "0.25rem",
        }}
      />
    </button>
  );
}
