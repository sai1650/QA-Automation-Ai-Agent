import { useEffect, useMemo, useState } from 'react'
import {
  Activity, Archive, Bell, BookOpen, Bot, Bug, ChevronDown, ChevronsLeft,
  ChevronsRight, FlaskConical, FolderKanban, Gauge, LayoutDashboard, Menu,
  Moon, Search, Settings, ShieldCheck, Sun, X,
} from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, healthURL } from '../api/client'
import { executionsApi } from '../api/resources'
import { Button, IconButton } from '../components'

const groups = [
  {
    label: 'WORKSPACE',
    links: [
      { label: 'Overview', path: '/', icon: LayoutDashboard },
      { label: 'Projects', path: '/projects', icon: FolderKanban },
      { label: 'Executions', path: '/executions', icon: Activity },
    ],
  },
  {
    label: 'INTELLIGENCE',
    links: [
      { label: 'Bug intelligence', path: '/bugs', icon: Bug },
      { label: 'Knowledge base', path: '/knowledge', icon: BookOpen },
      { label: 'AI agents', path: '/agents', icon: Bot },
      { label: 'Evaluations', path: '/evaluations', icon: FlaskConical },
    ],
  },
  {
    label: 'REPORTING',
    links: [
      { label: 'Test reports', path: '/reports', icon: Archive },
      { label: 'Analytics', path: '/analytics', icon: Gauge },
    ],
  },
  {
    label: 'SYSTEM',
    links: [{ label: 'Settings', path: '/settings', icon: Settings }],
  },
]

const routeTitles: Record<string, string> = {
  '/': 'Overview',
  '/projects': 'Projects',
  '/executions': 'Executions',
  '/bugs': 'Bug intelligence',
  '/knowledge': 'Knowledge base',
  '/agents': 'AI agents',
  '/evaluations': 'Evaluations',
  '/reports': 'Test reports',
  '/analytics': 'Analytics',
  '/settings': 'Settings',
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    window.localStorage.getItem('qa-theme') === 'light' ? 'light' : 'dark',
  )
  const [search, setSearch] = useState('')
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const basePath = location.pathname.startsWith('/projects/')
    ? '/projects'
    : location.pathname.startsWith('/executions/')
      ? '/executions'
      : location.pathname
  const title = useMemo(() => routeTitles[basePath] ?? 'Workspace', [basePath])
  const health = useQuery({
    queryKey: ['api-health'],
    queryFn: async () => (await api.get(healthURL)).data,
    refetchInterval: 60_000,
    retry: 1,
  })
  const recent = useQuery({
    queryKey: ['notification-executions'],
    queryFn: () => executionsApi.list({ page: 1, page_size: 5, status: 'FAILED' }),
    enabled: notificationsOpen,
    retry: 0,
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('qa-theme', theme)
  }, [theme])

  useEffect(() => {
    const handleThemeChange = (event: Event) => {
      const selected = (event as CustomEvent<'dark' | 'light'>).detail
      if (selected === 'dark' || selected === 'light') setTheme(selected)
    }
    window.addEventListener('qa-theme-change', handleThemeChange)
    return () => window.removeEventListener('qa-theme-change', handleThemeChange)
  }, [])

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const term = search.trim()
    if (!term) return
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    navigate(uuidPattern.test(term) ? `/executions/${term}` : `/projects?search=${encodeURIComponent(term)}`)
    setSearch('')
  }

  const sidebar = (
    <>
      <div className="brand">
        <div className="brand-mark"><ShieldCheck size={18} strokeWidth={2.2} /></div>
        {!collapsed && <div className="brand-copy"><strong>Autonomous QA</strong><span>INTELLIGENCE PLATFORM</span></div>}
        <IconButton className="sidebar-collapse" label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        </IconButton>
      </div>
      <nav className="side-nav" aria-label="Main navigation">
        {groups.map((group) => (
          <div className="nav-group" key={group.label}>
            {!collapsed && <div className="nav-label">{group.label}</div>}
            {group.links.map(({ label, path, icon: Icon }) => (
              <NavLink key={path} to={path} end={path === '/'} title={collapsed ? label : undefined}
                onClick={() => { setMobileOpen(false); setNotificationsOpen(false); setProfileOpen(false) }}
                className={({ isActive }) => `nav-link ${isActive || (path !== '/' && location.pathname.startsWith(`${path}/`)) ? 'active' : ''}`}>
                <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className={`api-state ${health.isSuccess ? 'online' : health.isLoading ? 'checking' : 'offline'}`}>
          <span className="status-dot" />
          {!collapsed && <span>{health.isSuccess ? 'API connected' : health.isLoading ? 'Checking API' : 'API unavailable'}</span>}
        </div>
        {!collapsed && <div className="workspace-profile"><div className="avatar">QA</div><div><strong>Local workspace</strong><span>Development</span></div><ChevronDown size={14} /></div>}
      </div>
    </>
  )

  return (
    <div className="app-shell">
      <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>{sidebar}</aside>
      {mobileOpen && <div className="mobile-backdrop" onClick={() => setMobileOpen(false)} />}
      <aside className={`mobile-sidebar ${mobileOpen ? 'mobile-sidebar-open' : ''}`}>
        <IconButton className="mobile-close" label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></IconButton>
        {sidebar}
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-leading">
            <IconButton className="mobile-menu" label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19} /></IconButton>
            <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{title}</strong></div>
          </div>
          <div className="topbar-actions">
            <form className="global-search" role="search" onSubmit={submitSearch}>
              <Search size={15} /><input aria-label="Search projects or open execution by ID" placeholder="Search projects or paste execution ID" value={search} onChange={(event) => setSearch(event.target.value)} />
              <kbd>↵</kbd>
            </form>
            <div className="popover-wrap">
              <IconButton label="Notifications" onClick={() => { setNotificationsOpen(!notificationsOpen); setProfileOpen(false) }}><Bell size={17} /></IconButton>
              {notificationsOpen && <div className="popover notification-popover">
                <div className="popover-title">Failed executions <span className="live-tag">LIVE</span></div>
                {recent.isLoading ? <p className="muted">Loading recent failures…</p> : recent.error ? <p className="muted">Could not load notifications.</p> : recent.data?.items.length
                  ? recent.data.items.map((item) => <button className="notification-item" key={item.id} onClick={() => navigate(`/executions/${item.id}`)}><span className="notification-dot" /><span><strong>{item.id.slice(0, 8)}</strong><small>{new Date(item.created_at).toLocaleString()}</small></span></button>)
                  : <p className="muted">No failed executions in the latest results.</p>}
              </div>}
            </div>
            <IconButton label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </IconButton>
            <div className="popover-wrap">
              <Button variant="profile" className="profile-button" onClick={() => { setProfileOpen(!profileOpen); setNotificationsOpen(false) }}>
                <span className="avatar avatar-small">QA</span><span className="profile-label">Workspace</span><ChevronDown size={14} />
              </Button>
              {profileOpen && <div className="popover profile-popover"><strong>Local development</strong><p className="muted">Authentication is not configured in the backend.</p><Button variant="secondary" onClick={() => navigate('/settings')}>Workspace settings</Button></div>}
            </div>
          </div>
        </header>
        <main className="page-content"><Outlet /></main>
        <footer className="app-footer"><span>Autonomous QA Intelligence Platform</span><span>Local workspace · Not authenticated</span></footer>
      </div>
    </div>
  )
}
