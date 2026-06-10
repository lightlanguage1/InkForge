import { get, post, del } from "./client";

export interface Song {
  id: string; mid: string; title: string; artist: string;
  album: string; duration: number; artwork: string;
  favorited?: boolean;
}

export function searchMusic(q: string, page = 1) {
  return get<{ results: Song[]; total: number }>(`/v1/music/search?q=${encodeURIComponent(q)}&page=${page}&limit=10`);
}

export function getRandomSongs(limit = 20) {
  return get<{ results: Song[]; total: number }>(`/v1/music/random?limit=${limit}`);
}

export function getFavorites() {
  return get<{ results: Song[] }>("/v1/music/favorites");
}

export function addFavorite(song: Song) {
  return post<{ ok: boolean; inserted: boolean }>("/v1/music/favorites", song);
}

export function removeFavorite(songId: string) {
  return del<{ ok: boolean }>(`/v1/music/favorites/${songId}`);
}

export function getStreamUrl(mid: string, title?: string, artist?: string) {
  let url = `/api/v1/music/stream/${mid}`;
  const params = new URLSearchParams();
  if (title) params.set("title", title);
  if (artist) params.set("artist", artist);
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}
