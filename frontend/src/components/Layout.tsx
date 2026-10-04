import { BookMarked, BookOpen, FileText, UserRound, Boxes, FlaskConical, Fingerprint, GitCompare, LayoutDashboard, Menu, SearchX, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { DemoBanner } from "./DemoBanner";
import { StatusBadge } from "./StatusBadge";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/experiments", label: "Experiments", icon: FlaskConical },
  { to: "/failures", label: "Failure analysis", icon: SearchX },
  { to: "/fingerprint", label: "Fingerprint", icon: Fingerprint },
  { to: "/compare", label: "Compare versions", icon: GitCompare },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/notebook", label: "Notebook", icon: BookMarked },
  { to: "/models", label: "Models", icon: Boxes },
  { to: "/", label: "About LLM Lens", icon: BookOpen, end: true },
];

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  return (
    <nav aria-label="Primary" className="flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded px-3 py-2 text-sm ${
              isActive ? "bg-lens-wash font-medium text-lens-deep" : "text-ink-soft hover:bg-bench"
            }`
          }
        >
          <Icon className="h-4 w-4" aria-hidden />
          {label}
        </NavLink>
      ))}
      <NavLink to="/account" onClick={onNavigate} className={({ isActive }) => `flex items-center gap-3 rounded px-3 py-2 text-sm ${isActive ? "bg-lens-wash font-medium text-lens-deep" : "text-ink-soft hover:bg-bench"}`}>
        <UserRound className="h-4 w-4" aria-hidden />{user ? user.display_name : "Sign in"}
      </NavLink>
    </nav>
  );
}

export function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="hidden border-r border-rule bg-panel p-4 lg:flex lg:flex-col lg:justify-between">
        <div>
          <p className="mb-6 px-3 font-display text-2xl font-semibold text-lens-deep">LLM Lens</p>
          <Nav />
        </div>
        <div className="px-3"><StatusBadge /></div>
      </aside>

      <header className="flex items-center justify-between border-b border-rule bg-panel px-4 py-3 lg:hidden">
        <p className="font-display text-xl font-semibold text-lens-deep">LLM Lens</p>
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="rounded p-2 text-ink-soft hover:bg-bench"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>
      {open && (
        <div className="border-b border-rule bg-panel p-4 lg:hidden">
          <Nav onNavigate={() => setOpen(false)} />
          <div className="mt-4 px-3"><StatusBadge /></div>
        </div>
      )}

      <div className="min-w-0">
        <DemoBanner />
        <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
