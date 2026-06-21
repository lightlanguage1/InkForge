import { get, post, patch, del } from "./client";

export interface Announcement {
  id: number;
  title: string;
  content: string;
  tag: string;
  active: number;
  created_at: string;
}

export function getActiveAnnouncements(limit = 5) {
  return get<{ announcements: Announcement[] }>(`/v1/announcements/active?limit=${limit}`);
}

export function listAllAnnouncements() {
  return get<{ announcements: Announcement[] }>("/v1/announcements/all");
}

export function createAnnouncement(title: string, content: string, tag: string) {
  return post<{ ok: boolean; id: number }>("/v1/announcements/", { title, content, tag });
}

export function updateAnnouncement(id: number, data: { title?: string; content?: string; tag?: string; active?: number }) {
  return patch<{ ok: boolean }>(`/v1/announcements/${id}`, data);
}

export function deleteAnnouncement(id: number) {
  return del<{ ok: boolean }>(`/v1/announcements/${id}`);
}
