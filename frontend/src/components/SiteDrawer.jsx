import { useEffect, useState } from 'react'
import { Activity, Clock3, ExternalLink, Pencil, RefreshCw, Server, ShieldCheck, Trash2, Wifi, X } from 'lucide-react'
import { api } from '../services/api.js'
import StatusPill from './StatusPill.jsx'

function displayDate(value) {
  if (!value) return 'No check recorded'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value))
}

export default function SiteDrawer({ websiteId, onClose, onEdit, onDelete, onCheck }) {
  const [detail, setDetail] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let live = true
    setLoading(true)
    Promise.all([api.detail(websiteId), api.history(websiteId)])
      .then(([current, records]) => {
        if (!live) return
        setDetail(current)
        setHistory(records)
      })
      .catch(() => live && setDetail(null))
      .finally(() => live && setLoading(false))
    return () => { live = false }
  }, [websiteId])

  const site = detail?.website
  const latest = detail?.latest
  const status = latest?.status || 'UNKNOWN'
  const chartRecords = history.slice(-36)

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="detail-drawer" aria-label="Website details">
        <header className="drawer-topbar"><span className="eyebrow">WEBSITE DETAIL</span><button className="icon-button" onClick={onClose} aria-label="Close details"><X size={18} /></button></header>
        {loading ? <div className="drawer-loading"><RefreshCw size={20} className="spin" />Loading check history</div> : site ? (
          <>
            <div className="drawer-title-row"><div><h2>{site.name}</h2><span className="muted-copy">Added to monitor</span></div><StatusPill status={status} /></div>
            <div className={`detail-incident incident-${status.toLowerCase()}`}>
              <div className="incident-icon"><Activity size={17} /></div>
              <div><strong>{latest?.error_message || (status === 'UP' ? 'Application responded as expected' : 'Awaiting first health check')}</strong><span>{latest?.checked_at ? `Last result · ${displayDate(latest.checked_at)}` : 'The first result will appear after a check.'}</span></div>
            </div>
            <div className="detail-actions"><button className="button button-primary" onClick={() => onCheck(site.id)}><RefreshCw size={15} />Check now</button><button className="button button-quiet" onClick={() => onEdit(site)}><Pencil size={15} />Edit</button><button className="icon-button danger-icon" onClick={() => onDelete(site)} aria-label="Delete website"><Trash2 size={16} /></button></div>
            <section className="detail-section"><div className="section-heading"><div><span className="eyebrow">URL VERIFICATION</span><h3>Destination</h3></div><ShieldCheck size={18} /></div>
              <div className="url-comparison"><span>Configured URL</span><a href={site.expected_url} target="_blank" rel="noreferrer">{site.expected_url}<ExternalLink size={13} /></a>{site.expected_final_url && <><span>Expected final URL</span><a href={site.expected_final_url} target="_blank" rel="noreferrer">{site.expected_final_url}<ExternalLink size={13} /></a></>}<span>Actual final URL</span><a className={latest?.status === 'URL_MISMATCH' ? 'url-failure' : ''} href={latest?.actual_url || site.expected_url} target="_blank" rel="noreferrer">{latest?.actual_url || 'Not checked yet'}<ExternalLink size={13} /></a></div>
              {latest?.redirect_chain?.length > 0 && <div className="redirect-list"><span className="eyebrow">REDIRECT CHAIN</span>{latest.redirect_chain.map((hop, index) => <div className="redirect-hop" key={`${hop.url}-${index}`}><span>{hop.status_code}</span><code>{hop.url}</code></div>)}</div>}
            </section>
            <section className="detail-section"><div className="section-heading"><div><span className="eyebrow">CONNECTIVITY</span><h3>Check results</h3></div><Wifi size={18} /></div>
              <div className="check-grid"><div><span><Wifi size={14} />DNS</span><strong className={latest?.dns_ok ? 'check-pass' : 'check-fail'}>{latest ? latest.dns_ok ? 'PASS' : 'FAILED' : '—'}</strong></div><div><span><Server size={14} />Connection</span><strong className={latest?.connection_ok ? 'check-pass' : 'check-fail'}>{latest ? latest.connection_ok ? 'PASS' : 'FAILED' : '—'}</strong></div><div><span><Activity size={14} />HTTP status</span><strong className={latest?.http_status_code >= 400 ? 'check-fail' : 'check-pass'}>{latest?.http_status_code || '—'}</strong></div><div><span><Clock3 size={14} />Response time</span><strong>{latest?.response_time_ms == null ? '—' : `${Math.round(latest.response_time_ms)} ms`}</strong></div></div>
              <div className="last-checks"><span>Last successful check<strong>{displayDate(detail.last_successful_check)}</strong></span><span>Last failed check<strong>{displayDate(detail.last_failed_check)}</strong></span></div>
            </section>
            <section className="detail-section history-section"><div className="section-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h3>Check history</h3></div><span className="history-count">{history.length} checks</span></div>
              {chartRecords.length ? <div className="history-chart" role="img" aria-label="Recent check history by status">{chartRecords.map((record) => <span key={record.id} title={`${displayDate(record.checked_at)} · ${record.status}`} className={`history-bar bar-${record.status.toLowerCase()}`} />)}</div> : <div className="history-empty">History will build as checks run.</div>}
              <div className="chart-legend"><span><i className="legend-up" />UP</span><span><i className="legend-down" />DOWN</span><span><i className="legend-mismatch" />MISMATCH</span><span><i className="legend-http" />HTTP ERROR</span></div>
            </section>
          </>
        ) : <div className="drawer-loading">Couldn’t load website details.</div>}
      </aside>
    </div>
  )
}