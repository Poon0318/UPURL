import { ArrowUpRight, Globe2 } from 'lucide-react'
import StatusPill from './StatusPill.jsx'

function shortUrl(value) {
  if (!value) return '—'
  try {
    const url = new URL(value)
    return `${url.host}${url.pathname === '/' ? '' : url.pathname}${url.search}`
  } catch {
    return value
  }
}

function checkedTime(value) {
  if (!value) return 'Waiting for first check'
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value))
}

export default function SiteTable({ sites, onSelect }) {
  if (!sites.length) {
    return <div className="empty-table"><Globe2 size={22} /><strong>No websites match</strong><span>Try another search or status filter.</span></div>
  }

  return (
    <div className="table-scroll">
      <table className="site-table">
        <thead>
          <tr>
            <th>Website</th>
            <th>Expected URL</th>
            <th>Actual URL</th>
            <th>Status</th>
            <th>HTTP</th>
            <th>Response</th>
            <th>Last checked</th>
            <th>Error</th>
            <th><span className="sr-only">Open details</span></th>
          </tr>
        </thead>
        <tbody>
          {sites.map((site) => (
            <tr key={site.id} onClick={() => onSelect(site.id)} className={`site-row row-${site.status.toLowerCase()}`} tabIndex="0" onKeyDown={(event) => event.key === 'Enter' && onSelect(site.id)}>
              <td>
                <div className="site-name-cell">
                  <span className={`site-glyph glyph-${site.status.toLowerCase()}`}><Globe2 size={15} /></span>
                  <span className="site-title-wrap"><strong>{site.name}</strong><small>{site.enabled ? 'Monitoring enabled' : 'Monitoring paused'}</small></span>
                </div>
              </td>
              <td><span className="url-cell" title={site.expected_url}>{shortUrl(site.expected_url)}</span></td>
              <td><span className={`url-cell ${site.status === 'URL_MISMATCH' ? 'url-different' : ''}`} title={site.actual_url || 'Not checked'}>{shortUrl(site.actual_url)}</span></td>
              <td><StatusPill status={site.status} /></td>
              <td><span className={`http-code ${site.http_status_code >= 400 ? 'http-bad' : ''}`}>{site.http_status_code || '—'}</span></td>
              <td><span className="response-time">{site.response_time_ms == null ? '—' : `${Math.round(site.response_time_ms)} ms`}</span></td>
              <td><span className="checked-time">{checkedTime(site.checked_at)}</span></td>
              <td><span className={`error-cell ${site.error_message ? 'has-error' : ''}`} title={site.error_message || ''}>{site.error_message || '—'}</span></td>
              <td><ArrowUpRight size={16} className="row-open" aria-hidden="true" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}