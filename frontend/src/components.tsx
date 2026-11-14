import { useState, type FormEvent, type ReactNode } from 'react'
import { AlertCircle, Check, ChevronLeft, ChevronRight, LoaderCircle, X } from 'lucide-react'

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'profile' }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>
}

export function IconButton({
  label,
  children,
  className = '',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button aria-label={label} title={label} className={`icon-button ${className}`.trim()} {...props}>{children}</button>
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p className="muted page-description">{description}</p>}
      </div>
      {action && <div className="page-action">{action}</div>}
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone.toLowerCase().replaceAll('_', '-')}`}>{children}</span>
}

export function StatusBadge({ status }: { status: string }) {
  const tone = ({
    COMPLETED: 'success',
    PASSED: 'success',
    APPROVED: 'success',
    QUEUED: 'blue',
    RUNNING: 'blue',
    WAITING_APPROVAL: 'warning',
    PARTIAL: 'warning',
    FAILED: 'danger',
    REJECTED: 'danger',
    CANCELLED: 'neutral',
    BLOCKED: 'warning',
    NOT_SUPPORTED: 'neutral',
    SKIPPED: 'neutral',
    CRITICAL: 'danger',
    HIGH: 'danger',
    MEDIUM: 'warning',
    LOW: 'blue',
    INFO: 'neutral',
    COMPLETED_WITH_WARNINGS: 'warning',
  } as Record<string, string>)[status] ?? 'neutral'
  return <Badge tone={tone}>{status.replaceAll('_', ' ')}</Badge>
}

export function LoadingState({ label = 'Loading data' }: { label?: string }) {
  return <div className="state-box" role="status"><LoaderCircle className="spin" size={18} />{label}…</div>
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="state-box state-error" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
      {retry && <Button variant="secondary" onClick={retry}>Retry</Button>}
    </div>
  )
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-mark"><Check size={18} /></div><h3>{title}</h3><p>{description}</p>{action}</div>
}

export function Modal({
  open,
  title,
  onClose,
  children,
  wide = false,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}) {
  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-heading"><h2 id="modal-title">{title}</h2><IconButton label="Close dialog" onClick={onClose}><X size={18} /></IconButton></div>
        {children}
      </section>
    </div>
  )
}

export function TextField({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label className="field"><span>{label}</span><input {...props} /></label>
}

export function TextAreaField({
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return <label className="field"><span>{label}</span><textarea {...props} /></label>
}

export function SelectField({
  label,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span><select {...props}>{children}</select></label>
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number
  pageSize: number
  total: number
  onChange: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="pagination">
      <span className="muted">{total === 0 ? 'No records' : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}</span>
      <div className="inline-actions">
        <IconButton label="Previous page" disabled={page <= 1} onClick={() => onChange(page - 1)}><ChevronLeft size={16} /></IconButton>
        <span className="page-count">{page} / {pages}</span>
        <IconButton label="Next page" disabled={page >= pages} onClick={() => onChange(page + 1)}><ChevronRight size={16} /></IconButton>
      </div>
    </div>
  )
}

export function ConfirmCheckbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
}) {
  return <label className="confirm-row"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>{children}</span></label>
}

export function Form({
  onSubmit,
  children,
  className = '',
}: {
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  children: ReactNode
  className?: string
}) {
  const [submitted, setSubmitted] = useState(false)
  return <form className={className} onSubmit={(event) => {
    setSubmitted(true)
    onSubmit(event)
  }} data-submitted={submitted}>{children}</form>
}
