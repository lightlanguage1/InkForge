import { get, post } from "./client";

export interface TimelineNode {
  tick: number;
  hash: string;
  parent: string;
  branch: string;
  title: string;
  file: string;
  archived: boolean;
  active: boolean;
}

export interface TimelineBranch {
  name: string;
  hash: string;
  tick: number;
  message: string;
  active: boolean;
}

export interface TimelineCheckpoint {
  id: string;
  tick: number;
  hash: string;
  label: string;
}

export interface TimelineData {
  current_tick: number;
  current_branch: string;
  current_hash: string;
  nodes: TimelineNode[];
  branches: TimelineBranch[];
  checkpoints: TimelineCheckpoint[];
}

export function getTimeline(projectId: string) {
  return get<TimelineData>(`/v1/project/${encodeURIComponent(projectId)}/timeline`);
}

export function switchBranch(projectId: string, branchName: string) {
  return post<{ switched: boolean; branch: string; current_tick: number }>(`/v1/project/${encodeURIComponent(projectId)}/switch-branch/${encodeURIComponent(branchName)}`);
}
