import type {
  Job,
  ProductionManifest,
  Project,
  ProjectCreate,
  SystemHealth,
} from "../types";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<SystemHealth>("/system/health"),
  config: () => request<Record<string, unknown>>("/system/config"),

  listProjects: () =>
    request<{ items: Project[]; total: number }>("/projects"),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (payload: ProjectCreate) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (id: string, payload: Partial<ProjectCreate & { status?: string }>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProject: (id: string) =>
    request<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" }),
  duplicateProject: (id: string) =>
    request<Project>(`/projects/${id}/duplicate`, { method: "POST" }),

  getManifest: (id: string) => request<ProductionManifest>(`/projects/${id}/manifest`),
  patchManifest: (id: string, patch: Record<string, unknown>) =>
    request<ProductionManifest>(`/projects/${id}/manifest`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  updateScene: (projectId: string, sceneId: string, patch: Record<string, unknown>) =>
    request(`/projects/${projectId}/scenes/${sceneId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  generateContent: (id: string) =>
    request<Job>(`/projects/${id}/generate-content`, { method: "POST" }),
  generateNarration: (id: string) =>
    request<Job>(`/projects/${id}/generate-narration`, { method: "POST" }),
  generateVisuals: (id: string) =>
    request<Job>(`/projects/${id}/generate-visuals`, { method: "POST" }),
  render: (id: string) => request<Job>(`/projects/${id}/render`, { method: "POST" }),
  runPipeline: (id: string) => request<Job>(`/projects/${id}/run`, { method: "POST" }),
  retryScene: (projectId: string, sceneId: string) =>
    request<Job>(`/projects/${projectId}/scenes/${sceneId}/retry`, { method: "POST" }),

  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  listJobs: () => request<{ items: Job[]; total: number }>("/jobs"),
  pauseJob: (id: string) => request<Job>(`/jobs/${id}/pause`, { method: "POST" }),
  resumeJob: (id: string) => request<Job>(`/jobs/${id}/resume`, { method: "POST" }),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),

  openFolder: (id: string) =>
    request<{ ok: boolean }>(`/projects/${id}/open-folder`, { method: "POST" }),

  mediaUrl: (projectId: string, type: "narration" | "render" | "srt" | "ass") =>
    `${BASE}/projects/${projectId}/media/${type}`,
  scenePreviewUrl: (projectId: string, sceneId: string) =>
    `${BASE}/projects/${projectId}/scenes/${sceneId}/preview`,
};

export function connectJobSocket(jobId: string, onEvent: (ev: unknown) => void): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/jobs/${jobId}`);
  ws.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data));
    } catch {
      /* ignore */
    }
  };
  return ws;
}
