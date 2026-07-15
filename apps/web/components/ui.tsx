import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react"

type ButtonVariant = "primary" | "secondary" | "quiet" | "destructive"

type ActionButtonProps = Readonly<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant
    loading?: boolean
  }
>

export function ActionButton({
  children,
  className = "",
  loading = false,
  variant = "secondary",
  disabled,
  ...props
}: ActionButtonProps) {
  return (
    <button
      aria-busy={loading}
      className={`action-button action-button--${variant} ${className}`}
      disabled={disabled || loading}
      type="button"
      {...props}
    >
      {loading ? (
        <>
          <span aria-hidden="true" className="loading-indicator" />
          <span>처리 중</span>
        </>
      ) : (
        children
      )}
    </button>
  )
}

type StatusTone = "success" | "warning" | "error" | "info" | "neutral"

export function StatusBadge({ label, tone }: Readonly<{ label: string; tone: StatusTone }>) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span aria-hidden="true" className="status-badge__dot" />
      {label}
    </span>
  )
}

type ResearchPanelProps = Readonly<{
  title: string
  description?: string
  children?: ReactNode
  language?: "en" | "ko"
  loading?: boolean
  tone?: "standard" | "recessed" | "highlighted"
}>

export function ResearchPanel({
  title,
  description,
  children,
  language,
  loading = false,
  tone = "standard",
}: ResearchPanelProps) {
  return (
    <section aria-busy={loading} className={`research-panel research-panel--${tone}`}>
      <header className="research-panel__header" lang={language}>
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
      </header>
      <div className="research-panel__body">
        {loading ? (
          <>
            <p className="panel-loading-label">콘텐츠 준비 중</p>
            <div className="panel-skeleton" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </>
        ) : (
          children
        )}
        {loading && <span className="visually-hidden">패널 콘텐츠 로딩 중</span>}
      </div>
    </section>
  )
}

type FormFieldProps = Readonly<
  InputHTMLAttributes<HTMLInputElement> & {
    id: string
    label: string
    helper?: string
    error?: string
    loading?: boolean
  }
>

export function FormField({
  id,
  label,
  helper,
  error,
  loading = false,
  className = "",
  readOnly = false,
  size = 1,
  ...props
}: FormFieldProps) {
  const descriptionId = error || helper || loading ? `${id}-description` : undefined

  return (
    <div className={`form-field ${error ? "form-field--invalid" : ""} ${className}`}>
      <label htmlFor={id}>{label}</label>
      <input
        aria-busy={loading}
        aria-describedby={descriptionId}
        aria-invalid={Boolean(error)}
        id={id}
        readOnly={loading || readOnly}
        size={size}
        {...props}
      />
      {descriptionId && (
        <span className="form-field__message" id={descriptionId}>
          {loading && <span aria-hidden="true" className="loading-indicator" />}
          {error ?? (loading ? "검증 중" : helper)}
        </span>
      )}
    </div>
  )
}
