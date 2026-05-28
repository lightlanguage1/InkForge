import { get } from "./client";
import type { CharacterItem, CharacterDetail, LocationItem, LocationDetail, SceneItem, SceneDetail, LoopItem, FactionItem, FactionDetail } from "../types/entities";

export function getCharacters(projectId: string) {
  return get<{ characters: CharacterItem[] }>(`/v1/project/${projectId}/characters`);
}

export function getCharacter(projectId: string, charId: string) {
  return get<CharacterDetail>(`/v1/project/${projectId}/characters/${charId}`);
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

export function getLoops(projectId: string) {
  return get<{ loops: LoopItem[] }>(`/v1/project/${projectId}/loops`);
}

export function getFactions(projectId: string) {
  return get<{ factions: FactionItem[] }>(`/v1/project/${projectId}/factions`);
}

export function getFaction(projectId: string, factionId: string) {
  return get<FactionDetail>(`/v1/project/${projectId}/factions/${factionId}`);
}
