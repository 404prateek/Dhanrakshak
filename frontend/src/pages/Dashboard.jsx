import { useQuery } from '@tanstack/react-query';
import { 
  Briefcase, AlertTriangle, FileCheck, ShieldAlert, CheckCircle 
} from 'lucide-react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { StatCard } from '../components/ui/StatCard';
import { Table } from '../components/ui/Table';
import { StatusPill, RiskBadge } from '../components/ui/Badges';
import { formatDate } from '../utils/helpers';
import { api } from '../services/api';

const riskTrendData = [
  { name: "Jan", highRisk: 40, mediumRisk: 24, lowRisk: 24 },
  { name: "Feb", highRisk: 30, mediumRisk: 13, lowRisk: 22 },
  { name: "Mar", highRisk: 20, mediumRisk: 58, lowRisk: 29 },
  { name: "Apr", highRisk: 27, mediumRisk: 39, lowRisk: 20 },
  { name: "May", highRisk: 18, mediumRisk: 48, lowRisk: 21 },
  { name: "Jun", highRisk: 23, mediumRisk: 38, lowRisk: 25 },
];

const fraudCategoryData = [
  { name: 'Income Falsification', value: 400 },
  { name: 'Property Title Fraud', value: 300 },
  { name: 'Identity Theft', value: 300 },
  { name: 'Synthetic Identity', value: 200 },
];

const COLORS = ['#1d4ed8', '#3b82f6', '#93c5fd', '#1e3a8a'];

export function Dashboard() {
  const { data: cases = [], isLoading, isError } = useQuery({
    queryKey: ['cases'],
    queryFn: api.getCases,
  });

  const recentCasesColumns = [
    { header: 'Case ID', accessorKey: 'id', cell: (row) => `CASE-${row.id}` },
    { header: 'Applicant', accessorKey: 'applicant_name' },
    { header: 'Status', cell: (row) => <StatusPill status={row.status} /> },
    { header: 'Risk Score', cell: (row) => <RiskBadge score={row.risk_score} /> },
    { header: 'Created', cell: (row) => formatDate(row.created_at) },
  ];

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-red-50 text-red-600 p-4 rounded-md flex items-center">
        <ShieldAlert className="w-5 h-5 mr-2" />
        Failed to load dashboard data. Please try again later.
      </div>
    );
  }

  const totalCases = cases.length;
  const highRiskCases = cases.filter(c => c.risk_score > 75).length;
  const activeInvestigations = cases.filter(c => c.status === 'Open' || c.status === 'Under Review').length;
  // Documents would ideally come from an aggregate endpoint. Mocking for now based on case count.
  const uploadedDocs = cases.reduce((acc, c) => acc + (c.documents?.length || 0), 0);
  
  const highRiskList = cases.filter(c => c.risk_score > 75).sort((a, b) => b.risk_score - a.risk_score).slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard Overview</h1>
          <p className="mt-1 text-sm text-slate-500">Real-time fraud monitoring and underwriting metrics.</p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Cases" value={totalCases.toString()} icon={Briefcase} trend="neutral" trendValue="Live" color="blue" />
        <StatCard title="High Risk Cases" value={highRiskCases.toString()} icon={AlertTriangle} trend="neutral" trendValue="Live" color="red" />
        <StatCard title="Active Investigations" value={activeInvestigations.toString()} icon={ShieldAlert} trend="neutral" trendValue="Live" color="amber" />
        <StatCard title="Uploaded Documents" value={uploadedDocs > 0 ? uploadedDocs.toString() : 'N/A'} icon={FileCheck} trend="neutral" trendValue="Live" color="emerald" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="enterprise-card p-6 lg:col-span-2 flex flex-col h-96">
          <h3 className="text-lg font-medium text-slate-900 mb-4">Risk Trend Analysis (Sample)</h3>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={riskTrendData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b' }} />
                <RechartsTooltip 
                  contentStyle={{ borderRadius: '0.5rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)' }}
                />
                <Area type="monotone" dataKey="highRisk" stackId="1" stroke="#ef4444" fill="#fee2e2" name="High Risk" />
                <Area type="monotone" dataKey="mediumRisk" stackId="1" stroke="#f59e0b" fill="#fef3c7" name="Medium Risk" />
                <Area type="monotone" dataKey="lowRisk" stackId="1" stroke="#10b981" fill="#d1fae5" name="Low Risk" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="enterprise-card p-6 flex flex-col h-96">
          <h3 className="text-lg font-medium text-slate-900 mb-4">Fraud Categories (Sample)</h3>
          <div className="flex-1 min-h-0 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={fraudCategoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {fraudCategoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip />
                <Legend verticalAlign="bottom" height={36} iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="enterprise-card lg:col-span-2">
          <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-white">
            <h3 className="text-lg font-medium text-slate-900">Recent Cases</h3>
          </div>
          <Table columns={recentCasesColumns} data={cases.slice(0, 5)} />
        </div>

        <div className="enterprise-card bg-slate-900 text-white">
          <div className="px-6 py-4 border-b border-slate-800">
            <h3 className="text-lg font-medium text-white flex items-center">
              <ShieldAlert className="w-5 h-5 mr-2 text-red-500" />
              Action Required
            </h3>
          </div>
          <div className="divide-y divide-slate-800">
            {highRiskList.length > 0 ? highRiskList.map(caseItem => (
              <div key={caseItem.id} className="p-4 hover:bg-slate-800 transition-colors cursor-pointer">
                <div className="flex justify-between">
                  <span className="font-medium text-blue-400">CASE-{caseItem.id}</span>
                  <span className="text-xs text-slate-400">{formatDate(caseItem.created_at)}</span>
                </div>
                <p className="text-sm mt-1">{caseItem.applicant_name}</p>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs bg-red-900/50 text-red-400 px-2 py-1 rounded">High Risk Score: {caseItem.risk_score}</span>
                  <button className="text-xs text-slate-300 hover:text-white underline">Review</button>
                </div>
              </div>
            )) : (
              <div className="p-4 text-slate-400 text-sm">No high risk cases currently require action.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
