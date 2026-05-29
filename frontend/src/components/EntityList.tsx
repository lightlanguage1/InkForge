import type { ReactNode } from "react";
import { Card } from "./ui/Card";
import { Spinner } from "./ui/Spinner";
import { Table } from "./ui/Table";

interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => ReactNode;
}

interface Props<T> {
  title: string;
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  onRowClick?: (item: T) => void;
}

export function EntityList<T>({ title, columns, data, loading, onRowClick }: Props<T>) {
  return (
    <Card className="flex-1 flex flex-col overflow-hidden">
      <div
        className="px-4 py-3 flex items-center justify-between flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <h3 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>{title}</h3>
        <span className="text-xs tabular-nums font-mono" style={{ color: "var(--text-3)" }}>{data.length}</span>
      </div>
      <div className="overflow-y-auto flex-1">
        {loading ? <Spinner /> : <Table columns={columns} data={data} onRowClick={onRowClick} />}
      </div>
    </Card>
  );
}
