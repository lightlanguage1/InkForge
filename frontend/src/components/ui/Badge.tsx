import type { ReactNode } from "react";

interface Props {
  variant?: "default" | "success" | "warning" | "danger" | "info";
  children: ReactNode;
}

export function Badge({ variant = "default", children }: Props) {
  const styles: Record<string, React.CSSProperties> = {
    default: { background: "var(--bg-raised)", color: "var(--text-2)", border: "1px solid var(--border)" },
    success: { background: "rgba(77,170,133,0.15)", color: "#5dbf96", border: "1px solid rgba(77,170,133,0.25)" },
    warning: { background: "rgba(200,151,90,0.15)", color: "#c8975a", border: "1px solid rgba(200,151,90,0.25)" },
    danger:  { background: "rgba(200,80,80,0.15)",  color: "#e07070", border: "1px solid rgba(200,80,80,0.25)" },
    info:    { background: "rgba(90,150,200,0.15)", color: "#7ab0d4", border: "1px solid rgba(90,150,200,0.25)" },
  };

  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={styles[variant]}
    >
      {children}
    </span>
  );
}
