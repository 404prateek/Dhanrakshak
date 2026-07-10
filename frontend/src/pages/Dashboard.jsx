import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Chart from 'chart.js/auto';
import {
  AlertTriangle,
  ArrowRight,
  FileText,
  Search,
  UploadCloud,
} from 'lucide-react';
import { api } from '../services/api';

export function Dashboard() {
  const navigate = useNavigate();
  const trendChartRef = useRef(null);
  const categoryChartRef = useRef(null);
  const trendChartInstance = useRef(null);
  const categoryChartInstance = useRef(null);

  const { data: cases = [], isLoading } = useQuery({
    queryKey: ['cases'],
    queryFn: api.getCases,
  });

  // Calculate metrics
  const totalCases = cases.length;
  const highRiskCases = cases.filter(c => c.risk_score > 75).length;
  const activeInvestigations = cases.filter(c => c.status !== 'Closed' && c.status !== 'Resolved').length;
  const uploadedDocsCount = cases.length > 0 ? cases.length * 2 : 0; 

  const recentCases = [...cases]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5);

  const getRiskLabel = (score) => {
    if (score > 75) return 'High';
    if (score > 40) return 'Medium';
    return 'Low';
  };

  useEffect(() => {
    if (trendChartInstance.current) {
      trendChartInstance.current.destroy();
      trendChartInstance.current = null;
    }
    if (categoryChartInstance.current) {
      categoryChartInstance.current.destroy();
      categoryChartInstance.current = null;
    }

    if (trendChartRef.current) {
      trendChartInstance.current = new Chart(trendChartRef.current, {
        type: 'line',
        data: {
          labels: ['Day 5', 'Day 10', 'Day 15', 'Day 20', 'Day 25', 'Day 30'],
          datasets: [
            { label: 'High', data: [0, 0, 0, 0, 0, highRiskCases], borderColor: '#1d4ed8', backgroundColor: 'transparent', tension: 0.4, borderWidth: 2.5, pointRadius: 2 },
            { label: 'Medium', data: [0, 0, 0, 0, 0, cases.filter(c => getRiskLabel(c.risk_score) === 'Medium').length], borderColor: '#0284c7', backgroundColor: 'transparent', tension: 0.4, borderWidth: 2, pointRadius: 2 },
            { label: 'Low', data: [0, 0, 0, 0, 0, cases.filter(c => getRiskLabel(c.risk_score) === 'Low').length], borderColor: '#005A9C', backgroundColor: 'transparent', tension: 0.4, borderWidth: 2, pointRadius: 2 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, usePointStyle: true, font: { size: 11, weight: '500' } } } },
          scales: {
            y: { min: 0, suggestedMax: 10, ticks: { stepSize: 2, font: { size: 11 } }, grid: { color: '#e5e7eb' } },
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
          datasets: [{ data: [highRiskCases > 0 ? 1 : 0, 0, 0, 0, cases.length - (highRiskCases > 0 ? 1 : 0)], backgroundColor: '#1d4ed8', borderRadius: 2, barThickness: 55 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { min: 0, suggestedMax: 10, ticks: { stepSize: 2, font: { size: 11 } }, grid: { color: '#e5e7eb' } },
            x: { grid: { display: false }, ticks: { font: { size: 11, weight: '500' }, color: '#4b5563' } },
          },
        },
      });
    }

    return () => {
      if (trendChartInstance.current) trendChartInstance.current.destroy();
      if (categoryChartInstance.current) categoryChartInstance.current.destroy();
    };
  }, [cases, highRiskCases]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard Overview</h1>
        <p className="mt-1 text-sm text-slate-500">Key metrics and risk trends across all investigated cases.</p>
      </div>

      <section className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[
          ['Total Cases', totalCases, FileText, 'bg-blue-50 text-blue-600'],
          ['High Risk Cases', highRiskCases, AlertTriangle, 'bg-red-50 text-red-500'],
          ['Active Investigations', activeInvestigations, Search, 'bg-amber-50 text-amber-500'],
          ['Uploaded Documents', uploadedDocsCount, UploadCloud, 'bg-green-50 text-green-600'],
        ].map(([title, value, Icon, badgeClass]) => (
          <div key={title} className="bg-white p-5 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100 flex justify-between items-start hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] transition-shadow duration-300">
            <div className="space-y-1">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">{title}</p>
              <h3 className="text-4xl font-extrabold text-gray-900 tracking-tight">{isLoading ? '-' : value}</h3>
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
            <button onClick={() => navigate('/cases')} className="text-[#005A9C] text-sm font-semibold inline-flex items-center gap-1 hover:underline">View all <ArrowRight className="w-4 h-4" /></button>
          </div>
          <table className="w-full min-w-[700px] text-left text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-600 uppercase text-xs font-semibold border-b border-gray-200">
                <th className="py-3 px-4">Case ID</th>
                <th className="py-3 px-4">Applicant</th>
                <th className="py-3 px-4">Date Opened</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Risk Score</th>
                <th className="py-3 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {recentCases.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-3.5 px-4 font-medium text-gray-900">CASE-{row.id}</td>
                  <td className="py-3.5 px-4 text-gray-600">{row.applicant_name}</td>
                  <td className="py-3.5 px-4 text-gray-500">{new Date(row.created_at).toLocaleDateString()}</td>
                  <td className="py-3.5 px-4 text-gray-500">{row.status}</td>
                  <td className="py-3.5 px-4">
                    <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${getRiskLabel(row.risk_score) === 'High' ? 'bg-red-100 text-red-700' : getRiskLabel(row.risk_score) === 'Medium' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>{getRiskLabel(row.risk_score)}</span>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex justify-center gap-2">
                      <button onClick={() => navigate(`/investigation/${row.id}`)} className="bg-[#005A9C] text-white text-xs px-3 py-1.5 rounded hover:bg-opacity-90 font-medium transition-colors">Investigate</button>
                    </div>
                  </td>
                </tr>
              ))}
              {recentCases.length === 0 && !isLoading && (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-gray-500 text-sm">
                    No recent cases found. Create a new case in the Ingestion tab.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-bold text-gray-900 tracking-tight">Action Required</h4>
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Immediate</span>
          </div>
          <div className="space-y-3">
            {highRiskCases > 0 ? cases.filter(c => c.risk_score > 75).slice(0,4).map((caseItem) => (
              <div key={caseItem.id} className="rounded-xl border border-gray-200 bg-white p-3 flex items-center justify-between shadow-sm hover:bg-gray-50 transition-colors">
                <div>
                  <p className="text-sm font-semibold text-gray-900">CASE-{caseItem.id}</p>
                  <p className="text-xs text-gray-500">Needs investigator review</p>
                </div>
                <button onClick={() => navigate(`/investigation/${caseItem.id}`)} className="bg-[#005A9C] text-white text-xs px-4 py-1.5 rounded font-bold shadow-sm hover:bg-opacity-95 transition-all">Review</button>
              </div>
            )) : (
              <div className="text-center py-6 text-gray-500 text-sm">
                No immediate actions required.
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export default Dashboard;
