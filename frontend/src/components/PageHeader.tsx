import { cn } from "../utils/cn";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--accent)]">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-1 text-3xl font-bold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-[var(--text-muted)]">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function AlertBanner({
  tone = "danger",
  children,
}: {
  tone?: "danger" | "warn" | "ok" | "info";
  children: React.ReactNode;
}) {
  const styles = {
    danger: "border-[var(--danger)]/40 bg-[var(--danger)]/10 text-[var(--danger)]",
    warn: "border-[var(--warn)]/40 bg-[var(--warn)]/10 text-[var(--warn)]",
    ok: "border-[var(--ok)]/40 bg-[var(--ok)]/10 text-[var(--ok)]",
    info: "border-[var(--accent)]/40 bg-[var(--accent)]/10 text-[var(--accent)]",
  } as const;
  return (
    <div className={cn("rounded-lg border px-4 py-2.5 text-sm", styles[tone])}>{children}</div>
  );
}
