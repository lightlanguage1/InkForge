interface Props {
  value: number;  // 0.0 - 1.0
  label?: string;
}

export function ProgressBar({ value, label }: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="flex items-center gap-2.5">
      {label && <span className="text-xs text-parchment-2 w-20 truncate">{label}</span>}
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(240,236,226,0.08)" }}>
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: "#c8975a" }} />
      </div>
      <span className="text-xs text-parchment-3 w-9 text-right tabular-nums">{pct}%</span>
    </div>
  );
}
