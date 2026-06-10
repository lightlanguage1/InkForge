import { get, post, patch as patchReq, del } from "./client";

export interface WritingTemplate {
  id: string; name: string; description: string;
  prompt_snippet: string; is_preset: number; user_id: string | null;
}

export function getStylePresets() {
  return get<{ templates: WritingTemplate[] }>("/v1/styles/presets");
}
export function getCraftPresets() {
  return get<{ templates: WritingTemplate[] }>("/v1/craft/presets");
}
export function getStyleTemplates() {
  return get<{ templates: WritingTemplate[] }>("/v1/styles/templates");
}
export function getCraftTemplates() {
  return get<{ templates: WritingTemplate[] }>("/v1/craft/templates");
}
export function getPublicStyles() {
  return get<{ templates: WritingTemplate[] }>("/v1/styles/public");
}
export function createStyleTemplate(body: { name: string; description: string; prompt_snippet: string }) {
  return post<{ ok: boolean; id: string }>("/v1/styles/templates", body);
}
export function createCraftTemplate(body: { name: string; description: string; prompt_snippet: string }) {
  return post<{ ok: boolean; id: string }>("/v1/craft/templates", body);
}
export function updateStyleTemplate(id: string, body: { name: string; description: string; prompt_snippet: string }) {
  return patchReq<{ ok: boolean }>(`/v1/styles/templates/${id}`, body);
}
export function deleteStyleTemplate(id: string) {
  return del<{ ok: boolean }>(`/v1/styles/templates/${id}`);
}
export function deleteCraftTemplate(id: string) {
  return del<{ ok: boolean }>(`/v1/craft/templates/${id}`);
}
export function getProjectStyleConfig(projectId: string) {
  return get<{ style_id: string; craft_id: string }>(`/v1/project/${projectId}/style-config`);
}
export function setProjectStyleConfig(projectId: string, style_id: string, craft_id: string) {
  return patchReq<{ ok: boolean }>(`/v1/project/${projectId}/style-config`, { style_id, craft_id });
}

export function updateCraftTemplate(id: string, body: { name: string; description: string; prompt_snippet: string }) {
  return patchReq<{ ok: boolean }>(`/v1/craft/templates/${id}`, body);
}
