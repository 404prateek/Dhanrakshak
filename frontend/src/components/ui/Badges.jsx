import { cn } from '../../utils/helpers';

export function Badge({ children, variant = 'default', className }) {
  const variants = {
    default: 'bg-slate-100 text-slate-800 border-slate-200',
    primary: 'bg-[var(--canara-blue-100)] text-[var(--canara-blue-700)] border-blue-100',
    success: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    warning: 'bg-amber-100 text-amber-700 border-amber-200',
    danger: 'bg-red-100 text-red-700 border-red-200',
    info: 'bg-slate-100 text-slate-700 border-slate-200',
  };

  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em]', variants[variant], className)}>
      {children}
    </span>
  );
}

export function RiskBadge({ score }) {
  let variant = 'success';
  let label = 'Low Risk';

  if (score >= 80) {
    variant = 'danger';
    label = 'High Risk';
  } else if (score >= 50) {
    variant = 'warning';
    label = 'Medium Risk';
  }

  return (
    <div className="flex items-center gap-2">
      <Badge variant={variant}>{label}</Badge>
      <span className={cn('text-sm font-semibold', score >= 80 ? 'text-red-600' : score >= 50 ? 'text-amber-600' : 'text-emerald-600')}>
        {score}/100
      </span>
    </div>
  );
}

export function StatusPill({ status }) {
  const normalized = (status || '').toLowerCase();
  let variant = 'default';

  if (normalized.includes('approved') || normalized.includes('active') || normalized.includes('success')) variant = 'success';
  if (normalized.includes('fraud') || normalized.includes('rejected') || normalized.includes('fail') || normalized.includes('flagged')) variant = 'danger';
  if (normalized.includes('pending') || normalized.includes('review') || normalized.includes('under review')) variant = 'warning';
  if (normalized.includes('low') || normalized.includes('medium') || normalized.includes('high') || normalized.includes('critical')) variant = 'info';

  return <Badge variant={variant}>{status || 'Unknown'}</Badge>;
}
