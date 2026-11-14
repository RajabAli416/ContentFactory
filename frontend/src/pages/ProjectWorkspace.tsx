import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FolderOpen, Play, RefreshCw } from "lucide-react";
import { api, connectJobSocket } from "../services/api";
import type { JobEvent, ProductionManifest, Project } from "../types";
import { AlertBanner } from "../components/PageHeader";
import { PipelineProgress, ProgressBar } from "../components/PipelineProgress";
import { Badge, Button, Label, Panel, Tabs, Textarea, statusTone } from "../components/ui";
import { stageLabel } from "../utils/pipeline";

export function ProjectWorkspace() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [manifest, setManifest] = useState<ProductionManifest | null>(null);
  const [tab, setTab] = useState<"overview" | "script" | "scenes" | "monitor" | "export">("overview");
  const [logs, setLogs] = useState<JobEvent[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const load = async () => {
    const [p, m] = await Promise.all([api.getProject(projectId), api.getManifest(projectId)]);
    setProject(p);
    setManifest(m);
  };

  useEffect(() => {
    load().catch((e) => setError(e.message));
    return () => wsRef.current?.close();
  }, [projectId]);

  const attachJob = (jobId: string) => {
    setActiveJobId(jobId);
    wsRef.current?.close();
    wsRef.current = connectJobSocket(jobId, (ev) => {
      const event = ev as JobEvent;
      setLogs((prev) => [...prev.slice(-200), event]);
      if (event.stage && ["RUNNING", "COMPLETED", "FAILED", "SKIPPED", "PAUSED"].includes(event.status)) {
        const nextStatus =
          event.status === "RUNNING"
            ? "running"
            : event.status === "COMPLETED"
              ? "completed"
              : event.status === "SKIPPED"
                ? "skipped"
                : event.status === "PAUSED"
                  ? "paused"
                  : "failed";
        setManifest((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            pipeline_stages: prev.pipeline_stages.map((s) =>
              s.stage === event.stage ? { ...s, status: nextStatus, error: event.status === "FAILED" ? event.message ?? s.error : s.error } : s
            ),
          };
        });
      }
      if (
        ["FAILED", "CANCELLED"].includes(event.status) ||
        (event.status === "COMPLETED" && (event.stage === "COMPLETED" || !event.stage))
      ) {
        load().catch(() => undefined);
      }
    });
  };

  const run = async (action: () => Promise<{ id: string }>, label: string) => {
    setBusy(label);
    setError(null);
    try {
      const job = await action();
      attachJob(job.id);
      setTab("monitor");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  };

  const stages = useMemo(() => manifest?.pipeline_stages ?? [], [manifest]);
  const latestEvent = logs.length ? logs[logs.length - 1] : null;
  const overviewPct = useMemo(() => {
    if (latestEvent?.progress_pct != null) return latestEvent.progress_pct;
    if (!stages.length) return 0;
    const done = stages.filter((s) =>
      ["completed", "skipped"].includes(s.status.toLowerCase())
    ).length;
    return Math.round((done / stages.length) * 100);
  }, [latestEvent, stages]);

  if (!project || !manifest) {
    return <div className="page-shell text-[var(--text-muted)]">{error ?? "Loading…"}</div>;
  }

  return (
    <div className="page-shell space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/" className="text-xs text-[var(--text-muted)] hover:text-[var(--accent)]">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight md:text-3xl">{project.title}</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">{project.topic}</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            <Badge tone={statusTone(project.status)}>{project.status}</Badge>
            <Badge>{project.target_duration_seconds}s</Badge>
            {(project.content_mode || manifest.settings?.content_mode) === "desi" ? (
              <Badge tone="accent">Desi mode</Badge>
            ) : null}
            <Badge>{project.language}</Badge>
            <Badge>{project.visual_aesthetic}</Badge>
            <Badge tone="accent">{project.narration_voice}</Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() => run(() => api.generateContent(projectId), "content")}
          >
            Generate content
          </Button>
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() => run(() => api.generateNarration(projectId), "narration")}
          >
            Narration
          </Button>
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() => run(() => api.generateVisuals(projectId), "visuals")}
          >
            Visuals
          </Button>
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() => run(() => api.render(projectId), "render")}
          >
            Render
          </Button>
          <Button disabled={!!busy} onClick={() => run(() => api.runPipeline(projectId), "full")}>
            <Play className="h-4 w-4" /> {busy === "full" ? "Starting…" : "Run full pipeline"}
          </Button>
        </div>
      </header>

      {error ? <AlertBanner>{error}</AlertBanner> : null}

      {latestEvent && ["RUNNING", "PAUSED", "PENDING"].includes(latestEvent.status) ? (
        <button
          type="button"
          onClick={() => setTab("monitor")}
          className="w-full rounded-xl border border-[var(--accent)]/30 bg-[var(--accent)]/8 px-4 py-3 text-left transition hover:bg-[var(--accent)]/12"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-[var(--accent)]">Pipeline running</p>
              <p className="mt-0.5 text-sm font-medium">
                {latestEvent.stage_label || stageLabel(latestEvent.stage)}
                {latestEvent.message ? ` — ${latestEvent.message}` : ""}
              </p>
            </div>
            <span className="text-lg font-semibold tabular-nums text-[var(--accent)]">
              {Math.round(overviewPct)}%
            </span>
          </div>
          <ProgressBar value={overviewPct} animated className="mt-2.5" />
        </button>
      ) : null}

      <Tabs
        value={tab}
        onChange={(id) => setTab(id as typeof tab)}
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "script", label: "Script" },
          { id: "scenes", label: "Scenes" },
          { id: "monitor", label: "Monitor" },
          { id: "export", label: "Export" },
        ]}
        trailing={
          <Button variant="ghost" onClick={() => load()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        }
      />

      {tab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel
            title="Pipeline stages"
            actions={
              <span className="text-xs tabular-nums text-[var(--text-muted)]">{overviewPct}%</span>
            }
          >
            <ProgressBar value={overviewPct} className="mb-4" />
            <ol className="space-y-2">
              {stages.map((s) => (
                <li key={s.stage} className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate">{stageLabel(s.stage)}</span>
                  <Badge tone={statusTone(s.status)}>{s.status}</Badge>
                </li>
              ))}
            </ol>
          </Panel>
          <Panel title="Narration">
            <p className="mb-2 text-sm text-[var(--text-muted)]">
              Status: {manifest.narration.status} · {manifest.narration.duration_seconds?.toFixed(1) ?? "—"}s ·{" "}
              {manifest.narration.provider || "—"}
            </p>
            {manifest.narration.audio_path ? (
              <audio controls className="w-full" src={api.mediaUrl(projectId, "narration")} />
            ) : (
              <p className="text-sm text-[var(--text-muted)]">No narration audio yet.</p>
            )}
          </Panel>
        </div>
      )}

      {tab === "script" && (
        <Panel title="Script editor">
          <div className="space-y-3">
            <div>
              <Label>Hook</Label>
              <Textarea
                value={manifest.script.hook}
                onChange={(e) =>
                  setManifest({ ...manifest, script: { ...manifest.script, hook: e.target.value } })
                }
              />
            </div>
            <div>
              <Label>Full narration (spoken / TTS)</Label>
              <Textarea
                className="min-h-48"
                value={manifest.script.full_text}
                onChange={(e) =>
                  setManifest({
                    ...manifest,
                    script: { ...manifest.script, full_text: e.target.value },
                  })
                }
              />
            </div>
            {(project.content_mode === "desi" ||
              manifest.settings?.content_mode === "desi" ||
              !!manifest.script.caption_text) && (
              <div>
                <Label>Roman Urdu captions</Label>
                <Textarea
                  className="min-h-36"
                  value={manifest.script.caption_text || ""}
                  onChange={(e) =>
                    setManifest({
                      ...manifest,
                      script: { ...manifest.script, caption_text: e.target.value },
                    })
                  }
                />
              </div>
            )}
            <div>
              <Label>Closing line</Label>
              <Textarea
                value={manifest.script.closing_line}
                onChange={(e) =>
                  setManifest({
                    ...manifest,
                    script: { ...manifest.script, closing_line: e.target.value },
                  })
                }
              />
            </div>
            <Button
              onClick={async () => {
                const updated = await api.patchManifest(projectId, {
                  script: manifest.script,
                });
                setManifest(updated);
              }}
            >
              Save script
            </Button>
          </div>
        </Panel>
      )}

      {tab === "scenes" && (
        <div className="grid gap-4 md:grid-cols-2">
          {manifest.scenes.map((scene) => (
            <Panel
              key={scene.scene_id}
              title={`Scene ${scene.sequence}`}
              actions={<Badge tone={statusTone(scene.generation_status)}>{scene.generation_status}</Badge>}
            >
              <div className="space-y-3">
                <div>
                  <Label>Narration beat</Label>
                  <Textarea
                    value={scene.narration_text}
                    onChange={(e) => {
                      const scenes = manifest.scenes.map((s) =>
                        s.scene_id === scene.scene_id
                          ? { ...s, narration_text: e.target.value }
                          : s
                      );
                      setManifest({ ...manifest, scenes });
                    }}
                  />
                </div>
                <div>
                  <Label>Visual description</Label>
                  <Textarea
                    value={scene.visual_description}
                    onChange={(e) => {
                      const scenes = manifest.scenes.map((s) =>
                        s.scene_id === scene.scene_id
                          ? { ...s, visual_description: e.target.value }
                          : s
                      );
                      setManifest({ ...manifest, scenes });
                    }}
                  />
                </div>
                <div>
                  <Label>Video prompt</Label>
                  <Textarea
                    className="min-h-24"
                    value={scene.video_prompt}
                    onChange={(e) => {
                      const scenes = manifest.scenes.map((s) =>
                        s.scene_id === scene.scene_id
                          ? { ...s, video_prompt: e.target.value }
                          : s
                      );
                      setManifest({ ...manifest, scenes });
                    }}
                  />
                </div>
                {(scene.raw_asset_path || scene.processed_asset_path) && (
                  <video
                    className="aspect-[9/16] max-h-64 w-full rounded-md bg-black object-contain"
                    controls
                    src={api.scenePreviewUrl(projectId, scene.scene_id)}
                  />
                )}
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      await api.updateScene(projectId, scene.scene_id, {
                        narration_text: scene.narration_text,
                        visual_description: scene.visual_description,
                        video_prompt: scene.video_prompt,
                      });
                      await load();
                    }}
                  >
                    Save
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      run(() => api.retryScene(projectId, scene.scene_id), `scene-${scene.scene_id}`)
                    }
                  >
                    Regenerate clip
                  </Button>
                </div>
              </div>
            </Panel>
          ))}
          {manifest.scenes.length === 0 && (
            <p className="text-sm text-[var(--text-muted)]">Generate content to create scenes.</p>
          )}
        </div>
      )}

      {tab === "monitor" && (
        <PipelineProgress stages={stages} logs={logs} activeJobId={activeJobId} />
      )}

      {tab === "export" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Final video">
            {manifest.render.output_path && manifest.render.status === "completed" ? (
              <video
                className="aspect-[9/16] max-h-[70vh] w-full rounded-lg bg-black object-contain"
                controls
                src={api.mediaUrl(projectId, "render")}
              />
            ) : (
              <p className="text-sm text-[var(--text-muted)]">
                No final render yet. Run the pipeline or click Render.
              </p>
            )}
          </Panel>
          <Panel
            title="Export details"
            actions={
              <Button variant="secondary" onClick={() => api.openFolder(projectId)}>
                <FolderOpen className="h-4 w-4" /> Open folder
              </Button>
            }
          >
            <dl className="space-y-2.5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--text-muted)]">Render status</dt>
                <dd>
                  <Badge tone={statusTone(manifest.render.status)}>{manifest.render.status}</Badge>
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--text-muted)]">QA</dt>
                <dd>
                  <Badge tone={statusTone(manifest.render.qa_status)}>
                    {manifest.render.qa_status || "—"}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--text-muted)]">Duration</dt>
                <dd className="tabular-nums">{manifest.render.duration_seconds?.toFixed(2) ?? "—"}s</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--text-muted)]">Captions</dt>
                <dd>
                  <Badge tone={statusTone(manifest.captions.status)}>{manifest.captions.status || "—"}</Badge>
                </dd>
              </div>
              <div>
                <dt className="text-[var(--text-muted)]">Path</dt>
                <dd className="mt-1 break-all font-mono text-xs text-[var(--text-muted)]">
                  {manifest.render.output_path ?? "—"}
                </dd>
              </div>
            </dl>
            {manifest.render.qa_report && (
              <pre className="mt-4 max-h-64 overflow-auto rounded bg-[var(--bg)] p-3 text-xs">
                {JSON.stringify(manifest.render.qa_report, null, 2)}
              </pre>
            )}
          </Panel>
          {manifest.packaging && (manifest.packaging.hashtags?.length || manifest.packaging.post_caption) ? (
            <Panel
              title={
                manifest.packaging.markets?.length
                  ? `Post packaging (${manifest.packaging.markets.join(" · ")})`
                  : "Post packaging"
              }
              className="lg:col-span-2"
              actions={
                <Button
                  variant="secondary"
                  onClick={() => {
                    const pack = manifest.packaging!;
                    const blob = [pack.post_caption, "", pack.hashtag_string || pack.hashtags.join(" ")]
                      .filter(Boolean)
                      .join("\n");
                    void navigator.clipboard.writeText(blob);
                  }}
                >
                  Copy caption + hashtags
                </Button>
              }
            >
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">Title</p>
                  <p className="mt-1 font-medium">{manifest.packaging.post_title || "—"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">Caption</p>
                  <p className="mt-1 whitespace-pre-wrap">{manifest.packaging.post_caption || "—"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">
                    Hashtags {manifest.packaging.markets?.length ? `(${manifest.packaging.markets.join(" · ")})` : ""}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(manifest.packaging.hashtags || []).map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                  <p className="mt-3 break-words font-mono text-xs text-[var(--text-muted)]">
                    {manifest.packaging.hashtag_string || (manifest.packaging.hashtags || []).join(" ")}
                  </p>
                </div>
              </div>
            </Panel>
          ) : null}
        </div>
      )}
    </div>
  );
}
