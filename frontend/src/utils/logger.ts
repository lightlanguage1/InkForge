const MAX_BUFFER = 100;

interface LogEntry {
  level: "debug" | "info" | "warn" | "error";
  source: string;
  message: string;
  stack?: string;
  context?: Record<string, unknown>;
  timestamp: string;
}

const buffer: LogEntry[] = [];

function push(entry: LogEntry) {
  buffer.push(entry);
  if (buffer.length > MAX_BUFFER) buffer.shift();
  send(entry);
}

async function send(entry: LogEntry) {
  try {
    await fetch("/api/v1/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
  } catch {
    // 发送失败时不再递归记录，避免循环
  }
}

function extractMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try { return JSON.stringify(error); } catch { return String(error); }
}

function extractStack(error: unknown): string | undefined {
  return error instanceof Error ? error.stack : undefined;
}

export function logError(source: string, error: unknown, context?: Record<string, unknown>) {
  const entry: LogEntry = {
    level: "error",
    source,
    message: extractMessage(error),
    stack: extractStack(error),
    context,
    timestamp: new Date().toISOString(),
  };
  console.error(`[${source}]`, error);
  push(entry);
}

export function logWarn(source: string, message: string, context?: Record<string, unknown>) {
  const entry: LogEntry = { level: "warn", source, message, context, timestamp: new Date().toISOString() };
  console.warn(`[${source}]`, message);
  push(entry);
}

export function logInfo(source: string, message: string) {
  push({ level: "info", source, message, timestamp: new Date().toISOString() });
}

export function getLogBuffer(): readonly LogEntry[] {
  return buffer;
}

// 全局未捕获异常
if (typeof window !== "undefined") {
  window.addEventListener("error", (e) => {
    push({
      level: "error",
      source: "window.onerror",
      message: e.message,
      stack: e.error?.stack,
      context: { filename: e.filename, lineno: e.lineno, colno: e.colno },
      timestamp: new Date().toISOString(),
    });
  });

  window.addEventListener("unhandledrejection", (e) => {
    push({
      level: "error",
      source: "unhandledrejection",
      message: extractMessage(e.reason),
      stack: extractStack(e.reason),
      timestamp: new Date().toISOString(),
    });
  });
}
