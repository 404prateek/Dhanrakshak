import { Bell, Search, UserCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export function TopNavigation() {
  const { user } = useAuth();

  return (
    <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-6 z-10 relative">
      <div className="flex-1 flex items-center">
        <div className="max-w-md w-full relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-slate-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-md leading-5 bg-slate-50 placeholder-slate-400 focus:outline-none focus:bg-white focus:ring-1 focus:ring-primary focus:border-primary sm:text-sm transition-colors"
            placeholder="Search cases, users, or reports..."
          />
        </div>
      </div>
      
      <div className="ml-4 flex items-center space-x-4">
        <button className="p-1 rounded-full text-slate-400 hover:text-slate-500 focus:outline-none relative">
          <span className="absolute top-1 right-1 block h-2 w-2 rounded-full bg-red-500 ring-2 ring-white"></span>
          <Bell className="h-6 w-6" />
        </button>
        
        <div className="flex items-center space-x-3 border-l border-slate-200 pl-4">
          <div className="flex flex-col text-right">
            <span className="text-sm font-medium text-slate-700">{user?.full_name || 'System Admin'}</span>
            <span className="text-xs text-blue-600 font-medium bg-blue-50 px-2 py-0.5 rounded-full inline-block mt-0.5">{user?.role?.name || 'Admin'}</span>
          </div>
          <UserCircle className="h-9 w-9 text-slate-400" />
        </div>
      </div>
    </header>
  );
}
