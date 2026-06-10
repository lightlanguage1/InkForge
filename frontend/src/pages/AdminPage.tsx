import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get } from "../api/client";
import { clearToken, isAdmin } from "../components/LoginGate";
import { useNavigate } from "react-router-dom";

interface User { user_id: string; display_name: string; is_admin: number; disabled: number; created_at: string; last_seen: string; project_count: number; }
interface Code { code: string; max_uses: number; used: number; created_at: string; expires_at: string | null; used_by: string | null; strict_expiry: number; }

function useAdminQuery<T>(path: string, key: string[]) {
  const token = localStorage.getItem("inkforge_token");
  return useQuery<T>({ queryKey: key, queryFn: () => get<T>(`/v1/admin${path}`), enabled: !!token });
}

export function AdminPage() {
  const navigate = useNavigate();
  if (!isAdmin()) { navigate("/"); return null; }
  const qc = useQueryClient();
  const [tab, setTab] = useState<"users" | "codes" | "stats" | "logs">("users");
  const [logService, setLogService] = useState("backend");
  const [logLines, setLogLines] = useState(100);
  const [logs, setLogs] = useState("");
  const [logLoading, setLogLoading] = useState(false);

  const fetchLogs = async () => {
    setLogLoading(true);
    try {
      const token = localStorage.getItem("inkforge_token");
      const r = await fetch(`/api/v1/admin/logs?service=${logService}&lines=${logLines}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      setLogs(d.logs || d.error || "无日志");
    } catch { setLogs("获取失败"); }
    setLogLoading(false);
  };
  const [genCount, setGenCount] = useState(5);
  const [genUses, setGenUses] = useState(1);
  const [genDays, setGenDays] = useState(30);
  const [msg, setMsg] = useState("");
  const [editExpiryCode, setEditExpiryCode] = useState<string | null>(null);
  const [editExpiryDays, setEditExpiryDays] = useState(30);

  const { data: usersRes } = useAdminQuery<{ users: User[] }>("/users", ["admin", "users"]);
  const { data: codesRes } = useAdminQuery<{ codes: Code[] }>("/codes", ["admin", "codes"]);
  const { data: stats } = useAdminQuery<{ total_users: number; active_users: number; total_projects: number; available_codes: number }>("/stats", ["admin", "stats"]);
  const users = usersRes?.users ?? [];
  const codes = codesRes?.codes ?? [];

  const api = (method: string, path: string, body?: unknown) => {
    const token = localStorage.getItem("inkforge_token");
    return fetch(`/api/v1/admin${path}`, {
      method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: body ? JSON.stringify(body) : undefined,
    }).then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.detail || "error"); }); return r.json(); });
  };

  const toggleUser = async (uid: string, disabled: boolean) => {
    await api("PATCH", `/users/${uid}?disabled=${disabled}`);
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
  };
  const resetPw = async (uid: string) => {
    const r = await api("POST", `/users/${uid}/reset-password`);
    alert(`用户 ${r.display_name} 的新密码：${r.new_password}`);
    setMsg(`已重置 ${r.display_name} 的密码`);
  };
  const generateCodes = async () => {
    await api("POST", "/codes", { count: genCount, max_uses: genUses, days: genDays });
    qc.invalidateQueries({ queryKey: ["admin", "codes"] });
    qc.invalidateQueries({ queryKey: ["admin", "stats"] });
    setMsg(`已生成 ${genCount} 个邀请码`);
  };
  const revokeCode = async (code: string) => {
    if (!confirm(`作废邀请码 ${code}？`)) return;
    await api("DELETE", `/codes/${code}`);
    qc.invalidateQueries({ queryKey: ["admin", "codes"] });
  };

  const updateExpiry = async (code: string, days: number) => {
    await api("PATCH", `/codes/${code}`, { days });
    setEditExpiryCode(null);
    qc.invalidateQueries({ queryKey: ["admin", "codes"] });
    setMsg(`邀请码 ${code} 过期时间已更新`);
  };

  const toggleStrict = async (code: string) => {
    const r = await api("POST", `/codes/${code}/toggle-strict`);
    qc.invalidateQueries({ queryKey: ["admin", "codes"] });
    setMsg(`邀请码 ${code}: ${(r as any).label}`);
  };

  const tabStyle = (t: string) => ({
    padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 500,
    background: tab === t ? "var(--accent)" : "transparent",
    color: tab === t ? "var(--bg-base)" : "var(--text-3)",
    border: tab === t ? "none" : "1px solid var(--border)",
  } as const);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: "var(--text-1)" }}>管理面板</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => navigate("/")} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", color: "var(--text-2)", fontSize: 12, cursor: "pointer" }}>返回首页</button>
          <button onClick={() => { clearToken(); navigate("/"); window.location.reload(); }} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", color: "var(--text-3)", fontSize: 12, cursor: "pointer" }}>退出</button>
        </div>
      </div>
      {msg && <div style={{ padding: "8px 14px", borderRadius: 8, background: "rgba(77,170,133,0.1)", color: "#4daa85", fontSize: 12, marginBottom: 16 }}>{msg}</div>}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <button style={tabStyle("users")} onClick={() => setTab("users")}>用户</button>
        <button style={tabStyle("codes")} onClick={() => setTab("codes")}>邀请码</button>
        <button style={tabStyle("stats")} onClick={() => setTab("stats")}>概览</button>
        <button style={tabStyle("logs")} onClick={() => { setTab("logs"); fetchLogs(); }}>日志</button>
      </div>

      {tab === "users" && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["用户名","项目","注册时间","最近活跃","状态","操作"].map(h => <th key={h} style={{ textAlign: "left", padding: "8px 10px", color: "var(--text-3)", fontWeight: 500, fontSize: 11 }}>{h}</th>)}
          </tr></thead>
          <tbody>
            {users?.map(u => (
              <tr key={u.user_id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "10px", color: "var(--text-1)" }}>{u.display_name}{u.is_admin ? " ⚡" : ""}</td>
                <td style={{ padding: "10px", color: "var(--text-2)" }}>{u.project_count}</td>
                <td style={{ padding: "10px", color: "var(--text-3)", fontSize: 11 }}>{u.created_at?.slice(0, 10)}</td>
                <td style={{ padding: "10px", color: "var(--text-3)", fontSize: 11 }} title={u.last_seen}>{u.last_seen?.replace("T", " ").slice(0, 16)}</td>
                <td style={{ padding: "10px" }}><span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10, background: u.disabled ? "rgba(248,113,113,0.1)" : "rgba(77,170,133,0.1)", color: u.disabled ? "#f87171" : "#4daa85" }}>{u.disabled ? "已禁用" : "活跃"}</span></td>
                <td style={{ padding: "10px", display: "flex", gap: 6 }}>
                  <button onClick={() => resetPw(u.user_id)} style={{ padding: "3px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "transparent", color: "var(--text-2)", fontSize: 11, cursor: "pointer" }}>重置密码</button>
                  <button onClick={() => toggleUser(u.user_id, !u.disabled)} style={{ padding: "3px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "transparent", color: u.disabled ? "#4daa85" : "#f87171", fontSize: 11, cursor: "pointer" }}>{u.disabled ? "启用" : "禁用"}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "codes" && (
        <div>
          <div style={{ display: "flex", gap: 10, marginBottom: 24, alignItems: "end" }}>
            <div><label style={{ fontSize: 11, color: "var(--text-3)", display: "block", marginBottom: 4 }}>数量</label><input type="number" value={genCount} onChange={e => setGenCount(+e.target.value)} min={1} max={50} style={{ width: 60, padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-raised)", color: "var(--text-1)", fontSize: 13 }} /></div>
            <div><label style={{ fontSize: 11, color: "var(--text-3)", display: "block", marginBottom: 4 }}>次数</label><input type="number" value={genUses} onChange={e => setGenUses(+e.target.value)} min={1} max={10} style={{ width: 60, padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-raised)", color: "var(--text-1)", fontSize: 13 }} /></div>
            <div><label style={{ fontSize: 11, color: "var(--text-3)", display: "block", marginBottom: 4 }}>天数</label><input type="number" value={genDays} onChange={e => setGenDays(+e.target.value)} min={1} max={999} style={{ width: 60, padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-raised)", color: "var(--text-1)", fontSize: 13 }} /></div>
            <button onClick={generateCodes} style={{ padding: "7px 16px", borderRadius: 8, background: "var(--accent)", color: "var(--bg-base)", border: "none", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>生成</button>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["邀请码","已用/上限","使用者","过期时间","严格","操作"].map(h => <th key={h} style={{ textAlign: "left", padding: "8px 10px", color: "var(--text-3)", fontWeight: 500, fontSize: 11 }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {codes?.map(c => (
                <tr key={c.code} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "10px", color: "var(--text-1)", fontFamily: "monospace", fontSize: 12 }}>{c.code}</td>
                  <td style={{ padding: "10px", color: "var(--text-2)" }}>{c.used}/{c.max_uses}</td>
                  <td style={{ padding: "10px", color: "var(--text-2)" }}>{c.used_by || "—"}</td>
                  <td style={{ padding: "10px", color: "var(--text-3)", fontSize: 11 }}>
                    {editExpiryCode === c.code ? (
                      <span style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
                        <input type="number" value={editExpiryDays}
                          onChange={e => setEditExpiryDays(+e.target.value)}
                          min={0} max={9999}
                          style={{ width: 50, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--accent)", background: "var(--bg-base)", color: "var(--text-1)", fontSize: 11 }} />
                        <span style={{ fontSize: 10, color: "var(--text-3)" }}>天</span>
                        <button onClick={() => updateExpiry(c.code, editExpiryDays)}
                          style={{ padding: "2px 8px", borderRadius: 4, border: "none", background: "var(--accent)", color: "var(--bg-base)", fontSize: 10, cursor: "pointer" }}>确认</button>
                        <button onClick={() => setEditExpiryCode(null)}
                          style={{ padding: "2px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "transparent", color: "var(--text-3)", fontSize: 10, cursor: "pointer" }}>✕</button>
                      </span>
                    ) : (
                      <span onClick={() => { setEditExpiryCode(c.code); setEditExpiryDays(30); }}
                        style={{ cursor: "pointer", borderBottom: "1px dashed var(--text-3)" }}
                        title="点击修改过期时间">
                        {c.expires_at?.slice(0, 10) || "永不过期"}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "10px" }}>
                    <button onClick={() => toggleStrict(c.code)}
                      style={{ padding: "2px 8px", borderRadius: 10, border: "none", fontSize: 10, cursor: "pointer",
                        background: c.strict_expiry ? "rgba(248,113,113,0.1)" : "rgba(77,170,133,0.1)",
                        color: c.strict_expiry ? "#f87171" : "#4daa85" }}
                      title="严格过期：过期后已注册用户也拦截">
                      {c.strict_expiry ? "严格" : "宽松"}
                    </button>
                  </td>
                  <td style={{ padding: "10px" }}><button onClick={() => revokeCode(c.code)} style={{ padding: "3px 10px", borderRadius: 6, border: "1px solid rgba(248,113,113,0.3)", background: "transparent", color: "#f87171", fontSize: 11, cursor: "pointer" }}>作废</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "stats" && stats && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 16 }}>
          {[["总用户", stats.total_users], ["活跃用户", stats.active_users], ["总项目", stats.total_projects], ["可用邀请码", stats.available_codes]].map(([label, val]) => (
            <div key={label as string} style={{ padding: 20, borderRadius: 12, background: "var(--bg-surface)", border: "1px solid var(--border)", textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-1)" }}>{val as number}</div>
              <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>{label as string}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "logs" && (
        <div>
          <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "end" }}>
            <select value={logService} onChange={e => setLogService(e.target.value)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-raised)", color: "var(--text-1)", fontSize: 12 }}>
              <option value="backend">后端</option>
              <option value="frontend">前端</option>
            </select>
            <select value={logLines} onChange={e => setLogLines(+e.target.value)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-raised)", color: "var(--text-1)", fontSize: 12 }}>
              <option value={50}>50 行</option>
              <option value={100}>100 行</option>
              <option value={200}>200 行</option>
              <option value={500}>500 行</option>
            </select>
            <button onClick={fetchLogs} disabled={logLoading} style={{ padding: "7px 16px", borderRadius: 8, background: "var(--accent)", color: "var(--bg-base)", border: "none", fontSize: 13, cursor: "pointer" }}>
              {logLoading ? "加载中…" : "刷新"}
            </button>
          </div>
          <pre style={{ padding: 16, borderRadius: 10, background: "#0d1117", color: "#c9d1d9", fontSize: 11, fontFamily: "monospace", lineHeight: 1.6, maxHeight: "70vh", overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
            {logs || "点击刷新加载日志"}
          </pre>
        </div>
      )}
    </div>
  );
}
