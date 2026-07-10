import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Search, Filter, Download, Plus, X } from 'lucide-react';
import { Table } from '../components/ui/Table';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { StatusPill, RiskBadge } from '../components/ui/Badges';
import { formatDate } from '../utils/helpers';
import { api } from '../services/api';

// ── New Case Modal ────────────────────────────────────────────────
function NewCaseModal({ onClose }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    case_ref: '',
    applicant_name: '',
    property_address: '',
    risk_score: '',
    status: 'Pending Review',
  });

  const createMutation = useMutation({
    mutationFn: (data) => api.createCase(data),
    onSuccess: (newCase) => {
      toast.success('Case created successfully');
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      onClose();
      navigate(`/investigation/${newCase.id}`);
    },
    onError: (err) => {
      toast.error('Failed to create case', {
        description: err.response?.data?.detail || 'An error occurred'
      });
    },
  });

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.case_ref.trim() || !form.applicant_name.trim() || !form.property_address.trim()) {
      toast.warning('Please fill in all required fields.');
      return;
    }
    createMutation.mutate({
      ...form,
      risk_score: parseFloat(form.risk_score) || 0,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-[24px] shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <h2 className="text-lg font-bold text-slate-900">New Investigation Case</h2>
          <button onClick={onClose} className="p-1.5 rounded-[18px] hover:bg-slate-200 transition-colors text-slate-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
              Case Reference <span className="text-red-500">*</span>
            </label>
            <input
              name="case_ref"
              value={form.case_ref}
              onChange={handleChange}
              placeholder="e.g. CASE-2024-001"
              className="enterprise-input w-full"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
              Applicant Name <span className="text-red-500">*</span>
            </label>
            <input
              name="applicant_name"
              value={form.applicant_name}
              onChange={handleChange}
              placeholder="Full name of the applicant"
              className="enterprise-input w-full"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
              Property Address <span className="text-red-500">*</span>
            </label>
            <input
              name="property_address"
              value={form.property_address}
              onChange={handleChange}
              placeholder="Full property address"
              className="enterprise-input w-full"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                Initial Status
              </label>
              <select name="status" value={form.status} onChange={handleChange} className="enterprise-input w-full">
                <option value="Pending Review">Pending Review</option>
                <option value="Open">Open</option>
                <option value="Under Review">Under Review</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                Initial Risk Score
              </label>
              <input
                name="risk_score"
                type="number"
                min="0"
                max="100"
                value={form.risk_score}
                onChange={handleChange}
                placeholder="0 – 100"
                className="enterprise-input w-full"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-2 border-t border-slate-100">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            <Button
              type="submit"
              variant="primary"
              icon={Plus}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Case'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────
export function CaseManagement() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All Statuses');
  const [riskFilter, setRiskFilter] = useState('All Risk Levels');
  const [showNewCaseModal, setShowNewCaseModal] = useState(false);
  
  const { data: cases = [], isLoading, isError } = useQuery({
    queryKey: ['cases'],
    queryFn: api.getCases,
  });

  const filteredCases = cases.filter(c => {
    const matchesSearch = 
      c.id.toString().includes(searchTerm) || 
      c.applicant_name.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = 
      statusFilter === 'All Statuses' || c.status === statusFilter;

    const matchesRisk =
      riskFilter === 'All Risk Levels' ||
      (riskFilter === 'High Risk' && c.risk_score > 75) ||
      (riskFilter === 'Medium Risk' && c.risk_score > 40 && c.risk_score <= 75) ||
      (riskFilter === 'Low Risk' && c.risk_score <= 40);

    return matchesSearch && matchesStatus && matchesRisk;
  });

  const columns = [
    { header: 'Case ID', accessorKey: 'id', cell: (row) => `CASE-${row.id}` },
    { header: 'Applicant', accessorKey: 'applicant_name' },
    { header: 'Property', accessorKey: 'property_address', cell: (row) => <span className="truncate max-w-[200px] inline-block" title={row.property_address}>{row.property_address}</span> },
    { header: 'Status', cell: (row) => <StatusPill status={row.status} /> },
    { header: 'Risk Score', cell: (row) => <RiskBadge score={row.risk_score} /> },
    { header: 'Created Date', cell: (row) => formatDate(row.created_at) },
    { header: 'Actions', cell: (row) => (
        <Button variant="ghost" className="text-blue-600" onClick={() => navigate(`/investigation/${row.id}`)}>
          Investigate
        </Button>
      ) 
    },
  ];

  return (
    <>
      {showNewCaseModal && <NewCaseModal onClose={() => setShowNewCaseModal(false)} />}

      <div className="space-y-6 flex flex-col h-[calc(100vh-6rem)]">
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Case Management</h1>
            <p className="mt-1 text-sm text-slate-500">Manage and track fraud investigation cases.</p>
          </div>
          <div className="flex items-center space-x-2">
            <Button icon={Download} variant="secondary">Export to CSV</Button>
            <Button icon={Plus} variant="primary" onClick={() => setShowNewCaseModal(true)}>
              New Case
            </Button>
          </div>
        </div>

        <div className="enterprise-card flex-1 flex flex-col min-h-0">
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex flex-wrap gap-4 items-center justify-between rounded-t-[24px]">
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
              <select
                className="enterprise-input w-44"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option>All Statuses</option>
                <option>Pending Review</option>
                <option>Open</option>
                <option>Under Review</option>
                <option>APPROVED</option>
                <option>FRAUD_CONFIRMED</option>
              </select>
              <select
                className="enterprise-input w-40"
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
              >
                <option>All Risk Levels</option>
                <option>High Risk</option>
                <option>Medium Risk</option>
                <option>Low Risk</option>
              </select>
            </div>
          </div>
          
          <div className="flex-1 overflow-auto rounded-b-[24px]">
            {isLoading ? (
               <div className="flex h-full items-center justify-center">
                 <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
               </div>
            ) : isError ? (
               <div className="flex h-full items-center justify-center text-red-500">
                 Failed to load cases.
               </div>
            ) : filteredCases.length === 0 ? (
               <div className="flex h-full items-center justify-center text-slate-400 flex-col space-y-2">
                 <Search className="w-10 h-10 opacity-30" />
                 <p className="text-sm font-medium">No cases match your filters.</p>
               </div>
            ) : (
              <Table columns={columns} data={filteredCases} className="h-full" />
            )}
          </div>
          
          <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-slate-500">
            <div>Showing {filteredCases.length} of {cases.length} cases</div>
            <div className="flex space-x-2">
              <Button variant="secondary" disabled>Previous</Button>
              <Button variant="secondary" disabled>Next</Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
