import type { ReactNode } from "react";

interface Column<T> {
  key: string;
  header: string;
  width?: string;
  render?: (item: T) => ReactNode;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (item: T) => void;
}

export function Table<T>({ columns, data, onRowClick }: Props<T>) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr style={{ borderBottom: "1px solid var(--border)" }}>
          {columns.map((c) => (
            <th
              key={c.key}
              className="text-left py-2.5 px-4 text-xs font-medium uppercase tracking-wider"
              style={{ color: "var(--text-3)", width: c.width }}
            >
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => (
          <tr
            key={i}
            className={`transition-colors duration-100 ${onRowClick ? "cursor-pointer" : ""}`}
            style={{ borderBottom: "1px solid var(--border)" }}
            onMouseEnter={(e) => { if (onRowClick) (e.currentTarget as HTMLElement).style.background = "rgba(200,151,90,0.06)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = ""; }}
            onClick={() => onRowClick?.(row)}
          >
            {columns.map((c) => (
              <td key={c.key} className="py-3 px-4" style={{ color: "var(--text-2)" }}>
                {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
