import { Outlet } from 'react-router-dom';
import { TopNavigation } from './TopNavigation';

export function MainLayout() {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-slate-900">
      <TopNavigation />
      <main className="main-content mx-auto w-full max-w-[1440px] px-6 py-6 pt-[112px]">
        <Outlet />
      </main>
    </div>
  );
}
