import { forwardRef } from 'react';
import { cn } from '../../utils/helpers';

export const Input = forwardRef(({ className, label, error, icon: Icon, ...props }, ref) => {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-[14px] font-semibold text-[var(--primary-text,#0F172A)] mb-2 tracking-[0.01em]">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="pointer-events-none absolute inset-y-0 left-0 pl-4 flex items-center">
            <Icon className="h-5 w-5 text-slate-400" />
          </div>
        )}
        <input
          ref={ref}
          className={cn(
            'enterprise-input',
            Icon && 'pl-12',
            error ? 'border-red-300 text-red-900 placeholder-red-300 focus:border-red-500 focus:ring-red-100' : '',
            className
          )}
          {...props}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
});

Input.displayName = 'Input';
