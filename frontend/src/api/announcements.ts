import { get } from "./client";

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
