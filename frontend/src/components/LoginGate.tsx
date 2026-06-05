import { useState } from "react";
import { post } from "../api/client";

const LS_TOKEN = "inkforge_token";
const LS_NAME = "inkforge_name";
const LS_ADMIN = "inkforge_admin";

export function getToken(): string | null {
  return localStorage.getItem(LS_TOKEN);
}

export function getSavedName(): string | null {
  return localStorage.getItem(LS_NAME);
}

export function isAdmin(): boolean {
  return localStorage.getItem(LS_ADMIN) === "1";
}

export function clearToken() {
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_NAME);
  localStorage.removeItem(LS_ADMIN);
}

type Mode = "register" | "login" | "reset";

interface Props {
  onActivated: (token: string) => void;
}

const S: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg-base)" },
  card: { width: "100%", maxWidth: 400, padding: "40px 32px", background: "var(--bg-surface)", borderRadius: 16, border: "1px solid var(--border)" },
  logo: { textAlign: "center", marginBottom: 32 },
  title: { fontSize: 28, fontWeight: 700, color: "var(--text-1)", letterSpacing: "-0.02em", marginBottom: 4 },
  sub: { fontSize: 13, color: "var(--text-3)", lineHeight: 1.6 },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  label: { display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-2)", marginBottom: 6, letterSpacing: "0.04em" },
  input: { width: "100%", padding: "10px 14px", borderRadius: 10, background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-1)", fontSize: 15, outline: "none", boxSizing: "border-box" as const },
  btn: { width: "100%", padding: "12px 0", borderRadius: 10, background: "var(--accent)", color: "var(--bg-base)", fontSize: 15, fontWeight: 600, border: "none", cursor: "pointer", marginTop: 4 },
  btnDisabled: { background: "var(--bg-raised)", color: "var(--text-3)" },
  err: { fontSize: 12, color: "#f87171", padding: "8px 12px", borderRadius: 8, background: "rgba(248,113,113,0.08)" },
  ok: { fontSize: 12, color: "#4daa85", padding: "8px 12px", borderRadius: 8, background: "rgba(77,170,133,0.08)" },
  link: { fontSize: 12, color: "var(--text-3)", textAlign: "center", cursor: "pointer", marginTop: 8 },
};
(S.input as any).boxSizing = "border-box";
(S.btn as any).boxSizing = "border-box";

export function LoginGate({ onActivated }: Props) {
  const savedName = getSavedName();
  const [mode, setMode] = useState<Mode>(savedName ? "login" : "register");
  const [code, setCode] = useState("");
  const [name, setName] = useState(savedName || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const reset = () => { setError(""); setMsg(""); };
  const switchTo = (m: Mode) => { setMode(m); reset(); };

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault(); reset();
    if (!code.trim()) { setError("请输入邀请码"); return; }
    if (!name.trim()) { setError("请输入用户名"); return; }
    if (!password || password.length < 4) { setError("密码至少4个字符"); return; }
    setLoading(true);
    try {
      const data = await post<{ token: string; user_id: string; display_name: string; is_admin: number }>(
        "/v1/auth/register", { invite_code: code.trim(), display_name: name.trim(), password }
      );
      localStorage.setItem(LS_TOKEN, data.token);
      localStorage.setItem(LS_NAME, data.display_name);
      localStorage.setItem(LS_ADMIN, String(data.is_admin ?? 0));
      onActivated(data.token);
    } catch (e: unknown) {
      setError(cleanErr(e));
    } finally { setLoading(false); }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault(); reset();
    if (!name.trim()) { setError("请输入用户名"); return; }
    if (!password) { setError("请输入密码"); return; }
    setLoading(true);
    try {
      const data = await post<{ token: string; user_id: string; display_name: string; is_admin: number }>(
        "/v1/auth/login", { display_name: name.trim(), password }
      );
      localStorage.setItem(LS_TOKEN, data.token);
      localStorage.setItem(LS_NAME, data.display_name);
      localStorage.setItem(LS_ADMIN, String(data.is_admin ?? 0));
      onActivated(data.token);
    } catch (e: unknown) {
      setError(cleanErr(e));
    } finally { setLoading(false); }
  }

  async function handleReset(e: React.FormEvent) {
    e.preventDefault(); reset();
    if (!name.trim()) { setError("请输入用户名"); return; }
    if (!code.trim()) { setError("请输入邀请码"); return; }
    if (!password || password.length < 4) { setError("新密码至少4个字符"); return; }
    setLoading(true);
    try {
      await post<{ ok: boolean }>("/v1/auth/reset-password", { display_name: name.trim(), invite_code: code.trim(), new_password: password });
      setMsg("密码重置成功，请返回登录");
    } catch (e: unknown) {
      setError(cleanErr(e));
    } finally { setLoading(false); }
  }

  const buttons = {
    register: { handler: handleRegister, label: "注 册", subtitle: "内测邀请制 · 注册新账户" },
    login: { handler: handleLogin, label: "登 录", subtitle: "欢迎回来" },
    reset: { handler: handleReset, label: "重 置", subtitle: "使用邀请码重设密码" },
  }[mode];

  return (
    <div style={S.wrap}>
      <div style={S.card}>
        <div style={S.logo}>
          <h1 style={S.title}>InkForge</h1>
          <p style={S.sub}>{buttons.subtitle}</p>
        </div>
        <form onSubmit={buttons.handler} style={S.form}>
          {mode !== "login" && (
            <div>
              <label style={S.label}>邀请码</label>
              <input type="text" value={code} onChange={e => setCode(e.target.value.toUpperCase())}
                placeholder="IF-XXXXXXXX" maxLength={12} autoFocus
                style={{...S.input, fontFamily: "monospace", letterSpacing: "0.08em"}} />
            </div>
          )}
          <div>
            <label style={S.label}>用户名</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              placeholder="你的用户名" maxLength={30} autoFocus={mode === "login"}
              style={S.input} />
          </div>
          <div>
            <label style={S.label}>{mode === "reset" ? "新密码" : "密 码"}</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder={mode === "reset" ? "设置新密码" : "输入密码"}
              style={S.input} />
          </div>
          {error && <p style={S.err}>{error}</p>}
          {msg && <p style={S.ok}>{msg}</p>}
          <button type="submit" disabled={loading}
            style={loading ? {...S.btn, ...S.btnDisabled} : S.btn}>
            {loading ? "请稍候…" : buttons.label}
          </button>
        </form>
        <div style={{ marginTop: 16, display: "flex", justifyContent: "center", gap: 16 }}>
          {mode !== "register" && <span style={S.link} onClick={() => switchTo("register")}>→ 注册新账户</span>}
          {mode !== "login" && <span style={S.link} onClick={() => switchTo("login")}>→ 去登录</span>}
          {mode !== "reset" && <span style={S.link} onClick={() => switchTo("reset")}>→ 忘记密码</span>}
        </div>
      </div>
    </div>
  );
}

function cleanErr(e: unknown): string {
  const msg = e instanceof Error ? e.message : "操作失败";
  return msg.replace(/[{}"]/g, "").replace("detail:", "").trim() || msg;
}
