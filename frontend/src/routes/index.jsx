import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { Dashboard } from '../pages/Dashboard';
import { CaseManagement } from '../pages/CaseManagement';
import { Investigation } from '../pages/Investigation';
import { FraudReport } from '../pages/FraudReport';
import { AuditLogs } from '../pages/AuditLogs';
import { UserManagement } from '../pages/UserManagement';
import { Settings } from '../pages/Settings';
import { Ingest } from '../pages/Ingest';
import { ProtectedRoute } from './ProtectedRoute';

export function AppRoutes() {
  return (
    <Routes>
      {/* Protected Routes (Authentication bypassed) */}
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="ingest" element={<Ingest />} />
          <Route path="cases" element={<CaseManagement />} />
          
          {/* Contextual Routes - ID required */}
          <Route path="investigation/:id" element={<Investigation />} />
          <Route path="fraud-reports/:id" element={<FraudReport />} />
          
          {/* Role restricted routes */}
          <Route element={<ProtectedRoute allowedRoles={['Admin', 'Auditor', 'Compliance Manager']} />}>
            <Route path="audit-logs" element={<AuditLogs />} />
          </Route>
          
          <Route element={<ProtectedRoute allowedRoles={['Admin', 'Compliance Manager']} />}>
            <Route path="users" element={<UserManagement />} />
          </Route>
          
          <Route path="settings" element={<Settings />} />
        </Route>
      </Route>
      
      {/* Fallback to dashboard instead of login */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
