import { NavLink, Outlet } from "react-router-dom";
import { Clapperboard, FolderKanban, Activity, Plus } from "lucide-react";
import { cn } from "../utils/cn";

const links = [
  { to: "/", label: "Dashboard", icon: FolderKanban },
  { to: "/new", label: "New Project", icon: Plus },
  { to: "/monitor", label: "Monitor", icon: Activity },
];

export function AppLayout() {
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)]/70 backdrop-blur-md">
        <div className="flex items-center gap-2.5 border-b border-[var(--border)] px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)]/15">
            <Clapperboard className="h-5 w-5 text-[var(--accent)]" />
          </div>
          <div>
            <div className="text-base font-bold tracking-tight">ContentFactory</div>
            <div className="text-[11px] text-[var(--text-muted)]">Faceless short-form studio</div>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
                  isActive
                    ? "bg-[var(--accent)]/15 font-medium text-[var(--accent)]"
                    : "text-[var(--text-muted)] hover:bg-white/5 hover:text-[var(--text)]"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-[var(--border)] p-4 text-[11px] leading-relaxed text-[var(--text-muted)]">
          Narration is audio-only. Visuals stay cinematic and faceless.
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
