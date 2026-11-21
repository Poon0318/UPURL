import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

const emptyForm = {
  name: '',
  expected_url: '',
  expected_status_code: 200,
  expected_final_url: '',
  expected_text: '',
  enabled: true,
  allow_scheme_mismatch: false,
}

export default function WebsiteForm({ website, onClose, onSave }) {
  const [values, setValues] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const urlCount = values.expected_url.split(/[,\n]+/).filter((url) => url.trim()).length

  useEffect(() => {
    if (website) setValues({ ...emptyForm, ...website })
  }, [website])

  function update(key, value) {
    setValues((current) => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const urls = values.expected_url.split(/[,\n]+/).map((url) => url.trim()).filter(Boolean)
      if (!urls.length) throw new Error('Enter at least one website URL.')

      const websites = urls.map((url) => {
        let parsedUrl
        try {
          parsedUrl = new URL(url)
        } catch {
          throw new Error(`Enter a valid website URL: ${url}`)
        }
        if (!['http:', 'https:'].includes(parsedUrl.protocol) || !parsedUrl.hostname) {
          throw new Error(`Enter a valid HTTP or HTTPS website URL: ${url}`)
        }
        return {
          ...values,
          name: urls.length === 1 && values.name.trim() ? values.name.trim() : parsedUrl.hostname,
          expected_url: url,
          expected_status_code: Number(values.expected_status_code),
          expected_final_url: values.expected_final_url || null,
          expected_text: values.expected_text || null,
        }
      })

      await onSave(websites.length === 1 ? websites[0] : websites)
      onClose()
    } catch (issue) {
      setError(issue.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="website-modal" role="dialog" aria-modal="true" aria-labelledby="website-form-title">
        <div className="modal-heading">
          <div><span className="eyebrow">MONITOR CONFIGURATION</span><h2 id="website-form-title">{website ? 'Edit website' : urlCount > 1 ? 'Add websites' : 'Add website'}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close form"><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <label className="field-label">Website name {!website && <span className="optional-label">Optional for one website; bulk entries use each domain</span>}<input autoFocus required={Boolean(website)} maxLength="160" value={values.name} onChange={(event) => update('name', event.target.value)} placeholder="Customer portal" /></label>
          <label className="field-label">Expected URL{!website && 's'}<textarea required rows="3" value={values.expected_url} onChange={(event) => update('expected_url', event.target.value)} placeholder="https://service.example.com, https://shop.example.com" aria-describedby="website-url-hint" /></label>
          {!website && <span className="field-hint" id="website-url-hint">Separate URLs with commas or new lines. Each website will be added directly to monitoring.</span>}
          <div className="field-grid">
            <label className="field-label">Expected HTTP status<input type="number" min="100" max="599" value={values.expected_status_code} onChange={(event) => update('expected_status_code', event.target.value)} /></label>
            <label className="field-label">Expected final URL <span className="optional-label">Optional</span><input type="url" value={values.expected_final_url || ''} onChange={(event) => update('expected_final_url', event.target.value)} placeholder="Same as expected URL" /></label>
          </div>
          <label className="field-label">Expected page text <span className="optional-label">Optional</span><input value={values.expected_text || ''} onChange={(event) => update('expected_text', event.target.value)} placeholder="A phrase that must appear on the page" /></label>
          <div className="form-toggles">
            <label className="toggle-line"><input type="checkbox" checked={values.enabled} onChange={(event) => update('enabled', event.target.checked)} /><span>Monitoring enabled</span></label>
            <label className="toggle-line"><input type="checkbox" checked={values.allow_scheme_mismatch} onChange={(event) => update('allow_scheme_mismatch', event.target.checked)} /><span>Allow HTTP / HTTPS difference</span></label>
          </div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="modal-actions"><button className="button button-quiet" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={saving}>{saving ? 'Saving…' : website ? 'Save changes' : `Add ${urlCount > 1 ? `${urlCount} websites` : 'website'}`}</button></div>
        </form>
      </section>
    </div>
  )
}