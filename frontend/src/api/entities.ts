import { get, post, patch, del } from "./client";
import type { CharacterItem, CharacterDetail, LocationItem, LocationDetail, SceneItem, SceneDetail, LoopItem, FactionItem, FactionDetail, RelationshipGraph } from "../types/entities";

export function getCharacters(projectId: string) {
  return get<{ characters: CharacterItem[] }>(`/v1/project/${projectId}/characters`);
}

export function getCharacter(projectId: string, charId: string) {
  return get<CharacterDetail>(`/v1/project/${projectId}/characters/${charId}`);
}

export function updateCharacter(projectId: string, charId: string, data: Record<string, unknown>) {
  return patch<CharacterDetail>(`/v1/project/${projectId}/characters/${charId}`, data);
}

export function deleteCharacter(projectId: string, charId: string) {
  return del<{ deleted: string; name: string; cleaned: Record<string, unknown> }>(`/v1/project/${projectId}/characters/${charId}`);
}

export function getLocations(projectId: string) {
  return get<{ locations: LocationItem[] }>(`/v1/project/${projectId}/locations`);
}

export function getLocation(projectId: string, locId: string) {
  return get<LocationDetail>(`/v1/project/${projectId}/locations/${locId}`);
}

export function getScenes(projectId: string) {
  return get<{ scenes: SceneItem[] }>(`/v1/project/${projectId}/scenes`);
}

export function getScene(projectId: string, sceneId: string) {
  return get<SceneDetail>(`/v1/project/${projectId}/scenes/${sceneId}`);
}

export function deleteScene(projectId: string, sceneId: string) {
  return del<{ deleted: string; tick: number; files: string[] }>(`/v1/project/${projectId}/scenes/${sceneId}`);
}

export function rewriteScene(projectId: string, sceneId: string) {
  return post<{ rewrite: string; rollback_to: number; backup: string }>(`/v1/project/${projectId}/scenes/${sceneId}/rewrite`);
}

export function updateLocation(projectId: string, locId: string, data: Record<string, unknown>) {
  return patch<LocationDetail>(`/v1/project/${projectId}/locations/${locId}`, data);
}

export function deleteLocation(projectId: string, locId: string) {
  return del<{ deleted: string }>(`/v1/project/${projectId}/locations/${locId}`);
}

export function getLoops(projectId: string) {
  return get<{ loops: LoopItem[] }>(`/v1/project/${projectId}/loops`);
}

export function updateLoop(projectId: string, loopId: string, data: Record<string, unknown>) {
  return patch<LoopItem>(`/v1/project/${projectId}/loops/${loopId}`, data);
}

export function deleteLoop(projectId: string, loopId: string) {
  return del<{ deleted: string }>(`/v1/project/${projectId}/loops/${loopId}`);
}

export function getFactions(projectId: string) {
  return get<{ factions: FactionItem[] }>(`/v1/project/${projectId}/factions`);
}

export function getFaction(projectId: string, factionId: string) {
  return get<FactionDetail>(`/v1/project/${projectId}/factions/${factionId}`);
}

export function getRelationships(projectId: string) {
  return get<RelationshipGraph>(`/v1/project/${projectId}/relationships`);
}
