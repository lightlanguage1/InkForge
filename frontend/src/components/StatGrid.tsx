interface StatItem {
  label: string;
  value: string | number;
}

export function StatGrid({ stats }: { stats: StatItem[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((s) => (
        <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-2xl font-bold text-indigo-600">{s.value}</p>
          <p className="text-sm text-gray-500">{s.label}</p>
        </div>
      ))}
    </div>
  );
}
