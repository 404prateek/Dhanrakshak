import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileText, Printer, Download, ShieldAlert, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { api } from '../services/api';
import { formatDate } from '../utils/helpers';

export function FraudReport() {
  const { id } = useParams();
  const caseId = parseInt(id, 10);

  const { data: cases = [], isLoading: loadingCases } = useQuery({
    queryKey: ['cases'],
    queryFn: api.getCases,
  });

  const { data: reportsData = [], isLoading: loadingReports, isError: reportsError } = useQuery({
    queryKey: ['reports', caseId],
    queryFn: () => api.getReportsByCase(caseId),
    enabled: !!caseId,
  });

  const reports = Array.isArray(reportsData) ? reportsData : [];

  console.log("Reports API Response:", reports);

  if (!caseId) {
    return (
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center -m-6 bg-slate-50">
        <div className="text-center max-w-md p-8 bg-white rounded-xl border border-slate-200 shadow-sm">
          <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">No Case Selected</h2>
          <p className="text-slate-500 mb-6">Please select a case from the Cases menu to view its fraud report.</p>
          <Button variant="primary" onClick={() => navigate('/cases')}>
            Go to Cases
          </Button>
        </div>
      </div>
    );
  }

  if (loadingCases || loadingReports) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (reportsError) {
    return (
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center -m-6 bg-slate-50">
        <div className="text-center max-w-md p-8 bg-white rounded-xl border border-red-200 shadow-sm">
          <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">Failed to Load Reports</h2>
          <p className="text-slate-500 mb-6">There was an error communicating with the server. Please try again later.</p>
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const currentCase = cases.find(c => c.id === caseId);

  if (!currentCase) {
    return <div className="p-8 text-center text-slate-500">Case not found.</div>;
  }

  const latestReport = reports.length > 0 ? reports[reports.length - 1] : null;

  if (!latestReport) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="p-8 text-center text-slate-500 bg-white shadow-sm rounded-lg border border-slate-200">
          <ShieldAlert className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h2 className="text-lg font-medium text-slate-900 mb-2">No Report Found</h2>
          <p>No fraud report available for this case.</p>
        </div>
      </div>
    );
  }

  // Fix 2: Deduplicate reports to prevent duplicate findings
  const uniqueReportsMap = new Map();
  reports.forEach(report => {
    uniqueReportsMap.set(report.fraud_category + '-' + report.findings, report);
  });
  const uniqueReports = Array.from(uniqueReportsMap.values());

  // Fix 4 & 5: Print and Download Handlers
  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPDF = () => {
    const element = document.getElementById('report-content');
    if (window.html2pdf) {
      window.html2pdf().from(element).save(`Fraud_Report_CASE-${currentCase.id}.pdf`);
    } else {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js';
      script.onload = () => {
        window.html2pdf().from(element).save(`Fraud_Report_CASE-${currentCase.id}.pdf`);
      };
      document.body.appendChild(script);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-end print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Fraud Investigation Report</h1>
          <p className="mt-1 text-sm text-slate-500">Official generated report for CASE-{currentCase.id}</p>
        </div>
        <div className="flex space-x-2">
          <Button variant="secondary" icon={Download} onClick={handleDownloadPDF}>Download PDF</Button>
          <Button variant="primary" icon={Printer} onClick={handlePrint}>Print Report</Button>
        </div>
      </div>

      <div id="report-content" className="enterprise-card bg-white shadow-lg p-10 print:shadow-none print:border-none print:p-0">
        {/* SECTION A — REPORT HEADER */}
        <div className="border-b-2 border-slate-900 pb-6 mb-8 flex justify-between items-start">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded bg-blue-600 flex items-center justify-center print:bg-slate-900">
              <ShieldAlert className="w-8 h-8 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">DhanRakshak</h2>
              <p className="text-sm font-medium text-slate-500 uppercase tracking-widest">Fraud Intelligence Unit</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-bold text-slate-900">Report ID: FR-{currentCase.id}-{new Date().getFullYear()}</p>
            <p className="text-sm text-slate-500">Generated: {formatDate(latestReport?.generated_at || latestReport?.created_at || new Date().toISOString())}</p>
            <p className="text-sm text-slate-500">Classification: <span className="font-bold text-red-600">CONFIDENTIAL</span></p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6 mb-8">
          {/* SECTION B — RISK SCORE CARD */}
          <div className={`p-6 rounded-xl border-2 text-center flex flex-col justify-center h-full ${
            currentCase.risk_score > 75 ? "bg-red-50 border-red-200" : 
            currentCase.risk_score > 40 ? "bg-amber-50 border-amber-200" : 
            "bg-emerald-50 border-emerald-200"
          }`}>
            <p className="text-sm font-bold uppercase tracking-wider mb-2 text-slate-500">Overall Risk Score</p>
            <p className={`text-7xl font-black mb-2 tracking-tighter ${
              currentCase.risk_score > 75 ? "text-red-600" : 
              currentCase.risk_score > 40 ? "text-amber-600" : 
              "text-emerald-600"
            }`}>
              {currentCase.risk_score}
            </p>
            <p className={`text-lg font-black uppercase tracking-wide ${
              currentCase.risk_score > 75 ? "text-red-700" : 
              currentCase.risk_score > 40 ? "text-amber-700" : 
              "text-emerald-700"
            }`}>
              {currentCase.risk_score > 75 ? "High Risk" : currentCase.risk_score > 40 ? "Medium Risk" : "Low Risk"}
            </p>
          </div>

          <div className="col-span-2 flex flex-col space-y-6">
            <section className="bg-slate-50 rounded-xl p-5 border border-slate-200">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Case Details</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="font-medium text-slate-500 block mb-0.5">Applicant Name</span> <span className="font-bold text-slate-900">{currentCase.applicant_name}</span></div>
                <div><span className="font-medium text-slate-500 block mb-0.5">Case Reference</span> <span className="font-bold text-slate-900">CASE-{currentCase.id}</span></div>
                <div className="col-span-2"><span className="font-medium text-slate-500 block mb-0.5">Property Address</span> <span className="font-bold text-slate-900">{currentCase.property_address}</span></div>
              </div>
            </section>
            
            <section className="bg-slate-50 rounded-xl p-5 border border-slate-200 flex-1">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Executive Summary</h3>
              <p className="text-sm text-slate-700 leading-relaxed font-medium">
                {latestReport ? latestReport.findings : "Pending final review."}
              </p>
            </section>
          </div>
        </div>

        {/* SECTION C — FRAUD FINDINGS */}
        <section className="mb-8">
          <h3 className="text-lg font-bold text-slate-900 mb-4 uppercase border-b-2 border-slate-200 pb-2 flex items-center">
            <FileText className="w-5 h-5 mr-2 text-slate-400" />
            Detailed Investigation Findings
          </h3>
          {uniqueReports.length > 0 ? (
            <div className="space-y-4">
              {uniqueReports.map((report, idx) => (
                <div key={idx} className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                  <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center">
                    <h4 className="font-bold text-slate-800">{report.fraud_category}</h4>
                    <span className="text-xs font-bold bg-amber-100 text-amber-800 px-2 py-1 rounded border border-amber-200">
                      Score Impact: {report.risk_score}
                    </span>
                  </div>
                  <div className="p-4">
                    <div className="mb-4">
                      <p className="text-xs font-bold text-slate-500 uppercase mb-1">Observation</p>
                      <p className="text-sm text-slate-700">{report.findings}</p>
                    </div>
                    {report.recommendation && (
                      <div className="bg-slate-50 p-3 rounded border border-slate-200">
                        <p className="text-xs font-bold text-slate-500 uppercase mb-1">Recommendation</p>
                        <p className="text-sm font-medium text-slate-800">{report.recommendation}</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-slate-500 p-8 text-center border border-dashed border-slate-300 rounded-lg">
              AI Verification results will populate here once documents are fully processed.
            </div>
          )}
        </section>

        {/* Signatures */}
        <div className="mt-16 pt-8 grid grid-cols-2 gap-8 text-sm">
          <div>
            <div className="border-b border-slate-400 h-10 mb-2 w-48"></div>
            <p className="font-bold text-slate-900">System Generated</p>
            <p className="text-slate-500">DhanRakshak AI</p>
          </div>
          <div>
            <div className="border-b border-slate-400 h-10 mb-2 w-48"></div>
            <p className="font-bold text-slate-900">Assigned Officer</p>
            <p className="text-slate-500">ID: {currentCase.assigned_officer_id || 'Unassigned'}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
