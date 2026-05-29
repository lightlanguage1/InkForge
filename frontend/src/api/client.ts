import { logError } from "../utils/logger";

const BASE = "/api"; // proxied by vite to localhost:8221

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response, path: string): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    const err = new ApiError(res.status, text);
    logError("api", err, { path, status: res.status });
    throw err;
  }
  return res.json();
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = localStorage.getItem("inkforge_token");
  return {
    ...(extra ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  return handleResponse<T>(res, path);
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res, path);
}

export async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res, path);
}

export async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse<T>(res, path);
}
