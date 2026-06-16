import { Outlet } from 'react-router-dom';
import { EnterpriseSidebar } from './EnterpriseSidebar';
import { TopNavigation } from './TopNavigation';

export function MainLayout() {
  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <EnterpriseSidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopNavigation />
        <main className="flex-1 overflow-y-auto p-6 bg-slate-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
