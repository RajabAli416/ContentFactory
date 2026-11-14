import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Film, Plus, Trash2, Copy } from "lucide-react";
import { api } from "../services/api";
import type { Project, SystemHealth } from "../types";
import { AlertBanner, PageHeader } from "../components/PageHeader";
import { Badge, Button, EmptyState, Panel, statusTone } from "../components/ui";

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [p, h] = await Promise.all([api.listProjects(), api.health()]);
      setProjects(p.items);
      setHealth(h);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page-shell space-y-6">
      <PageHeader
        eyebrow="Production desk"
        title="Dashboard"
        description="Recent faceless short-form projects and system readiness."
        actions={
          <Link to="/new">
            <Button>
              <Plus className="h-4 w-4" /> New project
            </Button>
          </Link>
        }
      />

      {error ? <AlertBanner>{error}</AlertBanner> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="System">
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--text-muted)]">Status</dt>
              <dd>
                <Badge tone={statusTone(health?.status ?? "")}>{health?.status ?? "…"}</Badge>
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--text-muted)]">Gemini</dt>
              <dd>
                <Badge tone={health?.gemini_configured ? "ok" : "danger"}>
                  {health?.gemini_configured ? "configured" : "missing key"}
                </Badge>
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--text-muted)]">Visuals</dt>
              <dd>
                <Badge tone="accent">{health?.video_gen_provider ?? "…"}</Badge>
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--text-muted)]">FFmpeg</dt>
              <dd className="truncate text-xs text-[var(--text-muted)]">{health?.ffmpeg ?? "…"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--text-muted)]">Chrome CDP</dt>
              <dd>
                <Badge tone={health?.chrome_cdp ? "ok" : "warn"}>
                  {health?.chrome_cdp ? "connected" : "offline"}
                </Badge>
              </dd>
            </div>
          </dl>
        </Panel>
        <Panel title="Projects" className="md:col-span-2">
          <p className="text-3xl font-semibold tabular-nums">{projects.length}</p>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Stored locally under <span className="font-mono text-xs">data/projects</span>
          </p>
        </Panel>
      </div>

      <Panel
        title="Recent projects"
        actions={
          <Button variant="ghost" onClick={load}>
            Refresh
          </Button>
        }
      >
        {projects.length === 0 ? (
          <EmptyState
            icon={<Film className="h-10 w-10" />}
            title="No projects yet"
            description="Create your first short and run the full pipeline."
            action={
              <Link to="/new">
                <Button>Create project</Button>
              </Link>
            }
          />
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {projects.map((p) => (
              <li key={p.id} className="flex items-center gap-4 py-3">
                <div className="min-w-0 flex-1">
                  <Link to={`/projects/${p.id}`} className="font-medium hover:text-[var(--accent)]">
                    {p.title}
                  </Link>
                  <p className="truncate text-sm text-[var(--text-muted)]">{p.topic}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {p.content_mode === "desi" ? <Badge tone="accent">Desi</Badge> : null}
                    <Badge>{p.language}</Badge>
                    <Badge>{p.platform}</Badge>
                  </div>
                </div>
                <Badge tone={statusTone(p.status)}>{p.status}</Badge>
                <span className="text-xs tabular-nums text-[var(--text-muted)]">
                  {p.target_duration_seconds}s
                </span>
                <Button
                  variant="ghost"
                  title="Duplicate"
                  onClick={async () => {
                    await api.duplicateProject(p.id);
                    load();
                  }}
                >
                  <Copy className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  title="Delete"
                  onClick={async () => {
                    if (!confirm("Delete this project?")) return;
                    await api.deleteProject(p.id);
                    load();
                  }}
                >
                  <Trash2 className="h-4 w-4 text-[var(--danger)]" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
