import { useEffect, useState } from 'react'
import { Check, LockKeyhole, Moon, Sun } from 'lucide-react'
import { api } from '../api/client'
import { useQuery } from '@tanstack/react-query'
import { Badge, Card, PageHeader, LoadingState } from '../components'
import { knowledgeApi } from '../api/resources'

export function SettingsPage() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => window.localStorage.getItem('qa-theme') === 'light' ? 'light' : 'dark')
  const health = useQuery({ queryKey: ['knowledge-health'], queryFn: knowledgeApi.health, retry: 0 })
  const apiBase = api.defaults.baseURL ?? 'Not configured'

  useEffect(() => {
    const handleTheme = (event: Event) => {
      const next = (event as CustomEvent<'dark' | 'light'>).detail
      if (next === 'dark' || next === 'light') setTheme(next)
    }
    window.addEventListener('qa-theme-change', handleTheme)
    return () => window.removeEventListener('qa-theme-change', handleTheme)
  }, [])

  function changeTheme(next: 'dark' | 'light') {
    window.localStorage.setItem('qa-theme', next)
    document.documentElement.dataset.theme = next
    setTheme(next)
    window.dispatchEvent(new CustomEvent('qa-theme-change', { detail: next }))
  }

  return <>
    <PageHeader eyebrow="System" title="Settings" description="Frontend preferences and backend capabilities. Backend environment settings are not writable from this application." />
    <div className="settings-grid">
      <Card><div className="card-heading"><div><span className="eyebrow">APPEARANCE</span><h2>Theme</h2></div></div><p className="muted">Theme preference is stored locally in this browser; no backend configuration changes.</p><div className="theme-options"><button className={`theme-option ${theme === 'dark' ? 'selected' : ''}`} onClick={() => changeTheme('dark')}><Moon size={18} /><span><strong>Dark</strong><small>Default workspace theme</small></span>{theme === 'dark' && <Check size={16} />}</button><button className={`theme-option ${theme === 'light' ? 'selected' : ''}`} onClick={() => changeTheme('light')}><Sun size={18} /><span><strong>Light</strong><small>Bright workspace surfaces</small></span>{theme === 'light' && <Check size={16} />}</button></div></Card>
      <Card><div className="card-heading"><div><span className="eyebrow">CONNECTION</span><h2>API endpoint</h2></div><Badge tone="blue">READ ONLY</Badge></div><dl className="details-list"><div><dt>Base URL</dt><dd><code>{apiBase}</code></dd></div><div><dt>Timeout</dt><dd>20 seconds (inspection/evaluation requests use longer timeouts)</dd></div><div><dt>Health</dt><dd><Badge tone={health.data ? 'success' : 'warning'}>{health.isLoading ? 'Checking' : health.data ? 'Reachable' : 'Unavailable'}</Badge></dd></div></dl><p className="form-note">Set <code>VITE_API_BASE_URL</code> in the frontend environment to change the API location. Restart the dev server after changes.</p></Card>
      <Card><div className="card-heading"><div><span className="eyebrow">AI PROVIDER</span><h2>Provider and model</h2></div><LockKeyhole size={17} className="muted" /></div><div className="capability-row"><span>Provider</span><strong>Backend-configured</strong></div><div className="capability-row"><span>Model</span><strong>Not exposed by a settings endpoint</strong></div><p className="muted form-note">Evaluation responses may include provider/model identifiers. The frontend cannot modify provider settings and never handles provider credentials.</p></Card>
      <Card><div className="card-heading"><div><span className="eyebrow">RETRIEVAL</span><h2>RAG configuration</h2></div><Badge tone={health.data?.available ? 'success' : 'neutral'}>{health.data?.available ? 'AVAILABLE' : 'STATUS ONLY'}</Badge></div>{health.isLoading ? <LoadingState /> : health.data ? <dl className="details-list"><div><dt>Enabled</dt><dd>{health.data.enabled ? 'Yes' : 'No'}</dd></div><div><dt>Embedding model</dt><dd>{health.data.embedding_model}</dd></div><div><dt>Collection</dt><dd>{health.data.collection_name}</dd></div><div><dt>Service status</dt><dd>{health.data.available ? 'Available' : `Unavailable${health.data.error_category ? ` (${health.data.error_category})` : ''}`}</dd></div></dl> : <p className="muted">Knowledge health endpoint could not be reached.</p>}<p className="form-note">RAG configuration is managed by the backend environment; no write endpoint exists.</p></Card>
      <Card><div className="card-heading"><div><span className="eyebrow">SECURITY</span><h2>Access control</h2></div><Badge tone="warning">NOT CONFIGURED</Badge></div><p>Backend authentication and project-scoped authorization are not implemented. Confirmation checkboxes are explicit user assertions, not authorization checks.</p><p className="muted form-note">Do not expose this service publicly or treat client-side visibility as access control. Add and verify backend authentication before production deployment.</p></Card>
      <Card><div className="card-heading"><div><span className="eyebrow">BROWSER</span><h2>Inspection policy</h2></div><Badge tone="blue">BACKEND MANAGED</Badge></div><p>Browser inspection is read-only and restricted by backend target validation. Only GET/HEAD requests are allowed; interactive actions are not executed.</p><p className="muted form-note">Timeouts, screenshot limits, model settings, notifications, and browser behavior are not configurable through the current API.</p></Card>
    </div>
  </>
}
