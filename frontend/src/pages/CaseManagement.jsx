import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, Download } from 'lucide-react';
import { Table } from '../components/ui/Table';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { StatusPill, RiskBadge } from '../components/ui/Badges';
import { formatDate } from '../utils/helpers';
import { api } from '../services/api';

export function CaseManagement() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  
  const { data: cases = [], isLoading, isError } = useQuery({
    queryKey: ['cases'],
    queryFn: api.getCases,
  });

  const filteredCases = cases.filter(c => 
    c.id.toString().includes(searchTerm) || 
    c.applicant_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns = [
    { header: 'Case ID', accessorKey: 'id', cell: (row) => `CASE-${row.id}` },
    { header: 'Applicant', accessorKey: 'applicant_name' },
    { header: 'Property', accessorKey: 'property_address', cell: (row) => <span className="truncate max-w-[200px] inline-block" title={row.property_address}>{row.property_address}</span> },
    { header: 'Status', cell: (row) => <StatusPill status={row.status} /> },
    { header: 'Risk Score', cell: (row) => <RiskBadge score={row.risk_score} /> },
    { header: 'Created Date', cell: (row) => formatDate(row.created_at) },
    { header: 'Actions', cell: (row) => (
        <Button variant="ghost" className="text-blue-600" onClick={() => navigate(`/investigation/${row.id}`)}>
          View
        </Button>
      ) 
    },
  ];

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-6rem)]">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Case Management</h1>
          <p className="mt-1 text-sm text-slate-500">Manage and track fraud investigation cases.</p>
        </div>
        <Button icon={Download} variant="secondary">Export to CSV</Button>
      </div>

      <div className="enterprise-card flex-1 flex flex-col min-h-0">
        <div className="p-4 border-b border-slate-200 bg-white flex flex-wrap gap-4 items-center justify-between">
          <div className="w-full sm:max-w-xs">
            <Input 
              icon={Search} 
              placeholder="Search by Case ID or Applicant..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="secondary" icon={Filter}>Filters</Button>
            <select className="enterprise-input w-40">
              <option>All Statuses</option>
              <option>Open</option>
              <option>Under Review</option>
              <option>Closed</option>
            </select>
            <select className="enterprise-input w-40">
              <option>All Risk Levels</option>
              <option>High Risk</option>
              <option>Medium Risk</option>
              <option>Low Risk</option>
            </select>
          </div>
        </div>
        
        <div className="flex-1 overflow-auto">
          {isLoading ? (
             <div className="flex h-full items-center justify-center">
               <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
             </div>
          ) : isError ? (
             <div className="flex h-full items-center justify-center text-red-500">
               Failed to load cases.
             </div>
          ) : (
            <Table columns={columns} data={filteredCases} className="h-full" />
          )}
        </div>
        
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-slate-500">
          <div>Showing {filteredCases.length > 0 ? 1 : 0} to {filteredCases.length} of {filteredCases.length} entries</div>
          <div className="flex space-x-2">
            <Button variant="secondary" disabled>Previous</Button>
            <Button variant="secondary" disabled>Next</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
