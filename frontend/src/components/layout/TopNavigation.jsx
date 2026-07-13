import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Bell, UserCircle, LayoutDashboard, UploadCloud, Briefcase, SearchCheck, FileText, ShieldAlert, Users, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../../utils/helpers';

export function TopNavigation() {
  const navigate = useNavigate();
  const location = useLocation();

  const match = location.pathname.match(/\/(investigation|fraud-reports)\/(\d+)/);
  const currentCaseId = match ? match[2] : null;

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', basePath: '/dashboard', icon: LayoutDashboard },
    { name: 'Data Ingestion', path: '/ingest', basePath: '/ingest', icon: UploadCloud },
    { name: 'Cases', path: '/cases', basePath: '/cases', icon: Briefcase },
    { name: 'Investigation', path: currentCaseId ? `/investigation/${currentCaseId}` : '/cases', basePath: '/investigation', icon: SearchCheck, requiresCase: true },
    { name: 'Fraud Reports', path: currentCaseId ? `/fraud-reports/${currentCaseId}` : '/cases', basePath: '/fraud-reports', icon: FileText, requiresCase: true },
    { name: 'Audit Logs', path: '/audit-logs', basePath: '/audit-logs', icon: ShieldAlert },
    { name: 'Users', path: '/users', basePath: '/users', icon: Users },
    { name: 'Settings', path: '/settings', basePath: '/settings', icon: Settings },
  ];

  const handleNavClick = (e, item) => {
    if (item.requiresCase && !currentCaseId) {
      e.preventDefault();
      toast.info('Please select a case from the Cases table first.');
      navigate('/cases');
    }
  };

  return (
    <header className="fixed inset-x-0 top-0 z-30 border-b border-[var(--border)] bg-white shadow-[0_2px_12px_rgba(15,23,42,0.04)]">
      <div className="mx-auto flex h-[56px] max-w-[1440px] items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="Dhanrakshak Logo" className="h-10 w-auto object-contain" />
          </div>
          <div className="h-7 w-px bg-slate-300" />
          <h1 className="text-[20px] font-bold tracking-[-0.03em] text-[var(--canara-blue-700)]">Fraud Detection Dashboard</h1>
        </div>

        <div className="flex items-center gap-4">
          <button className="relative inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-700 transition-fast hover:bg-slate-100">
            <Bell className="h-5 w-5 text-[var(--canara-blue-700)]" />
            <span className="absolute right-[3px] top-[3px] h-2.5 w-2.5 rounded-full bg-red-500 shadow-sm" />
          </button>
          <button className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[var(--canara-blue-700)] text-white shadow-sm transition-fast hover:shadow-md">
            <UserCircle className="h-7 w-7" />
          </button>
        </div>
      </div>

      <div className="border-t border-[var(--border)] bg-white">
        <nav className="mx-auto flex h-[50px] max-w-[1440px] items-center gap-8 overflow-x-auto whitespace-nowrap px-6 text-[15px] font-medium">
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.basePath);
            return (
              <NavLink
                key={item.name}
                to={item.path}
                onClick={(e) => handleNavClick(e, item)}
                className={cn(
                  'relative inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-slate-700 transition-colors hover:text-[var(--canara-blue-700)]',
                  isActive && 'border-[var(--canara-blue-700)] text-[var(--canara-blue-700)] font-semibold'
                )}
              >
                <item.icon className="h-4 w-4" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
