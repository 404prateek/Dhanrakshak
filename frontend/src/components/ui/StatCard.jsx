import { cn } from '../../utils/helpers';

export function StatCard({ title, value, icon: Icon, trend, trendValue, color = 'blue', onClick }) {
  const colorMap = {
    blue: 'text-[var(--canara-blue-700)] bg-[var(--canara-blue-50,#EFF6FF)] border-[var(--canara-blue-100,#DBEAFE)]',
    red: 'text-[var(--danger,#DC2626)] bg-red-50 border-red-100',
    amber: 'text-amber-700 bg-amber-50 border-amber-100',
    emerald: 'text-emerald-700 bg-emerald-50 border-emerald-100',
    slate: 'text-[var(--primary-text,#0F172A)] bg-slate-50 border-slate-100',
  };

  const isClickable = typeof onClick === 'function';

  const handleKeyDown = (e) => {
    if (!isClickable) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      onClick={onClick}
      role={isClickable ? 'button' : 'region'}
      tabIndex={isClickable ? 0 : -1}
      onKeyDown={handleKeyDown}
      className={cn('enterprise-card relative overflow-hidden p-5 hover:shadow-md transition-medium', isClickable && 'cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-100')}
      aria-pressed={isClickable ? false : undefined}
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-[var(--canara-blue-700)]" />
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[13px] font-medium uppercase tracking-[0.14em] text-[var(--secondary-text,#64748B)] truncate">{title}</p>
          <p className="mt-2 text-[34px] leading-none font-bold text-[var(--primary-text,#0F172A)] truncate">{value}</p>
        </div>
        {Icon && (
          <div className={cn('rounded-2xl p-3 border flex items-center justify-center shadow-sm', colorMap[color])}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      {trendValue && (
        <div className="mt-3 flex items-center justify-between">
          <div className="text-sm text-[var(--secondary-text,#64748B)]">
            <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold', trend === 'up' ? 'bg-emerald-50 text-emerald-700' : trend === 'down' ? 'bg-red-50 text-red-700' : 'bg-slate-50 text-slate-600')}>{trend === 'up' ? '↑' : trend === 'down' ? '↓' : '–'} {trendValue}</span>
            <span className="ml-2 text-xs text-slate-400">from last period</span>
          </div>
          <div className="text-xs text-slate-400">Live</div>
        </div>
      )}
    </div>
  );
}
