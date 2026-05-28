import { type ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export function Card({ children, className = "", onClick }: Props) {
  return (
    <div
      className={`rounded-xl transition-colors duration-300 ${className}`}
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow)",
      }}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
