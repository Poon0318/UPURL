import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, AlertCircle, ArrowUp, Check, CircleAlert, Clock3, Globe2, LoaderCircle, Play, Plus, Radar, RefreshCw, Search, ShieldCheck, Signal, Upload } from 'lucide-react'
import { api } from './services/api.js'
import SiteTable from './components/SiteTable.jsx'
import SiteDrawer from './components/SiteDrawer.jsx'
import WebsiteForm from './components/WebsiteForm.jsx'

const filters = [
  { key: 'ALL', label: 'All websites' },
  { key: 'UP', label: 'Up' },
  { key: 'DOWN', label: 'Down' },
  { key: 'URL_MISMATCH', label: 'URL mismatch' },
  { key: 'HTTP_ERROR', label: 'HTTP error' },
]

const metricDetails = [
  { key: 'total', label: 'Total websites', Icon: Globe2, tone: 'neutral', helper: 'Configured targets' },
  { key: 'up', label: 'Up', Icon: Check, tone: 'up', helper: 'Responding as expected' },
  { key: 'down', label: 'Down', Icon: Signal, tone: 'down', helper: 'Network or server failure' },
  { key: 'url_mismatch', label: 'URL mismatch', Icon: ArrowUp, tone: 'mismatch', helper: 'Unexpected destination' },
  { key: 'http_error', label: 'HTTP error', Icon: AlertCircle, tone: 'http', helper: 'Unexpected response' },
]

function formatLastUpdated(value) {
  if (!value) return 'Waiting for first check'
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value))
}

