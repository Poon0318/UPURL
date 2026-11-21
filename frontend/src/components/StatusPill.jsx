import { CircleCheck, CircleX, TriangleAlert, CircleHelp } from 'lucide-react'

const statusConfig = {
  UP: { label: 'UP', Icon: CircleCheck },
  DOWN: { label: 'DOWN', Icon: CircleX },
  URL_MISMATCH: { label: 'URL MISMATCH', Icon: TriangleAlert },
  HTTP_ERROR: { label: 'HTTP ERROR', Icon: TriangleAlert },
  UNKNOWN: { label: 'NOT CHECKED', Icon: CircleHelp },
}

export default function StatusPill({ status }) {
  const { label, Icon } = statusConfig[status] || statusConfig.UNKNOWN
  return (
    <span className={`status-pill status-${status?.toLowerCase() || 'unknown'}`}>
      <Icon size={14} strokeWidth={2.2} aria-hidden="true" />
      {label}
    </span>
  )
}