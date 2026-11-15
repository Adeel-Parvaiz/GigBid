import { useEffect, useState } from "react";
import { Activity, BriefcaseBusiness, ChartNoAxesCombined, CircleUserRound, LayoutDashboard, LogOut, MessageSquareText, Settings2, Workflow } from "lucide-react";
import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import AnalyticsPage from "./app/analytics/page";
import DashboardPage from "./app/dashboard/page";
import InboxPage from "./app/inbox/page";
import JobDetailPage from "./app/jobs/[id]/page";
import LoginPage from "./app/login/page";
import MessagesPage from "./app/messages/page";
import PipelinePage from "./app/pipeline/page";
import RunViewerPage from "./app/runs/[id]/page";
import SettingsPage from "./app/settings/page";
import StudioPage from "./app/studio/[id]/page";
import { api, tokenStore } from "./lib/http";

function Shell() {
  const nav = useNavigate();
  const location = useLocation();
  const [degraded, setDegraded] = useState(false); const [queued, setQueued] = useState(0);
  useEffect(() => {
    let live = true;
    let wasDegraded = false;
    const poll = async () => {
      try { const { data } = await api.GET("/health"); if (live && data) {
        const down = data.marketplace === "degraded";
        setDegraded(down); setQueued(data.queued_degraded_runs);
        if (wasDegraded && !down) window.dispatchEvent(new Event("gigbid:marketplace-restored"));
        wasDegraded = down;
      } }
      catch { if (live) { setDegraded(true); wasDegraded = true; } }
    };
    poll(); const t = setInterval(poll, 8000);
    return () => { live = false; clearInterval(t); };
  }, []);
  if (!tokenStore.get()) return <Navigate to="/login" replace />;
  const links = [
    { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/inbox", label: "Job inbox", icon: BriefcaseBusiness },
    { to: "/pipeline", label: "Pipeline", icon: Workflow },
    { to: "/messages", label: "Messages", icon: MessageSquareText },
    { to: "/analytics", label: "Analytics", icon: ChartNoAxesCombined },
    { to: "/settings", label: "Settings", icon: Settings2 },
  ];
  const currentLabel = links.find(({ to, end }) => end ? location.pathname === to : location.pathname === to || location.pathname.startsWith(`${to}/`))?.label ?? "Workspace";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand" aria-label="GigBid overview">
          <span className="brand-mark"><Activity size={18} strokeWidth={2.4} /></span>GigBid
        </Link>
        <div className="nav-caption">Workspace</div>
        <nav className="main-nav" aria-label="Main">
          {links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
            <Icon size={17} strokeWidth={1.8} /><span>{label === "Job inbox" ? "Inbox" : label}</span>
          </NavLink>)}
        </nav>
        <div className="sidebar-bottom">
          <button onClick={() => { tokenStore.clear(); nav("/login"); }}><LogOut size={16} />Sign out</button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-label">{currentLabel}</div>
          <div className="topbar-actions">
            <span className="connection-pill" aria-label={degraded ? "Marketplace unavailable" : "Marketplace available"}>
              <span className={`connection-dot${degraded ? " bad" : ""}`} />
              <span>{degraded ? "Marketplace unavailable" : "Marketplace available"}</span>
            </span>
            <span className="user-icon" aria-label="Signed-in user"><CircleUserRound size={20} /></span>
          </div>
        </header>
        {degraded && <div role="alert" className="banner bad" data-testid="degraded-banner">
          <Activity size={17} />Marketplace unavailable. New work is queued{queued ? ` (${queued} waiting)` : ""} and resumes automatically when it is back.
        </div>}
        <main><Outlet /></main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Shell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          <Route path="/studio/:id" element={<StudioPage />} />
          <Route path="/runs/:id" element={<RunViewerPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
