import { Outlet, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Sidebar } from "../components/Sidebar";
import { Spinner } from "../components/ui/Spinner";
import { getStatus } from "../api/status";

export function ProjectLayout() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["status", id],
    queryFn: () => getStatus(id!),
    enabled: !!id,
  });

  if (isLoading) return (
    <div className="flex items-center justify-center h-screen" style={{ background: "var(--bg-base)" }}>
      <Spinner />
    </div>
  );
  if (!data) return (
    <div className="flex items-center justify-center h-screen text-sm" style={{ background: "var(--bg-base)", color: "var(--text-2)" }}>
      项目未找到
    </div>
  );

  return (
    <div className="flex h-screen" style={{ background: "var(--bg-base)" }}>
      <Sidebar projectName={data.novel_name} tick={data.current_tick} />
      <main className="flex-1 overflow-auto transition-colors duration-300" style={{ background: "var(--bg-base)" }}>
        <div className="p-8 animate-fade-in h-full">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
