import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Download, Filter } from 'lucide-react';
import { Table } from '../components/ui/Table';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badges';
import { api } from '../services/api';
import { formatDate } from '../utils/helpers';

export function AuditLogs() {
  const [searchTerm, setSearchTerm] = useState('');

  const { data: auditLogs = [], isLoading } = useQuery({
    queryKey: ['audit'],
    queryFn: api.getAuditLogs,
  });

  const filteredLogs = auditLogs.filter(log => 
    (log.action || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
    (log.case_ref || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.ip_address || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.result || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns = [
    { header: 'Timestamp', cell: (row) => <span className="text-xs">{formatDate(row.timestamp)} {new Date(row.timestamp).toLocaleTimeString('en-IN')}</span> },
    { header: 'User ID', accessorKey: 'user_id', cell: (row) => row.user_id ? `USR-${row.user_id}` : 'System' },
    { header: 'Action', accessorKey: 'action' },
    { header: 'Case Ref', accessorKey: 'case_ref', cell: (row) => row.case_ref || 'N/A' },
    { header: 'IP Address', cell: (row) => <span className="font-mono text-xs">{row.ip_address || 'N/A'}</span> },
    { header: 'Result', cell: (row) => (
      <Badge variant={(row.result || '').includes('Success') ? 'success' : 'danger'}>
        {row.result}
      </Badge>
    ) },
  ];

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-6rem)]">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">System Audit Logs</h1>
          <p className="mt-1 text-sm text-slate-500">Immutable record of all system access and actions.</p>
        </div>
        <Button icon={Download} variant="secondary">Export Logs</Button>
      </div>

      <div className="enterprise-card flex-1 flex flex-col min-h-0">
        <div className="p-4 border-b border-slate-200 bg-white flex flex-wrap gap-4 items-center justify-between">
          <div className="w-full sm:max-w-md">
            <Input 
              icon={Search} 
              placeholder="Search by Action, Case ID, or IP..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="secondary" icon={Filter}>Advanced Filters</Button>
            <Input type="date" className="w-40" />
            <span className="text-slate-500 text-sm">to</span>
            <Input type="date" className="w-40" />
          </div>
        </div>
        
        <div className="flex-1 overflow-auto bg-slate-50">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <Table columns={columns} data={filteredLogs} className="h-full bg-white" />
          )}
        </div>
        
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-slate-500">
          <div>Showing {filteredLogs.length > 0 ? 1 : 0} to {filteredLogs.length} of {filteredLogs.length} events</div>
          <div className="flex space-x-2">
            <Button variant="secondary" disabled>Previous</Button>
            <Button variant="secondary" disabled>Next</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
