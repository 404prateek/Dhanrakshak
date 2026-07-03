import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileText, Printer, Download, ShieldAlert, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { api } from '../services/api';
import { formatDate } from '../utils/helpers';

/* eslint-disable react/no-unknown-property */
const PRINT_STYLES = `
  @media print {
    .no-print { display: none !important; }
    body { background: white !important; }
    .print-container { box-shadow: none !important; border: none !important; }
    #report-content { padding: 0 !important; }
  }
`;

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
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center -m-6 bg-slate-100">
        <div className="text-center max-w-md p-8 enterprise-card">
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
        <div className="text-center max-w-md p-8 enterprise-card border-red-200">
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
        <div className="p-8 text-center text-slate-500 enterprise-panel">
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

  // FIX 4: Read the right score field — backend sends final_score_pct (0-100)
  // currentCase.risk_score is always 0 in DB until manually updated
  // The latest ML report has the real score in ml_result metadata
  const mlResult = latestReport?.ml_result || {};
  const displayScore = Math.round(
    mlResult.final_score_pct
    ?? mlResult.risk_score
    ?? ((mlResult.final_score ?? 0) * 100)
    ?? currentCase.risk_score
    ?? 0
  );
  const riskLevel = mlResult.risk_level || (displayScore > 65 ? 'HIGH' : displayScore > 35 ? 'MEDIUM' : 'LOW');

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
    <div className="max-w-6xl mx-auto space-y-6 px-4 sm:px-6 lg:px-8">
      {/* Inject print styles */}
      <style dangerouslySetInnerHTML={{ __html: PRINT_STYLES }} />

      <div className="enterprise-panel p-6 no-print">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Fraud Investigation Report</h1>
            <p className="mt-2 text-sm text-slate-500">Official generated report for CASE-{currentCase.id}</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" icon={Download} onClick={handleDownloadPDF}>Download PDF</Button>
            <Button variant="primary" icon={Printer} onClick={handlePrint}>Print Report</Button>
          </div>
        </div>
      </div>

      <div id="report-content" className="print-container enterprise-card overflow-hidden print:shadow-none print:border-none">
        {/* SECTION A — REPORT HEADER */}
        <div className="bg-white border-b border-gray-200 px-8 py-6 rounded-t-[24px]">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-700 rounded-[18px] flex items-center justify-center text-white font-bold text-xl flex-shrink-0">
                DR
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">DhanRakshak</h2>
                <p className="text-xs text-gray-500 uppercase tracking-widest font-medium">
                  Fraud Intelligence Unit · Canara Bank
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold text-gray-700">Report ID: FR-{currentCase.id}-{new Date().getFullYear()}</p>
              <p className="text-xs text-gray-500">Generated: {formatDate(latestReport?.generated_at || latestReport?.created_at || new Date().toISOString())}</p>
              <span className="text-xs font-bold text-red-600 border border-red-200 bg-red-50 px-2 py-0.5 rounded mt-1 inline-block">
                CONFIDENTIAL
              </span>
            </div>
          </div>
        </div>

        <div className="px-8 py-6 grid grid-cols-3 gap-6">
          {/* SECTION B — RISK SCORE CARD */}
          <div className={`p-6 rounded-[24px] border-2 text-center flex flex-col justify-center h-full ${
            displayScore > 65 ? "bg-red-50 border-red-200" : 
            displayScore > 35 ? "bg-amber-50 border-amber-200" : 
            "bg-emerald-50 border-emerald-200"
          }`}>
            <p className="text-sm font-bold uppercase tracking-wider mb-2 text-slate-500">Overall Risk Score</p>
            <p className={`text-7xl font-black mb-2 tracking-tighter ${
              displayScore > 65 ? "text-red-600" : 
              displayScore > 35 ? "text-amber-600" : 
              "text-emerald-600"
            }`}>
              {displayScore}
            </p>
            <p className={`text-lg font-black uppercase tracking-wide ${
              displayScore > 65 ? "text-red-700" : 
              displayScore > 35 ? "text-amber-700" : 
              "text-emerald-700"
            }`}>
              {riskLevel === 'HIGH' ? 'High Risk' : riskLevel === 'MEDIUM' ? 'Medium Risk' : 'Low Risk'}
            </p>
          </div>

          <div className="col-span-2 flex flex-col space-y-4">
            <section className="bg-gray-50 rounded-[24px] p-5 border border-gray-200">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">Case Details</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="font-medium text-gray-500 block mb-0.5">Applicant Name</span> <span className="font-bold text-gray-900">{currentCase.applicant_name}</span></div>
                <div><span className="font-medium text-gray-500 block mb-0.5">Case Reference</span> <span className="font-bold text-gray-900">CASE-{currentCase.id}</span></div>
                <div className="col-span-2"><span className="font-medium text-gray-500 block mb-0.5">Property Address</span> <span className="font-bold text-gray-900">{currentCase.property_address}</span></div>
              </div>
            </section>
            
            <section className="bg-gray-50 rounded-[24px] p-5 border border-gray-200 flex-1">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">Executive Summary</h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {latestReport ? latestReport.findings : "Pending final review."}
              </p>
            </section>
          </div>
        </div>

        <div className="px-8 py-6 border-t border-gray-100">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4 flex items-center">
            <FileText className="w-4 h-4 mr-2 text-gray-400" />
            Detailed Investigation Findings
          </h3>
          {uniqueReports.length > 0 ? (
            <div className="space-y-4">
              {uniqueReports.map((report, idx) => {
                // Parse ml_result if it's stored as a JSON string
                const ml = (typeof report.ml_result === 'string'
                  ? (() => { try { return JSON.parse(report.ml_result); } catch { return {}; } })()
                  : report.ml_result) || {};

                const docType   = ml.doc_type || report.fraud_category || 'Document';
                const docScore  = ml.final_score_pct ?? ml.risk_score ?? report.risk_score ?? 0;
                const integrity = ml.trufor_score ?? null;
                const conflicts = ml.conflicts || [];
                // One-line forensic summary — never repeat the full LLM text
                const forensicLine = integrity !== null
                  ? `Integrity: ${Math.round(integrity * 100)}% authentic — ${integrity > 0.8 ? 'appears genuine' : integrity > 0.5 ? 'minor anomalies' : 'tampering concerns'}.`
                  : 'Forensic scan unavailable for this format.';

                // Key finding = first sentence of findings text only
                const firstSentence = (report.findings || '').split(/[.!?]/)[0].trim();

                return (
                  <div key={idx} className="enterprise-panel overflow-hidden">
                    <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center rounded-t-[24px]">
                      <div>
                        <h4 className="font-bold text-slate-800">{docType}</h4>
                        <p className="text-xs text-slate-500 mt-0.5">{report.fraud_category}</p>
                      </div>
                      <span className={`text-xs font-bold px-2 py-1 rounded border ${
                        docScore > 65 ? 'bg-red-100 text-red-800 border-red-200'
                        : docScore > 35 ? 'bg-amber-100 text-amber-800 border-amber-200'
                        : 'bg-emerald-100 text-emerald-800 border-emerald-200'
                      }`}>
                        Risk Score: {Math.round(docScore)}
                      </span>
                    </div>
                    <div className="p-4 space-y-2">
                      <p className="text-xs font-bold text-slate-500 uppercase">Forensic Assessment</p>
                      <p className="text-sm text-slate-700">{forensicLine}</p>
                      <p className="text-xs text-slate-500">
                        {conflicts.length > 0
                          ? `⚠ ${conflicts.length} conflict(s) detected.`
                          : '✓ No conflicts found.'}
                      </p>
                      {firstSentence && (
                        <div className="mt-2 bg-slate-50 p-3 rounded-[20px] border border-slate-200">
                          <p className="text-xs font-bold text-slate-500 uppercase mb-1">Key Finding</p>
                          <p className="text-sm font-medium text-slate-800">{firstSentence}.</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-gray-500 p-8 text-center border border-dashed border-gray-300 rounded-[20px]">
              AI Verification results will populate here once documents are fully processed.
            </div>
          )}
        </div>

        {/* Signatures */}
        <div className="px-8 py-6 border-t border-gray-100 grid grid-cols-2 gap-8 text-sm bg-gray-50">
          <div>
            <div className="border-b border-gray-400 h-10 mb-2 w-48"></div>
            <p className="font-bold text-gray-900">System Generated</p>
            <p className="text-gray-500">DhanRakshak AI · {new Date().toLocaleDateString('en-IN')}</p>
          </div>
          <div>
            <div className="border-b border-gray-400 h-10 mb-2 w-48"></div>
            <p className="font-bold text-gray-900">Assigned Officer</p>
            <p className="text-gray-500">ID: {currentCase.assigned_officer_id || 'Unassigned'}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
