import { type ReactNode } from "react";

interface Props {
  variant?: "primary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
}

export function Button({ variant = "primary", size = "md", disabled, loading, onClick, children, className = "" }: Props) {
  const base = "inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-ink-base active:scale-[0.98]";

  const variants: Record<string, string> = {
    primary: "text-ink-base hover:bg-gold-light focus:ring-gold",
    danger:  "bg-red-900/60 text-red-200 border border-red-800/60 hover:bg-red-800/60 focus:ring-red-700",
    ghost:   "text-parchment-2 hover:text-parchment hover:bg-parchment/[0.06] focus:ring-parchment/20",
  };

  const variantStyles: Record<string, React.CSSProperties> = {
    primary: { background: "#c8975a", color: "#0e0c09" },
    danger:  {},
    ghost:   {},
  };

  const sizes: Record<string, string> = {
    sm: "px-3 py-1.5 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-sm gap-2",
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${disabled || loading ? "opacity-40 cursor-not-allowed" : ""} ${className}`}
      style={variantStyles[variant]}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
