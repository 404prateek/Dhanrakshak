import { Outlet } from 'react-router-dom';

// Auth is fully bypassed — all routes are accessible as the hardcoded Admin.
// This component exists only to preserve the route structure; it always renders.
export function ProtectedRoute() {
  return <Outlet />;
}

