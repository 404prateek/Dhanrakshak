import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Chart from 'chart.js/auto';
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  File,
  FileText,
  Filter,
  PieChart,
  Printer,
  RefreshCw,
  Search,
  ShieldAlert,
  Settings as SettingsIcon,
  UploadCloud,
  User,
  Users as UsersIcon,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';

const tabs = ['Dashboard', 'Data Ingestion', 'Case Management', 'Investigation', 'Fraud Report', 'Audit Logs', 'User Management', 'Settings'];

const recentCases = [
  { id: '53820', applicant_name: 'Customer Name', opened: '03-Dec-2023', status: 'Medium', risk: 'High' },
  { id: '37054', applicant_name: 'Account Takeover', opened: '01-Dec-2023', status: 'Medium', risk: 'Medium' },
  { id: '5252441', applicant_name: 'Yogera Kakashami', opened: '05-Dec-2023', status: 'Medium', risk: 'Low' },
  { id: '19550', applicant_name: 'Account Trkara', opened: '02-Dec-2023', status: 'Medium', risk: 'Low' },
  { id: '44840', applicant_name: 'Account Takeover', opened: '09-Dec-2023', status: 'Medium', risk: 'Low' },
];

const auditRows = [
  { time: '03-Dec-2023 14:22', user: 'System', action: 'Case created', result: 'Success' },
  { time: '03-Dec-2023 14:25', user: 'USR-102', action: 'Document upload', result: 'Success' },
  { time: '03-Dec-2023 14:31', user: 'USR-102', action: 'Review request', result: 'Success' },
];

const userRows = [
  { id: 'EMP-001', name: 'System Administrator', role: 'Admin', branch: 'Mumbai HQ' },
  { id: 'EMP-014', name: 'Priya Shah', role: 'Fraud Analyst', branch: 'Delhi Branch' },
  { id: 'EMP-021', name: 'Ankit Rao', role: 'Investigator', branch: 'Bengaluru Branch' },
];

