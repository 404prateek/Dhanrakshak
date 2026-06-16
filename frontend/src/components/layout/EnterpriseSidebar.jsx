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
  Menu
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../../utils/helpers';
import { useAuth } from '../../context/AuthContext';

export function EnterpriseSidebar() {
  const [collapsed, setCollapsed] = useState(false);
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

  return (
    <div className={cn(
      "flex flex-col h-screen bg-slate-900 text-slate-300 transition-all duration-300 border-r border-slate-800",
      collapsed ? "w-20" : "w-64"
    )}>
      {/* Logo Area */}
      <div className="flex items-center justify-between h-16 px-4 bg-slate-950 border-b border-slate-800">
        {!collapsed && (
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">DhanRakshak</span>
          </div>
        )}
        {collapsed && (
          <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center mx-auto">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
        )}
        <button 
          onClick={() => setCollapsed(!collapsed)}
          className={cn("p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors", collapsed && "hidden")}
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* Nav Links */}
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.basePath);
            return (
              <NavLink
                key={item.name}
                to={item.path}
                onClick={(e) => handleNavClick(e, item)}
                className={cn(
                  "flex items-center px-3 py-2.5 text-sm font-medium rounded-md transition-colors group",
                  isActive
                    ? "bg-blue-600 text-white" 
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                )}
              >
              <item.icon className={cn("flex-shrink-0 w-5 h-5", collapsed ? "mx-auto" : "mr-3")} />
              {!collapsed && <span>{item.name}</span>}
            </NavLink>
            );
          })}
        </nav>
      </div>

      {/* User Area */}
      <div className="p-4 bg-slate-950 border-t border-slate-800">
        <div className="flex items-center">
          <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-300 flex-shrink-0 uppercase font-bold text-sm">
            {user?.full_name ? user.full_name.substring(0, 2) : 'DR'}
          </div>
          {!collapsed && (
            <div className="ml-3 flex-1 overflow-hidden">
              <p className="text-sm font-medium text-white truncate">{user?.full_name || 'System Admin'}</p>
              <p className="text-xs text-slate-400 truncate">{user?.role?.name || 'Admin'}</p>
            </div>
          )}
        </div>
        {!collapsed && (
          <button 
            onClick={handleLogout}
            className="mt-4 flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800 border border-slate-700 rounded-md hover:bg-slate-700 hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </button>
        )}
      </div>
    </div>
  );
}
