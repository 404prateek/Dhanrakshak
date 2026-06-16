import { cn } from '../../utils/helpers';

export function StatCard({ title, value, icon: Icon, trend, trendValue, color = "blue" }) {
  const colorMap = {
    blue: "text-blue-600 bg-blue-50 border-blue-100",
    red: "text-red-600 bg-red-50 border-red-100",
    amber: "text-amber-600 bg-amber-50 border-amber-100",
    emerald: "text-emerald-600 bg-emerald-50 border-emerald-100",
    slate: "text-slate-600 bg-slate-50 border-slate-100",
  };

  return (
    <div className="enterprise-card p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-500">{title}</h3>
        {Icon && (
          <div className={cn("p-2 rounded-md border", colorMap[color])}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
      <div className="mt-4">
        <p className="text-3xl font-bold text-slate-900">{value}</p>
        {trend && (
          <div className="mt-2 flex items-center text-sm">
            <span className={cn(
              "font-medium",
              trend === 'up' ? (color === 'red' ? 'text-red-600' : 'text-emerald-600') : 
              trend === 'down' ? (color === 'red' ? 'text-emerald-600' : 'text-red-600') : 'text-slate-500'
            )}>
              {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '−'} {trendValue}
            </span>
            <span className="ml-2 text-slate-500">vs last month</span>
          </div>
        )}
      </div>
    </div>
  );
}
