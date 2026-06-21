/// <reference types="vite/client" />

// File System Access API 类型声明
interface FileSystemDirectoryHandle {
  name: string;
  kind: "directory";
  queryPermission(desc?: { mode: "read" | "readwrite" }): Promise<"granted" | "denied" | "prompt">;
  requestPermission(desc?: { mode: "read" | "readwrite" }): Promise<"granted" | "denied" | "prompt">;
  values(): AsyncIterableIterator<FileSystemHandle>;
  entries(): AsyncIterableIterator<[string, FileSystemHandle]>;
  [Symbol.asyncIterator](): AsyncIterableIterator<[string, FileSystemHandle]>;
}

interface FileSystemFileHandle {
  name: string;
  kind: "file";
  getFile(): Promise<File>;
  queryPermission(desc?: { mode: "read" | "readwrite" }): Promise<"granted" | "denied" | "prompt">;
  requestPermission(desc?: { mode: "read" | "readwrite" }): Promise<"granted" | "denied" | "prompt">;
}

type FileSystemHandle = FileSystemDirectoryHandle | FileSystemFileHandle;

interface Window {
  showDirectoryPicker(options?: { mode?: "read" | "readwrite" }): Promise<FileSystemDirectoryHandle>;
}
