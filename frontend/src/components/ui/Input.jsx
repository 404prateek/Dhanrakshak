import { forwardRef } from 'react';
import { cn } from '../../utils/helpers';

export const Input = forwardRef(({ className, label, error, icon: Icon, ...props }, ref) => {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-slate-700 mb-1">
          {label}
        </label>
      )}
      <div className="relative rounded-md shadow-sm">
        {Icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon className="h-5 w-5 text-slate-400" />
          </div>
        )}
        <input
          ref={ref}
          className={cn(
            "enterprise-input block w-full",
            Icon && "pl-10",
            error && "border-red-300 text-red-900 placeholder-red-300 focus:ring-red-500 focus:border-red-500",
            className
          )}
          {...props}
        />
      </div>
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
});

Input.displayName = 'Input';