export function Dashboard() {
  const navigate = useNavigate();
  const trendChartRef = useRef(null);
  const categoryChartRef = useRef(null);
  const trendChartInstance = useRef(null);
  const categoryChartInstance = useRef(null);

  const [activeTab, setActiveTab] = useState('Dashboard');
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState('Viewer');
  const [zoomLevel, setZoomLevel] = useState(100);
  const [isCaseModalOpen, setIsCaseModalOpen] = useState(false);
  const [newNote, setNewNote] = useState('');
  const [notes, setNotes] = useState([
    { id: 1, text: 'Initial high-risk pattern match flagged on account withdrawal document profile.', time: '03-Dec-2023 14:22' },
  ]);

  useEffect(() => {
    if (trendChartInstance.current) {
      trendChartInstance.current.destroy();
      trendChartInstance.current = null;
    }
    if (categoryChartInstance.current) {
      categoryChartInstance.current.destroy();
      categoryChartInstance.current = null;
    }

    if (activeTab !== 'Dashboard') return;

    if (trendChartRef.current) {
      trendChartInstance.current = new Chart(trendChartRef.current, {
        type: 'line',
        data: {
          labels: ['Day 5', 'Day 10', 'Day 15', 'Day 20', 'Day 25', 'Day 30'],
          datasets: [
            { label: 'High', data: [110, 40, 75, 45, 35, 85], borderColor: '#1d4ed8', backgroundColor: 'transparent', tension: 0.4, borderWidth: 2.5, pointRadius: 2 },
            { label: 'Medium', data: [50, 35, 52, 40, 48, 38], borderColor: '#0284c7', backgroundColor: 'transparent', tension: 0.4, borderWidth: 2, pointRadius: 2 },
            { label: 'Low', data: [38, 42, 30, 45, 32, 50], borderColor: '#005A9C', backgroundColor: 'transparent', tension: 0.4, borderWidth: 2, pointRadius: 2 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, usePointStyle: true, font: { size: 11, weight: '500' } } } },
          scales: {
            y: { min: 0, max: 120, ticks: { stepSize: 30, font: { size: 11 } }, grid: { color: '#e5e7eb' } },
            x: { grid: { display: false }, ticks: { font: { size: 11 } } },
          },
        },
      });
    }

    if (categoryChartRef.current) {
      categoryChartInstance.current = new Chart(categoryChartRef.current, {
        type: 'bar',
        data: {
          labels: ['Identity Theft', 'Account Takeover', 'Document Forgery', 'Loan Fraud', 'Other'],
          datasets: [{ data: [360, 220, 95, 50, 20], backgroundColor: '#1d4ed8', borderRadius: 2, barThickness: 55 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { min: 0, max: 400, ticks: { stepSize: 100, font: { size: 11 } }, grid: { color: '#e5e7eb' } },
            x: { grid: { display: false }, ticks: { font: { size: 11, weight: '500' }, color: '#4b5563' } },
          },
        },
      });
    }

    return () => {
      if (trendChartInstance.current) trendChartInstance.current.destroy();
      if (categoryChartInstance.current) categoryChartInstance.current.destroy();
    };
  }, [activeTab]);

  const renderDashboard = () => (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[
          ['Total Cases', '785', FileText, 'bg-blue-50 text-blue-600'],
          ['High Risk Cases', '112', AlertTriangle, 'bg-red-50 text-red-500'],
          ['Active Investigations', '45', Search, 'bg-amber-50 text-amber-500'],
          ['Uploaded Documents', '3,450', UploadCloud, 'bg-green-50 text-green-600'],
        ].map(([title, value, Icon, badgeClass]) => (
          <div key={title} className="bg-white p-5 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100 flex justify-between items-start">
            <div className="space-y-1">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">{title}</p>
              <h3 className="text-4xl font-extrabold text-gray-900 tracking-tight">{value}</h3>
            </div>
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-inner ${badgeClass}`}>
              <Icon className="w-6 h-6" />
            </div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="bg-white p-6 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100 flex flex-col justify-between">
          <h4 className="text-sm font-bold text-gray-900 mb-4 tracking-tight">Risk Trend (Last 30 Days)</h4>
          <div className="h-60 relative w-full"><canvas ref={trendChartRef}></canvas></div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100 flex flex-col justify-between">
          <h4 className="text-sm font-bold text-gray-900 mb-4 tracking-tight">Fraud Category Distribution</h4>
          <div className="h-60 relative w-full"><canvas ref={categoryChartRef}></canvas></div>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="bg-white p-5 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100 xl:col-span-2 overflow-x-auto">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-bold text-gray-900 tracking-tight">Recent Cases</h4>
            <button onClick={() => setActiveTab('Case Management')} className="text-[#005A9C] text-sm font-semibold inline-flex items-center gap-1">View all <ArrowRight className="w-4 h-4" /></button>
          </div>
          <table className="w-full min-w-[700px] text-left text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-600 uppercase text-xs font-semibold border-b border-gray-200">
                <th className="py-3 px-4">Case ID</th>
                <th className="py-3 px-4">Customer Name</th>
                <th className="py-3 px-4">Date Opened</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Risk Score</th>
                <th className="py-3 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {recentCases.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-3.5 px-4 font-medium text-gray-900">{row.id}</td>
                  <td className="py-3.5 px-4 text-gray-600">{row.applicant_name}</td>
                  <td className="py-3.5 px-4 text-gray-500">{row.opened}</td>
                  <td className="py-3.5 px-4 text-gray-500">{row.status}</td>
                  <td className="py-3.5 px-4">
                    <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${row.risk === 'High' ? 'bg-red-100 text-red-700' : row.risk === 'Medium' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>{row.risk}</span>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex justify-center gap-2">
                      <button onClick={() => setActiveTab('Investigation')} className="bg-[#005A9C] text-white text-xs px-3 py-1.5 rounded hover:bg-opacity-90 font-medium">Quick Review</button>
                      <button onClick={() => setActiveTab('Fraud Report')} className="bg-red-500 text-white text-xs px-3 py-1.5 rounded hover:bg-opacity-90 font-medium">Review</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-bold text-gray-900 tracking-tight">Action Required Panel</h4>
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Immediate</span>
          </div>
          <div className="space-y-3">
            {[1, 2, 3, 4].map((indexId) => (
              <div key={indexId} className="rounded-xl border border-gray-200 bg-white p-3 flex items-center justify-between shadow-sm hover:bg-gray-50 transition-colors">
                <div>
                  <p className="text-sm font-semibold text-gray-900">High Risk Queue Item #{indexId}</p>
                  <p className="text-xs text-gray-500">Needs investigator review</p>
                </div>
                <button onClick={() => setActiveTab('Investigation')} className="bg-[#005A9C] text-white text-xs px-4 py-1.5 rounded font-bold shadow-sm hover:bg-opacity-95 transition-all">Review</button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );

  const renderDataIngestion = () => (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] p-6">
        <h2 className="text-lg font-bold text-gray-900">Ingest New Operational Source Data</h2>
        <p className="mt-2 text-sm text-gray-500">Initialize a case ledger instance and execute deep structural multi-document compliance scans.</p>
        <div className="mt-6 rounded-2xl border-2 border-dashed border-gray-200 bg-slate-50 p-10 text-center">
          <UploadCloud className="mx-auto h-10 w-10 text-[#005A9C]" />
          <p className="mt-4 text-sm font-semibold text-gray-900">Drag files here or click to select storage volumes</p>
          <p className="mt-1 text-xs text-gray-500">Supported extensions: PDF, XLSX, DOCX, CSV (Max 45MB per upload execution)</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-gray-900">Case Details</h3>
          <span className="text-xs uppercase tracking-wider text-gray-400">Preview</span>
        </div>
        {['case_ref', 'applicant_name', 'property_address'].map((label) => (
          <input key={label} className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm" placeholder={label.replace('_', ' ')} />
        ))}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={() => setActiveTab('Dashboard')} className="px-5 py-2.5 bg-gray-100 text-gray-600 rounded-xl font-bold text-sm">Cancel</button>
          <button onClick={() => setActiveTab('Case Management')} className="px-6 py-2.5 bg-[#005A9C] text-white rounded-xl font-bold text-sm">Create Case & Ingest</button>
        </div>
      </div>
    </div>
  );

  const renderCaseManagement = () => (
    <div className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="p-5 border-b border-gray-200 bg-gray-50 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-3 items-center">
          <button className="px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm font-semibold"><Filter className="inline h-4 w-4 mr-2" />Filters</button>
          <button className="px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm font-semibold"><Download className="inline h-4 w-4 mr-2" />Export CSV</button>
        </div>
        <button onClick={() => setIsCaseModalOpen(true)} className="px-5 py-2.5 bg-[#005A9C] text-white font-bold text-xs uppercase tracking-wider rounded-xl shadow-md">New Case</button>
      </div>
      <div className="p-5">
        <table className="w-full text-left text-sm border-collapse min-w-[700px]">
          <thead>
            <tr className="bg-gray-50 text-gray-600 uppercase text-xs font-semibold border-b border-gray-200">
              <th className="py-3 px-4">Case ID</th>
              <th className="py-3 px-4">Applicant</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Risk Score</th>
              <th className="py-3 px-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {recentCases.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50">
                <td className="py-3.5 px-4 font-medium text-gray-900">CASE-{row.id}</td>
                <td className="py-3.5 px-4 text-gray-600">{row.applicant_name}</td>
                <td className="py-3.5 px-4 text-gray-500">{row.status}</td>
                <td className="py-3.5 px-4 text-gray-500">{row.risk}</td>
                <td className="py-3.5 px-4">
                  <button onClick={() => setActiveTab('Investigation')} className="text-[#005A9C] font-semibold text-sm">Investigate</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {isCaseModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg overflow-hidden rounded-[24px] bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-6 py-4">
              <h2 className="text-lg font-bold text-gray-900">Initialize Operational Ledger Case</h2>
              <button onClick={() => setIsCaseModalOpen(false)}><X className="h-5 w-5 text-gray-500" /></button>
            </div>
            <div className="space-y-4 p-6">
              <input className="enterprise-input w-full" placeholder="Case Reference" />
              <input className="enterprise-input w-full" placeholder="Applicant Name" />
              <input className="enterprise-input w-full" placeholder="Property Address" />
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setIsCaseModalOpen(false)} className="rounded-lg bg-gray-100 px-4 py-2 text-xs font-bold uppercase tracking-wider text-gray-600">Cancel</button>
                <button onClick={() => { setIsCaseModalOpen(false); setActiveTab('Investigation'); }} className="rounded-lg bg-[#005A9C] px-4 py-2 text-xs font-bold uppercase tracking-wider text-white">Create Case</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderInvestigation = () => (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
        <aside className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] p-5 space-y-4">
          <div>
            <h3 className="font-bold text-gray-900">Case Document Registry</h3>
            <p className="text-xs text-gray-500 mt-1">Append asset artifact</p>
          </div>
          {['commercial_invoice_901.pdf', 'balance_sheet_verified.xlsx', 'audit_confirmation_statement.pdf'].map((docName) => (
            <button key={docName} className="w-full rounded-xl border border-gray-200 px-4 py-3 text-left text-sm font-medium text-gray-700 hover:bg-gray-50">{docName}</button>
          ))}
          <button className="w-full rounded-xl border border-dashed border-gray-300 px-4 py-3 text-sm font-semibold text-[#005A9C]">+ Add Document</button>
        </aside>

        <section className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] overflow-hidden">
          <div className="border-b border-gray-200 bg-gray-50 px-5 py-4 flex items-center justify-between">
            <div>
              <h3 className="font-bold text-gray-900">Investigation Workspace</h3>
              <p className="text-xs text-gray-500 mt-1">Select a viewer mode or run an AI analysis pass</p>
            </div>
            <div className="flex items-center gap-2">
              {['Viewer', 'AI Analysis', 'Pair Analysis'].map((wTab) => (
                <button key={wTab} onClick={() => setActiveWorkspaceTab(wTab)} className={`rounded-lg px-3 py-1.5 text-xs font-bold tracking-wide ${activeWorkspaceTab === wTab ? 'bg-[#005A9C] text-white shadow-sm' : 'text-gray-500 hover:text-gray-900'}`}>{wTab}</button>
              ))}
            </div>
          </div>
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white p-3">
              <div className="flex items-center gap-2">
                <button onClick={() => setZoomLevel((z) => Math.max(50, z - 10))} className="rounded-lg border border-gray-200 p-2 text-gray-500"><ZoomOut className="h-4 w-4" /></button>
                <span className="text-sm font-semibold text-gray-700">{zoomLevel}%</span>
                <button onClick={() => setZoomLevel((z) => Math.min(200, z + 10))} className="rounded-lg border border-gray-200 p-2 text-gray-500"><ZoomIn className="h-4 w-4" /></button>
              </div>
              <div className="flex gap-2">
                <button className="rounded-lg border border-gray-200 px-3 py-2 text-xs font-bold text-gray-600">Run Pair Cross-Analysis</button>
                <button onClick={() => setActiveTab('Fraud Report')} className="rounded-lg bg-[#005A9C] px-3 py-2 text-xs font-bold text-white">View Report</button>
              </div>
            </div>
            <div className="min-h-[360px] rounded-xl bg-slate-100 p-6 text-center">
              {activeWorkspaceTab === 'Viewer' && <div className="mx-auto max-w-2xl rounded-2xl bg-white p-8 shadow-sm" style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'top center' }}>
                <h4 className="text-lg font-extrabold text-gray-900">INVOICE LEDGER SUMMARY #INV-90122</h4>
                <p className="mt-2 text-sm text-gray-600">Issuer: Global Logistics Inc. Target Date: 28-Nov-2023</p>
                <div className="mt-6 space-y-2 text-left text-sm text-gray-700">
                  <div className="flex justify-between border-b border-dashed border-gray-200 pb-2"><span>Structural Freight Transport Route Layer</span><span>$42,500.00</span></div>
                  <div className="flex justify-between border-b border-dashed border-gray-200 pb-2"><span>Priority Port Customs Handling Unit</span><span>$12,400.00</span></div>
                  <div className="flex justify-between pt-2 font-extrabold text-[#005A9C]"><span>TOTAL ROUTED VALUE</span><span>$54,900.00</span></div>
                </div>
              </div>}
              {activeWorkspaceTab === 'AI Analysis' && <div className="rounded-2xl bg-white p-8 text-left shadow-sm"><p className="text-xs font-bold uppercase tracking-widest text-gray-500">ML Model Classification Output</p><p className="mt-3 text-sm text-gray-700">Neural analysis identified an extraction footprint anomaly pattern in metadata header structures. Timestamp layers display divergence from sequential logs.</p><div className="mt-4 inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700">Confidence Threshold: 94.2% Anomaly Match</div></div>}
              {activeWorkspaceTab === 'Pair Analysis' && <div className="rounded-2xl bg-white p-8 text-left shadow-sm"><p className="text-sm text-gray-700">Select multiple elements from the left panel registry to calculate cross-document cross-reference vectors.</p><button className="mt-4 rounded-lg bg-[#005A9C] px-4 py-2 text-xs font-bold text-white">Run Pair Cross-Analysis</button></div>}
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] p-5 space-y-4">
            <h3 className="font-bold text-gray-900">Investigation Workspace Diary</h3>
            <div className="space-y-3">
              {notes.map((n) => (
                <div key={n.id} className="rounded-xl bg-gray-50 p-3 text-sm text-gray-700">
                  <p>{n.text}</p>
                  <p className="mt-1 text-[11px] text-gray-500">{n.time}</p>
                </div>
              ))}
            </div>
            <textarea value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder="Append operational desk note updates..." className="h-24 w-full rounded-xl border border-gray-200 p-3 text-xs font-medium focus:border-[#005A9C] focus:outline-none" />
            <button onClick={() => { if (!newNote.trim()) return; setNotes([...notes, { id: Date.now(), text: newNote, time: 'Just Now' }]); setNewNote(''); }} className="w-full rounded-xl border border-gray-200 bg-gray-50 py-2 text-xs font-bold uppercase tracking-wider text-gray-700 hover:bg-gray-100">Save Note</button>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-[0_4px_12px_rgba(0,0,0,0.03)] p-5 space-y-3">
            <h3 className="font-bold text-gray-900">Workflow Actions</h3>
            <button className="w-full rounded-xl bg-[#005A9C] px-4 py-2 text-xs font-bold uppercase tracking-wider text-white">Flag Fraud</button>
            <button className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2 text-xs font-bold uppercase tracking-wider text-gray-700">Approve</button>
          </div>
        </aside>
      </div>
    </div>
  );

  const renderFraudReport = () => (
    <div className="space-y-6 rounded-xl bg-white p-6 shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400">Official Form Matrix</p>
          <h2 className="mt-2 text-2xl font-extrabold text-gray-900">Executive Fraud Compliance Report</h2>
          <p className="mt-1 text-sm text-gray-500">Instance Ledger Mapping Reference: #CASE-2023-8891</p>
        </div>
        <div className="flex gap-3">
          <button className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold"><Printer className="inline h-4 w-4 mr-2" />Print</button>
          <button className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold"><Download className="inline h-4 w-4 mr-2" />PDF</button>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="rounded-2xl border-2 border-red-200 bg-red-50 p-6 text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-gray-500">Calculated Risk Index</p>
          <p className="mt-2 text-7xl font-black text-red-600">94</p>
          <p className="mt-1 text-sm font-bold uppercase tracking-widest text-red-700">/ 100</p>
          <div className="mt-4 space-y-2 text-sm text-gray-700">
            <div className="rounded-lg bg-white px-3 py-2 border border-red-100">Classification Group: Invoice Anomaly</div>
            <div className="rounded-lg bg-white px-3 py-2 border border-red-100">Review Status Layer: Flagged Confirmed</div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-500">Executive Review Summary</h3>
            <p className="mt-3 text-sm leading-7 text-gray-700">Deep structural network tracing identified automated text alignment variations inside extraction headers across corporate accounts records. Risk levels indicate systemic manipulation signature characteristics matching known industry exposure profiles.</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <button onClick={() => setActiveTab('Case Management')} className="rounded-lg bg-gray-100 px-4 py-2 text-xs font-bold uppercase tracking-wider text-gray-600">Return to Case Catalog</button>
            <button className="ml-3 rounded-lg bg-[#005A9C] px-4 py-2 text-xs font-bold uppercase tracking-wider text-white">Re-Run Data Synthesis</button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAuditLogs = () => (
    <div className="space-y-6 rounded-xl bg-white p-6 shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400">System Access Audit Trail Ledger</p>
          <h2 className="mt-2 text-2xl font-extrabold text-gray-900">Advanced Constraints</h2>
          <p className="mt-1 text-sm text-gray-500">Showing rows 1-2 of 451</p>
        </div>
        <button className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold"><Download className="inline h-4 w-4 mr-2" />Export Logs</button>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-gray-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wider text-gray-500">
            <tr>
              <th className="px-4 py-3">Timestamp</th>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {auditRows.map((row) => (
              <tr key={row.time}>
                <td className="px-4 py-3 text-gray-600">{row.time}</td>
                <td className="px-4 py-3 text-gray-700">{row.user}</td>
                <td className="px-4 py-3 text-gray-700">{row.action}</td>
                <td className="px-4 py-3"><span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-700">{row.result}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderUserManagement = () => (
    <div className="space-y-6 rounded-xl bg-white p-6 shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400">Active Administrative System Operators</p>
          <h2 className="mt-2 text-2xl font-extrabold text-gray-900">User Management</h2>
        </div>
        <button className="rounded-xl bg-[#005A9C] px-4 py-2 text-sm font-bold text-white"><UsersIcon className="inline h-4 w-4 mr-2" />Add New User</button>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-gray-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wider text-gray-500">
            <tr>
              <th className="px-4 py-3">Employee ID</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Branch</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {userRows.map((row) => (
              <tr key={row.id}>
                <td className="px-4 py-3 text-gray-700">{row.id}</td>
                <td className="px-4 py-3 text-gray-700">{row.name}</td>
                <td className="px-4 py-3 text-gray-700">{row.role}</td>
                <td className="px-4 py-3 text-gray-700">{row.branch}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderSettings = () => (
    <div className="space-y-6 rounded-xl bg-white p-6 shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100">
      <div>
        <p className="text-xs font-bold uppercase tracking-widest text-gray-400">Application Infrastructure System Settings</p>
        <h2 className="mt-2 text-2xl font-extrabold text-gray-900">Global Preferences & Settings</h2>
        <p className="mt-1 text-sm text-gray-500">Adjust validation scoring thresholds, background processing parameters, and identity security metrics.</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="font-semibold text-gray-900">Relaxed Filter Strict Enforcement Pattern</p>
              <p className="text-sm text-gray-500">Threshold at 85%</p>
            </div>
            <label className="relative inline-flex h-6 w-11 items-center rounded-full bg-[#005A9C]">
              <span className="absolute left-1 h-4 w-4 rounded-full bg-white shadow-sm" />
            </label>
          </div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="font-semibold text-gray-900">Automated Machine Learning Execution Sync</p>
              <p className="text-sm text-gray-500">Background processing on for uploaded artifacts</p>
            </div>
            <label className="relative inline-flex h-6 w-11 items-center rounded-full bg-[#005A9C]">
              <span className="absolute right-1 h-4 w-4 rounded-full bg-white shadow-sm" />
            </label>
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <button className="rounded-xl bg-[#005A9C] px-5 py-2.5 text-sm font-bold text-white"><SettingsIcon className="inline h-4 w-4 mr-2" />Save Preferences Matrix</button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#EBF2F7] font-sans antialiased text-gray-800 flex flex-col">
      <header className="bg-white px-8 py-3 flex items-center justify-between border-b border-gray-100 shrink-0">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-1">
            <div className="flex flex-col items-end leading-none">
              <span className="text-[#005A9C] font-black text-xl tracking-tight">Canara Bank</span>
              <span className="text-[8px] text-gray-400 italic font-semibold tracking-wide">Together We Can</span>
            </div>
            <div className="w-0 h-0 border-l-[9px] border-l-transparent border-b-[18px] border-b-[#FFD200] border-r-[9px] border-r-transparent ml-1" />
          </div>
          <div className="h-6 w-px bg-gray-200" />
          <h1 className="text-2xl font-bold text-[#005A9C] tracking-tight">Fraud Detection Dashboard</h1>
        </div>
        <div className="flex items-center space-x-5">
          <button className="relative p-1 text-gray-400 hover:text-gray-600">
            <Bell className="w-6 h-6 text-[#005A9C]" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
          </button>
          <div className="w-9 h-9 bg-[#005A9C] text-white rounded-full flex items-center justify-center shadow-sm">
            <User className="w-5 h-5" />
          </div>
        </div>
      </header>

      <nav className="bg-white px-8 border-b border-gray-200 shrink-0">
        <div className="flex w-full items-center justify-between gap-2 text-[13px] font-semibold tracking-wide">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 px-1 border-b-4 transition-all ${activeTab === tab ? 'border-[#005A9C] text-[#005A9C]' : 'border-transparent text-gray-500 hover:text-[#005A9C]'}`}
            >
              {tab}
            </button>
          ))}
        </div>
      </nav>

      <main className="p-6 flex-1 max-w-[1700px] w-full mx-auto overflow-y-auto">
        {activeTab === 'Dashboard' && renderDashboard()}
        {activeTab === 'Data Ingestion' && renderDataIngestion()}
        {activeTab === 'Case Management' && renderCaseManagement()}
        {activeTab === 'Investigation' && renderInvestigation()}
        {activeTab === 'Fraud Report' && renderFraudReport()}
        {activeTab === 'Audit Logs' && renderAuditLogs()}
        {activeTab === 'User Management' && renderUserManagement()}
        {activeTab === 'Settings' && renderSettings()}
      </main>
    </div>
  );
}

export default Dashboard;
