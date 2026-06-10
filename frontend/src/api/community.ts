import { get, post, patch, del } from "./client";

export function getOnlineCount() {
  return get<{ online: number }>("/v1/community/online");
}

export function listPosts() {
  return get<{ posts: { project_id: string; user_id: string; display_name: string; novel_name: string; current_tick: number; scene_count: number; genre: string; created_at: string }[] }>("/v1/community/posts");
}

export function getPublishStatus(projectId: string) {
  return get<{ published: boolean }>(`/v1/community/publish/${projectId}`);
}

export function togglePublish(projectId: string, published: boolean) {
  return patch<{ published: boolean }>(`/v1/community/publish/${projectId}`, { published });
}

export function getComments(projectId: string) {
  return get<{ comments: { id: number; user_id: string; display_name: string; chapter_tick: number | null; paragraph: number | null; content: string; parent_id: number | null; created_at: string }[] }>(`/v1/community/comments/${projectId}`);
}

export function addComment(projectId: string, body: { content: string; chapter_tick?: number; paragraph?: number; parent_id?: number }) {
  return post<{ id: number; created_at: string }>(`/v1/community/comments/${projectId}`, body);
}

export function editComment(commentId: number, content: string) {
  return patch<{ ok: boolean }>(`/v1/community/comments/${commentId}`, { content });
}

export function deleteComment(commentId: number) {
  return del<{ ok: boolean }>(`/v1/community/comments/${commentId}`);
}

export function getChatMessages(projectId?: string, sinceId: number = 0) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (sinceId > 0) params.set("since_id", String(sinceId));
  const qs = params.toString();
  return get<{ messages: { id: number; user_id: string; display_name: string; message: string; created_at: string }[] }>(`/v1/community/chat${qs ? '?' + qs : ''}`);
}

export function postChatMessage(message: string, projectId?: string) {
  return post<{ id: number; created_at: string }>("/v1/community/chat", { message, project_id: projectId || null });
}

export interface ReadScene {
  file: string; tick: number; title: string;
  paragraphs: string[]; word_count: number;
}

export function readProject(projectId: string, tick?: number) {
  const params = tick !== undefined ? `?tick=${tick}` : "";
  return get<{ title: string; scenes: ReadScene[] }>(`/v1/community/read/${projectId}${params}`);
}
