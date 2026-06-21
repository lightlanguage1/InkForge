import { get, post, patch } from "./client";

export interface Feedback {
  id: string;
  user_id: string;
  display_name: string;
  title: string;
  content: string;
  category: string;
  status: string;
  admin_note?: string;
  created_at: string;
}

export function submitFeedback(title: string, content: string, category: string) {
  return post<{ ok: boolean; id: string }>("/v1/feedback/", { title, content, category });
}

export function listFeedback(status?: string) {
  const qs = status ? `?status=${status}` : "";
  return get<{ feedback: Feedback[] }>(`/v1/feedback/${qs}`);
}

export function updateFeedback(id: string, data: { status?: string; admin_note?: string }) {
  return patch<{ ok: boolean }>(`/v1/feedback/${id}`, data);
}
