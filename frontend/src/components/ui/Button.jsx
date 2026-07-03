import { cn } from '../../utils/helpers';

export function Button({ 
  children, 
  variant = 'primary', 
  className, 
  isLoading, 
  disabled, 
  icon: Icon,
  size = 'md',
  ...props 
}) {
  const baseStyles = "inline-flex items-center justify-center rounded-[12px] font-semibold transition-fast focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed h-11"; // h-11 == 44px
  const sizes = {
    sm: 'px-3 text-sm h-10',
    md: 'px-5 text-sm h-11',
    lg: 'px-6 text-base h-12',
  };
  
  const variants = {
    primary: "border-transparent bg-[var(--canara-blue-700)] text-white shadow-sm hover:bg-[var(--canara-blue-600)] focus:ring-[var(--canara-blue-600)]",
    secondary: "border border-[var(--card-border,#E5E7EB)] bg-white text-[var(--primary-text,#0F172A)] hover:bg-slate-50 focus:ring-[var(--canara-blue-100)]",
    danger: "border-transparent bg-[var(--danger,#DC2626)] text-white shadow-sm hover:bg-red-700 focus:ring-red-500",
    ghost: "border-transparent bg-transparent text-[var(--secondary-text,#64748B)] hover:bg-slate-100 shadow-none",
  };

  return (
    <button
      className={cn(baseStyles, sizes[size], variants[variant], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )}
      {Icon && <Icon className="h-4 w-4 mr-2" />}
      {children}
    </button>
  );
}
