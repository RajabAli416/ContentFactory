import type { ButtonHTMLAttributes, InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "../utils/cn";

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger" | "secondary";
}) {
  const styles = {
    primary: "bg-[var(--accent)] text-[#052722] hover:brightness-110",
    secondary: "bg-[var(--bg-panel)] border border-[var(--border)] text-[var(--text)] hover:border-[var(--accent-dim)]",
    ghost: "bg-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5",
    danger: "bg-[var(--danger)]/20 text-[var(--danger)] border border-[var(--danger)]/40 hover:bg-[var(--danger)]/30",
  } as const;
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition disabled:opacity-40",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent-dim)]",
        className
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent-dim)] min-h-28",
        className
      )}
      {...props}
    />
  );
}

export function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <label className={cn("mb-1.5 block text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]", className)}>
      {children}
    </label>
  );
}

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent-dim)]",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "ok" | "warn" | "danger" | "accent";
}) {
  const map = {
    neutral: "bg-white/5 text-[var(--text-muted)]",
    ok: "bg-[var(--ok)]/15 text-[var(--ok)]",
    warn: "bg-[var(--warn)]/15 text-[var(--warn)]",
    danger: "bg-[var(--danger)]/15 text-[var(--danger)]",
    accent: "bg-[var(--accent)]/15 text-[var(--accent)]",
  };
  return (
    <span className={cn("inline-flex rounded px-2 py-0.5 text-xs font-medium capitalize", map[tone])}>
      {children}
    </span>
  );
}

export function Panel({
  title,
  children,
  actions,
  className,
}: {
  title?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/80 backdrop-blur",
        className
      )}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          {title ? <h2 className="text-sm font-semibold tracking-wide">{title}</h2> : <span />}
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function statusTone(status: string): "neutral" | "ok" | "warn" | "danger" | "accent" {
  const s = status.toLowerCase();
  if (["completed", "ok", "passed", "skipped"].includes(s)) return "ok";
  if (["running", "generating", "pending", "in_progress"].includes(s)) return "accent";
  if (["paused", "warning"].includes(s)) return "warn";
  if (["failed", "cancelled", "error"].includes(s)) return "danger";
  return "neutral";
}

export function Tabs({
  tabs,
  value,
  onChange,
  trailing,
}: {
  tabs: Array<{ id: string; label: string }>;
  value: string;
  onChange: (id: string) => void;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-[var(--border)] pb-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm transition",
            value === t.id
              ? "bg-[var(--accent)]/15 font-medium text-[var(--accent)]"
              : "text-[var(--text-muted)] hover:bg-white/5 hover:text-[var(--text)]"
          )}
        >
          {t.label}
        </button>
      ))}
      {trailing ? <div className="ml-auto flex items-center gap-1">{trailing}</div> : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      {icon ? <div className="opacity-40">{icon}</div> : null}
      <p className="font-medium">{title}</p>
      {description ? <p className="max-w-sm text-sm text-[var(--text-muted)]">{description}</p> : null}
      {action}
    </div>
  );
}
