import { cn } from '../../utils/helpers';

export function Badge({ children, variant = 'default', className }) {
  const variants = {
    default: "bg-slate-100 text-slate-800 border-slate-200",
    primary: "bg-blue-100 text-blue-800 border-blue-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warning: "bg-amber-100 text-amber-800 border-amber-200",
    danger: "bg-red-100 text-red-800 border-red-200",
  };

  return (
    <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border", variants[variant], className)}>
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
    <div className="flex items-center space-x-2">
      <Badge variant={variant}>{label}</Badge>
      <span className={cn("text-sm font-semibold", 
        score >= 80 ? 'text-red-600' : score >= 50 ? 'text-amber-600' : 'text-emerald-600'
      )}>
        {score}/100
      </span>
    </div>
  );
}

export function StatusPill({ status }) {
  const normalized = status.toLowerCase();
  let variant = 'default';
  
  if (normalized.includes('verified') || normalized.includes('pass') || normalized.includes('success') || normalized === 'active') variant = 'success';
  if (normalized.includes('flagged') || normalized.includes('fail') || normalized.includes('inactive')) variant = 'danger';
  if (normalized.includes('pending') || normalized.includes('progress') || normalized.includes('warning')) variant = 'warning';

  return <Badge variant={variant}>{status}</Badge>;
}
