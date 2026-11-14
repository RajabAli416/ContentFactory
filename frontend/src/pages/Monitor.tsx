import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Job } from "../types";
import { PageHeader, AlertBanner } from "../components/PageHeader";
import { Badge, Button, EmptyState, Panel, statusTone } from "../components/ui";
import { stageLabel } from "../utils/pipeline";

export function Monitor() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await api.listJobs();
      setJobs(res.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="page-shell space-y-6">
      <PageHeader
        eyebrow="Live ops"
        title="Production monitor"
        description="Active and recent pipeline jobs across all projects."
        actions={
          <Button variant="secondary" onClick={load}>
            Refresh
          </Button>
        }
      />

      {error ? <AlertBanner>{error}</AlertBanner> : null}

      <Panel title="Jobs">
        {jobs.length === 0 ? (
          <EmptyState title="No jobs yet" description="Start a pipeline from any project workspace." />
        ) : (
          <ul className="space-y-3">
            {jobs.map((j) => {
              const done = j.stages.filter((s) =>
                ["COMPLETED", "SKIPPED"].includes(s.status)
              ).length;
              const total = j.stages.length || 1;
              const pct = Math.round((done / total) * 100);
              return (
                <li
                  key={j.id}
                  className="rounded-xl border border-[var(--border)] bg-[var(--bg)]/50 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge tone={statusTone(j.status)}>{j.status}</Badge>
                    <Link
                      className="text-sm font-medium text-[var(--accent)] hover:underline"
                      to={`/projects/${j.project_id}`}
                    >
                      Open project
                    </Link>
                    <span className="font-mono text-[10px] text-[var(--text-muted)]">{j.id}</span>
                    <span className="ml-auto text-sm text-[var(--text-muted)]">
                      {j.job_type} · {stageLabel(j.current_stage)} · {pct}%
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)] transition-[width]"
                      style={{ width: `${j.status === "COMPLETED" ? 100 : pct}%` }}
                    />
                  </div>
                  {j.stages.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {j.stages.map((s) => {
                        const tone = statusTone(s.status);
                        const dot =
                          tone === "ok"
                            ? "bg-[var(--ok)]"
                            : tone === "accent"
                              ? "bg-[var(--accent)]"
                              : tone === "danger"
                                ? "bg-[var(--danger)]"
                                : tone === "warn"
                                  ? "bg-[var(--warn)]"
                                  : "bg-[var(--border)]";
                        return (
                          <span
                            key={s.stage}
                            title={`${stageLabel(s.stage)} · ${s.status}${s.error_message ? ` — ${s.error_message}` : ""}`}
                            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)]/70 px-2 py-0.5 text-[11px] text-[var(--text-muted)]"
                          >
                            <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
                            {stageLabel(s.stage)}
                          </span>
                        );
                      })}
                    </div>
                  ) : null}
                  {j.error_message && (
                    <p className="mt-2 text-sm text-[var(--danger)]">{j.error_message}</p>
                  )}
                  <div className="mt-3 flex gap-2">
                    {j.status === "RUNNING" && (
                      <Button variant="secondary" onClick={() => api.pauseJob(j.id).then(load)}>
                        Pause
                      </Button>
                    )}
                    {j.status === "PAUSED" && (
                      <Button variant="secondary" onClick={() => api.resumeJob(j.id).then(load)}>
                        Resume
                      </Button>
                    )}
                    {["RUNNING", "PENDING", "PAUSED"].includes(j.status) && (
                      <Button variant="danger" onClick={() => api.cancelJob(j.id).then(load)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
