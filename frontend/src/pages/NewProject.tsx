import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { AlertBanner, PageHeader } from "../components/PageHeader";
import { Button, Input, Label, Panel, Select, Textarea } from "../components/ui";

export function NewProject() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    topic: "",
    title: "",
    target_duration_seconds: 45,
    platform: "youtube_shorts",
    language: "English",
    content_mode: "standard",
    tone: "informative",
    visual_aesthetic: "cinematic documentary",
    narration_voice: "Aoede",
    aspect_ratio: "9:16",
    extra_instructions: "",
  });

  const setMode = (mode: string) => {
    if (mode === "desi") {
      setForm((f) => ({
        ...f,
        content_mode: "desi",
        language: "Urdu",
        platform: f.platform === "youtube_shorts" ? "tiktok" : f.platform,
        tone: f.tone === "informative" ? "conversational desi storytelling" : f.tone,
      }));
      return;
    }
    setForm((f) => ({ ...f, content_mode: "standard" }));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({
        ...form,
        title: form.title || undefined,
        extra_instructions: form.extra_instructions || undefined,
      });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  };

  const set = (key: string, value: string | number) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <div className="page-shell mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow="Quick create"
        title="New project"
        description="One topic in — structured script, scenes, narration, and assembly out."
      />

      <Panel>
        <form className="space-y-4" onSubmit={submit}>
          <div>
            <Label>Topic</Label>
            <Textarea
              required
              value={form.topic}
              onChange={(e) => set("topic", e.target.value)}
              placeholder="e.g. Why deep ocean trenches stay unexplored"
            />
          </div>
          <div>
            <Label>Working title (optional)</Label>
            <Input value={form.title} onChange={(e) => set("title", e.target.value)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label>Content mode</Label>
              <Select value={form.content_mode} onChange={(e) => setMode(e.target.value)}>
                <option value="standard">Standard (English)</option>
                <option value="desi">Desi (Urdu TTS + Roman Urdu captions)</option>
              </Select>
              {form.content_mode === "desi" && (
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  Spoken Urdu narration, on-screen Roman Urdu captions, plus PK/IN TikTok hashtags on export.
                </p>
              )}
            </div>
            <div>
              <Label>Duration (seconds)</Label>
              <Input
                type="number"
                min={10}
                max={180}
                value={form.target_duration_seconds}
                onChange={(e) => set("target_duration_seconds", Number(e.target.value))}
              />
            </div>
            <div>
              <Label>Platform</Label>
              <Select value={form.platform} onChange={(e) => set("platform", e.target.value)}>
                <option value="youtube_shorts">YouTube Shorts</option>
                <option value="tiktok">TikTok</option>
                <option value="instagram_reels">Instagram Reels</option>
              </Select>
            </div>
            <div>
              <Label>Language</Label>
              <Input value={form.language} onChange={(e) => set("language", e.target.value)} />
            </div>
            <div>
              <Label>Narration voice</Label>
              <Select
                value={form.narration_voice}
                onChange={(e) => set("narration_voice", e.target.value)}
              >
                {["Aoede", "Kore", "Charon", "Fenrir", "Puck"].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Tone</Label>
              <Input value={form.tone} onChange={(e) => set("tone", e.target.value)} />
            </div>
            <div>
              <Label>Visual aesthetic</Label>
              <Input
                value={form.visual_aesthetic}
                onChange={(e) => set("visual_aesthetic", e.target.value)}
              />
            </div>
          </div>
          <div>
            <Label>Extra instructions</Label>
            <Textarea
              value={form.extra_instructions}
              onChange={(e) => set("extra_instructions", e.target.value)}
              placeholder="Optional creative constraints…"
            />
          </div>
          {error ? <AlertBanner>{error}</AlertBanner> : null}
          <Button type="submit" disabled={busy || !form.topic.trim()}>
            {busy ? "Creating…" : "Create project"}
          </Button>
        </form>
      </Panel>
    </div>
  );
}
