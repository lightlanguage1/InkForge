interface Props {
  checked: boolean;
}

export function Checkbox({ checked }: Props) {
  return (
    <div
      className="w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all duration-150"
      style={{
        background: checked ? "#c8975a" : "transparent",
        borderColor: checked ? "#c8975a" : "rgba(240,236,226,0.2)",
      }}
    >
      {checked && (
        <span className="text-[11px] font-bold leading-none" style={{ color: "#0e0c09" }}>✓</span>
      )}
    </div>
  );
}
