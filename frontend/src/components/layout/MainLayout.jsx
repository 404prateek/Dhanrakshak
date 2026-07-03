import { Outlet, useLocation } from 'react-router-dom';
import { TopNavigation } from './TopNavigation';

export function MainLayout() {
  const location = useLocation();
  const isDashboardRoute = location.pathname.startsWith('/dashboard');

  return (
    <div className="min-h-screen bg-[var(--bg)] text-slate-900">
      {!isDashboardRoute && <TopNavigation />}
      <main className={isDashboardRoute ? 'main-content w-full' : 'main-content mx-auto w-full max-w-[1440px] px-6 py-6 pt-[112px]'}>
        <Outlet />
      </main>
    </div>
  );
}
