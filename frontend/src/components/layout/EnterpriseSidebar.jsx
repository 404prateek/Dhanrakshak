import { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  Search,
  FileText,
  ShieldAlert,
  Users,
  Settings,
  LogOut,
  Menu,
  UploadCloud,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../../utils/helpers';
import { useAuth } from '../../context/AuthContext';

export function EnterpriseSidebar() {
  // Static sidebar: always expanded for enterprise layout
  const collapsed = false;
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const match = location.pathname.match(/\/(investigation|fraud-reports)\/(\d+)/);
  const currentCaseId = match ? match[2] : null;

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', basePath: '/dashboard', icon: LayoutDashboard },
    { name: 'Data Ingestion', path: '/ingest', basePath: '/ingest', icon: UploadCloud },
    { name: 'Cases', path: '/cases', basePath: '/cases', icon: Briefcase },
    { name: 'Investigation', path: currentCaseId ? `/investigation/${currentCaseId}` : '#', basePath: '/investigation', icon: Search, requiresCase: true },
    { name: 'Fraud Reports', path: currentCaseId ? `/fraud-reports/${currentCaseId}` : '#', basePath: '/fraud-reports', icon: FileText, requiresCase: true },
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

  const [sidebarOnly, setSidebarOnly] = useState(false);

  const toggleSidebarOnly = () => {
    setSidebarOnly(v => {
      const next = !v;
      try {
        if (next) document.body.classList.add('sidebar-only'); else document.body.classList.remove('sidebar-only');
      } catch (e) {}
      return next;
    });
  };

  return (
    <div
      className={cn(
        'flex flex-col h-screen transition-all duration-300 border-r w-64',
        'border-slate-200'
      )}
      style={{ background: 'var(--bg)' }}
    >
      <div className="flex items-center justify-between h-16 px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--canara-blue-700)] text-xl font-bold text-white shadow-sm">
            D
          </div>
          <div>
            <p className="text-sm font-semibold tracking-[0.02em] text-slate-900">Dhanrakshak</p>
            <p className="text-xs text-slate-500">Fraud Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleSidebarOnly}
            className={cn('rounded-full p-2 text-slate-600 transition-fast hover:bg-slate-100', sidebarOnly && 'bg-slate-100')}
            aria-pressed={sidebarOnly}
            aria-label="Show only sidebar"
            title="Show only sidebar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="16" rx="2" ry="2"/><rect x="7" y="8" width="4" height="8"/></svg>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-5 px-3">

        <nav className="space-y-2">
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.basePath);
            return (
              <NavLink
                key={item.name}
                to={item.path}
                onClick={(e) => handleNavClick(e, item)}
                className={cn('flex items-center gap-3 px-3 py-2 text-sm rounded-[12px] transition-fast',
                  isActive ? 'bg-blue-50 text-[var(--canara-blue-700)] font-semibold' : 'text-slate-700 hover:bg-slate-50'
                )}
              >
                {/* left active indicator */}
                {!collapsed && isActive && <span className="w-1 h-6 rounded-r-full bg-[var(--canara-blue-700)]" />}
                <item.icon className={cn('flex-shrink-0', collapsed ? 'mx-auto w-5 h-5' : 'w-4 h-4')} />
                {!collapsed && <span>{item.name}</span>}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Removed Tip panel per design: keep sidebar clean and professional */}

      <div className="px-4 pb-5">
        <div className="enterprise-panel p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-sm font-semibold text-slate-900">{user?.full_name?.substring(0, 2) ?? 'DR'}</div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-900 leading-5">{user?.full_name || 'System Administrator'}</p>
                <p className="text-xs text-slate-500 leading-4">{user?.role?.name || 'Admin'}</p>
              </div>
            )}
          </div>
          {!collapsed && (
            <button
              onClick={handleLogout}
              className="mt-4 enterprise-btn w-full bg-[var(--canara-blue-700)] text-white"
            >
              <LogOut className="mr-2 h-4 w-4 inline-block" />
              Sign Out
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