export default function App() {
  const [dashboard, setDashboard] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [formWebsite, setFormWebsite] = useState(undefined)
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [importing, setImporting] = useState(false)
  const uploadRef = useRef(null)

  async function refresh(showSpinner = false) {
    if (showSpinner) setLoading(true)
    try {
      const data = await api.status()
      setDashboard(data)
      setError('')
    } catch (issue) {
      setError(issue.message || 'Can’t connect to the monitoring API.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh(true)
    const timer = window.setInterval(() => refresh(), 15000)
    return () => window.clearInterval(timer)
  }, [])

  const sites = dashboard?.websites || []
  const summary = dashboard?.summary || { total: 0, up: 0, down: 0, url_mismatch: 0, http_error: 0 }
  const monitoringLabel = error ? 'API unavailable' : loading ? 'Connecting' : dashboard?.monitoring_active ? 'Monitoring active' : 'Monitoring stopped'
  const filteredSites = useMemo(() => sites.filter((site) => {
    const matchesStatus = filter === 'ALL' || site.status === filter
    const needle = search.trim().toLowerCase()
    const matchesSearch = !needle || `${site.name} ${site.expected_url} ${site.actual_url || ''}`.toLowerCase().includes(needle)
    return matchesStatus && matchesSearch
  }), [sites, filter, search])

  async function checkNow() {
    setChecking(true)
    setNotice('')
    try {
      await api.checkAll()
      await refresh()
      setNotice('All enabled websites checked.')
    } catch (issue) {
      setError(issue.message || 'The check could not be completed.')
    } finally {
      setChecking(false)
    }
  }

  async function saveWebsite(values) {
    if (formWebsite?.id) await api.update(formWebsite.id, values)
    else if (Array.isArray(values)) await api.createMany(values)
    else await api.create(values)
    await refresh()
    setNotice(formWebsite?.id
      ? 'Website configuration updated.'
      : `${Array.isArray(values) ? values.length : 1} website${Array.isArray(values) && values.length !== 1 ? 's' : ''} added to monitoring.`)
  }

  async function importCsv(file) {
    setImporting(true)
    setError('')
    setNotice('')
    try {
      const result = await api.importCsv(file)
      setFilter('ALL')
      setSearch('')
      await refresh()
      setNotice(`${result.inserted} website${result.inserted === 1 ? '' : 's'} imported.`)
    } catch (issue) {
      setError(issue.message || 'The CSV could not be imported.')
    } finally {
      setImporting(false)
    }
  }

  async function deleteWebsite(site) {
    if (!window.confirm(`Remove ${site.name} and its stored history?`)) return
    try {
      await api.remove(site.id)
      setSelectedId(null)
      await refresh()
      setNotice('Website and its history removed.')
    } catch (issue) {
      setError(issue.message)
    }
  }

  async function checkSingle(id) {
    setChecking(true)
    try {
      await api.checkOne(id)
      await refresh()
      setSelectedId(null)
    } catch (issue) {
      setError(issue.message || 'The check could not be completed.')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="side-rail">
        <a className="brand-mark" href="#top" aria-label="UPURL home"><span><Activity size={20} strokeWidth={2.6} /></span><b>UPURL</b></a>
        <div className="rail-divider" />
        <button className="rail-link rail-active" title="Monitoring dashboard"><Radar size={19} /><span>Monitor</span></button>
        <div className="rail-spacer" />
        <div className="rail-health"><span className="rail-pulse" /><span>LOCAL<br />MONITOR</span></div>
      </aside>

      <main className="main-content" id="top">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>Website monitor</strong></div>
          <div className="topbar-right"><div className={`live-indicator ${error || (dashboard && !dashboard.monitoring_active) ? 'live-offline' : ''}`}><span />{monitoringLabel}</div><span className="topbar-divider" /><span className="interval-label"><Clock3 size={14} /> Every {dashboard?.monitoring_interval_seconds || 60}s</span></div>
        </header>

        <div className="page-wrap">
          <section className="page-heading">
            <div><div className="eyebrow heading-eyebrow"><span className="eyebrow-line" /> SYSTEM OVERVIEW</div><h1>Website monitor</h1><p>Live health and destination checks for your web properties.</p></div>
            <div className="heading-actions"><button className="button button-quiet refresh-button" onClick={() => refresh(true)} disabled={loading} title="Refresh dashboard"><RefreshCw size={15} className={loading ? 'spin' : ''} /><span>Refresh</span></button><button className="button button-primary" onClick={checkNow} disabled={checking}><span className={`check-action-icon ${checking ? 'button-spinner' : ''}`}>{checking ? <LoaderCircle size={15} /> : <Play size={14} fill="currentColor" />}</span>{checking ? 'Checking…' : 'Check now'}</button><button className="button button-quiet" onClick={() => uploadRef.current?.click()} disabled={importing} title="Import multiple websites from CSV"><Upload size={15} />{importing ? 'Importing…' : 'Import CSV'}</button><input ref={uploadRef} className="sr-only" type="file" accept=".csv,text/csv" aria-label="Choose website CSV file" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) importCsv(file) }} /><button className="button button-add" onClick={() => setFormWebsite(null)}><Plus size={16} />Add website</button></div>
          </section>

          {error && <div className="system-banner system-error"><CircleAlert size={17} /><span>{error}</span><button onClick={() => setError('')}>Dismiss</button></div>}
          {notice && !error && <div className="system-banner system-notice"><Check size={16} /><span>{notice}</span><button onClick={() => setNotice('')}>Dismiss</button></div>}

          <section className="metrics-grid" aria-label="Website status summary">
            {metricDetails.map(({ key, label, Icon, tone, helper }) => <article className={`metric-card metric-${tone}`} key={key}><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={16} strokeWidth={2.1} /></span></div><div className="metric-value">{loading && !dashboard ? <span className="skeleton-value" /> : summary[key] || 0}</div><div className="metric-helper">{helper}</div></article>)}
          </section>

          <section className="monitor-panel">
            <div className="panel-heading"><div><div className="eyebrow">LIVE TARGETS <span className="target-count">{summary.enabled || 0} ENABLED</span></div><h2>All websites</h2></div><div className="panel-updated"><span className="updated-dot" />Last updated <strong>{formatLastUpdated(dashboard?.last_updated)}</strong></div></div>
            <div className="table-toolbar"><div className="filter-tabs" role="tablist" aria-label="Filter websites">{filters.map((item) => <button className={`filter-tab ${filter === item.key ? 'filter-selected' : ''}`} key={item.key} onClick={() => setFilter(item.key)} role="tab" aria-selected={filter === item.key}>{item.label}{item.key !== 'ALL' && summary[item.key.toLowerCase()] > 0 && <span className="filter-count">{summary[item.key.toLowerCase()]}</span>}</button>)}</div><label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search websites" aria-label="Search by website name or URL" /></label></div>
            <SiteTable sites={filteredSites} onSelect={setSelectedId} />
            <footer className="table-footer"><span>Showing <strong>{filteredSites.length}</strong> of <strong>{sites.length}</strong> websites</span><span className="auto-refresh-note"><span className="auto-refresh-dot" />Auto-refreshes every 15 seconds</span></footer>
          </section>
          <footer className="page-footer"><span><ShieldCheck size={14} />HTTP(S) checks are authoritative. ICMP is not used for health status.</span><span>UPURL · Local deployment</span></footer>
        </div>
      </main>

      {selectedId && <SiteDrawer websiteId={selectedId} onClose={() => setSelectedId(null)} onEdit={(site) => { setFormWebsite(site); setSelectedId(null) }} onDelete={deleteWebsite} onCheck={checkSingle} />}
      {formWebsite !== undefined && <WebsiteForm website={formWebsite} onClose={() => setFormWebsite(undefined)} onSave={saveWebsite} />}
    </div>
  )
}