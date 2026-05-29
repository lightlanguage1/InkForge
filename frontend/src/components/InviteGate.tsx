import { useState } from "react";
import { post } from "../api/client";

const LS_TOKEN = "inkforge_token";

export function getToken(): string | null {
  return localStorage.getItem(LS_TOKEN);
}

export function clearToken() {
  localStorage.removeItem(LS_TOKEN);
}

interface Props {
  onActivated: (token: string) => void;
}

export function InviteGate({ onActivated }: Props) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!code.trim()) { setError("请输入邀请码"); return; }
    if (!name.trim()) { setError("请给自己起一个名字"); return; }

    setLoading(true);
    try {
      const data = await post<{ token: string; user_id: string; display_name: string }>(
        "/v1/auth/activate",
        { invite_code: code.trim(), display_name: name.trim() }
      );
      localStorage.setItem(LS_TOKEN, data.token);
      onActivated(data.token);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "激活失败";
      setError(msg.replace(/[{}"]/g, "").replace("detail:", "").trim() || msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "var(--bg-base)",
    }}>
      <div style={{
        width: "100%", maxWidth: 400, padding: "40px 32px",
        background: "var(--bg-surface)", borderRadius: 16,
        border: "1px solid var(--border)",
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: "var(--text-1)",
            letterSpacing: "-0.02em", marginBottom: 4 }}>
            InkForge
          </h1>
          <p style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.6 }}>
            内测邀请制 · 请使用邀请码激活
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{
              display: "block", fontSize: 12, fontWeight: 600,
              color: "var(--text-2)", marginBottom: 6, letterSpacing: "0.04em",
            }}>
              邀请码
            </label>
            <input
              type="text"
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              placeholder="IF-XXXXXXXX"
              maxLength={12}
              autoFocus
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 10,
                background: "var(--bg-raised)", border: "1px solid var(--border)",
                color: "var(--text-1)", fontSize: 16, fontFamily: "monospace",
                letterSpacing: "0.08em", outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div>
            <label style={{
              display: "block", fontSize: 12, fontWeight: 600,
              color: "var(--text-2)", marginBottom: 6, letterSpacing: "0.04em",
            }}>
              你的笔名
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="给自己起个名字"
              maxLength={30}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 10,
                background: "var(--bg-raised)", border: "1px solid var(--border)",
                color: "var(--text-1)", fontSize: 15, outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <p style={{
              fontSize: 12, color: "#f87171", padding: "8px 12px",
              borderRadius: 8, background: "rgba(248,113,113,0.08)",
            }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%", padding: "12px 0", borderRadius: 10,
              background: loading ? "var(--bg-raised)" : "var(--accent)",
              color: loading ? "var(--text-3)" : "var(--bg-base)",
              fontSize: 15, fontWeight: 600, border: "none", cursor: "pointer",
              marginTop: 4,
            }}
          >
            {loading ? "激活中…" : "进入 InkForge"}
          </button>
        </form>
      </div>
    </div>
  );
}
