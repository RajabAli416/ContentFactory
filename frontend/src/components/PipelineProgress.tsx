import { useMemo } from "react";
import { Check, Circle, Loader2, X } from "lucide-react";
import type { JobEvent } from "../types";
import { Badge, Panel, statusTone } from "./ui";
import { cn } from "../utils/cn";
import { formatStageStatus, stageDetail, stageLabel } from "../utils/pipeline";

type StageRow = {
  stage: string;
  status: string;
  error?: string | null;
};

function StageIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (["completed", "ok", "passed", "skipped"].includes(s)) {
    return <Check className="h-3.5 w-3.5 text-[var(--ok)]" />;
  }
  if (["running", "generating", "in_progress"].includes(s)) {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--accent)]" />;
  }
  if (["failed", "error", "cancelled"].includes(s)) {
    return <X className="h-3.5 w-3.5 text-[var(--danger)]" />;
  }
  return <Circle className="h-3 w-3 text-[var(--text-muted)]/50" />;
}

export function ProgressBar({
  value,
  className,
  animated,
}: {
  value: number;
  className?: string;
  animated?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-[var(--bg)] border border-[var(--border)]/60",
        className
      )}
    >
      <div
        className={cn(
          "h-full rounded-full bg-[var(--accent)] transition-[width] duration-500 ease-out",
          animated && "progress-shimmer"
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function PipelineProgress({
  stages,
  logs,
  activeJobId,
  compact = false,
}: {
  stages: StageRow[];
  logs: JobEvent[];
  activeJobId?: string | null;
  compact?: boolean;
}) {
  const latest = logs.length ? logs[logs.length - 1] : null;

  const progressPct = useMemo(() => {
    if (latest?.progress_pct != null) return latest.progress_pct;
    if (!stages.length) return 0;
    const done = stages.filter((s) =>
      ["completed", "skipped"].includes(s.status.toLowerCase())
    ).length;
    return Math.round((done / stages.length) * 100);
  }, [latest, stages]);

  const currentStage = latest?.stage ?? stages.find((s) => s.status.toLowerCase() === "running")?.stage;
  const currentStatus = latest?.status ?? "IDLE";
  const sceneProgress =
    latest?.scene_index && latest?.scene_total
      ? `Scene ${latest.scene_index}/${latest.scene_total}`
      : latest?.scene_id
        ? latest.scene_id
        : null;

  const recentLogs = logs.slice(-80).reverse();

  return (
    <div className={cn("grid gap-4", compact ? "" : "lg:grid-cols-5")}>
      <Panel
        title="Live progress"
        className={compact ? undefined : "lg:col-span-3"}
        actions={
          activeJobId ? (
            <span className="font-mono text-[10px] text-[var(--text-muted)]">{activeJobId}</span>
          ) : null
        }
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(currentStatus)}>{formatStageStatus(currentStatus)}</Badge>
                {latest?.stage_index && latest?.stage_total ? (
                  <span className="text-xs text-[var(--text-muted)]">
                    Stage {latest.stage_index}/{latest.stage_total}
                  </span>
                ) : null}
                {sceneProgress ? (
                  <Badge tone="accent">{sceneProgress}</Badge>
                ) : null}
              </div>
              <h3 className="mt-2 text-lg font-semibold tracking-tight">
                {latest?.stage_label || stageLabel(currentStage)}
              </h3>
              <p className="mt-0.5 text-sm text-[var(--text-muted)]">
                {latest?.message ||
                  latest?.stage_detail ||
                  stageDetail(currentStage) ||
                  "Waiting for pipeline events…"}
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-semibold tabular-nums text-[var(--accent)]">
                {Math.round(progressPct)}%
              </div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">
                overall
              </div>
            </div>
          </div>

          <ProgressBar
            value={progressPct}
            animated={["RUNNING", "PENDING", "PAUSED"].includes(currentStatus)}
          />

          {latest?.step ? (
            <p className="text-xs text-[var(--text-muted)]">
              Step: <span className="font-mono text-[var(--text)]">{latest.step}</span>
              {latest.duration_seconds != null
                ? ` · ${latest.duration_seconds.toFixed(1)}s`
                : ""}
            </p>
          ) : null}

          <div>
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Event log
              </h4>
              <span className="text-[11px] text-[var(--text-muted)]">{logs.length} events</span>
            </div>
            <div className="max-h-72 space-y-1.5 overflow-auto rounded-lg border border-[var(--border)]/70 bg-[var(--bg)]/40 p-2">
              {recentLogs.length === 0 && (
                <p className="px-2 py-6 text-center text-sm text-[var(--text-muted)]">
                  Run the pipeline to see live stage detail here.
                </p>
              )}
              {recentLogs.map((l, i) => (
                <div
                  key={`${l.timestamp}-${i}`}
                  className={cn(
                    "rounded-md border px-2.5 py-1.5 text-xs",
                    l.level === "error" || l.status === "FAILED"
                      ? "border-[var(--danger)]/30 bg-[var(--danger)]/5"
                      : "border-[var(--border)]/50 bg-[var(--bg-elevated)]/40"
                  )}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[10px] text-[var(--text-muted)]">
                      {l.timestamp?.slice(11, 19) ?? "--:--:--"}
                    </span>
                    <Badge tone={statusTone(l.status)}>{l.stage_label || stageLabel(l.stage) || l.status}</Badge>
                    {l.scene_index && l.scene_total ? (
                      <span className="text-[10px] text-[var(--accent)]">
                        {l.scene_index}/{l.scene_total}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 leading-relaxed text-[var(--text)]">
                    {l.message || "—"}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="Stage checklist" className={compact ? undefined : "lg:col-span-2"}>
        <ol className="space-y-1">
          {stages.length === 0 && (
            <li className="text-sm text-[var(--text-muted)]">No stages recorded yet.</li>
          )}
          {stages.map((s) => {
            const active = s.stage === currentStage && s.status.toLowerCase() === "running";
            return (
              <li
                key={s.stage}
                className={cn(
                  "flex items-start gap-2.5 rounded-lg px-2 py-2 text-sm transition",
                  active && "bg-[var(--accent)]/10 ring-1 ring-[var(--accent)]/25"
                )}
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                  <StageIcon status={s.status} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn("font-medium", active && "text-[var(--accent)]")}>
                      {stageLabel(s.stage)}
                    </span>
                    <Badge tone={statusTone(s.status)}>{formatStageStatus(s.status)}</Badge>
                  </div>
                  <p className="mt-0.5 text-[11px] leading-snug text-[var(--text-muted)]">
                    {stageDetail(s.stage)}
                  </p>
                  {s.error ? (
                    <p className="mt-1 text-[11px] text-[var(--danger)]">{s.error}</p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      </Panel>
    </div>
  );
}
