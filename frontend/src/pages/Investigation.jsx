import { useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { 
  FileText, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, Download, Printer, ShieldAlert,
  CheckCircle2, XCircle, AlertTriangle, UploadCloud, Clock, User, Brain, GitCompare, Play
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { api, runMLAnalysis as runML, runCrossDocAnalysis } from '../services/api';
import { cn, formatDate } from '../utils/helpers';
import { MLResultCard } from '../components/MLResultCard';
import { CrossDocComparisonCard } from '../components/CrossDocComparisonCard';
export function Investigation() {
  const { id } = useParams();
  const navigate = useNavigate();
  const caseId = parseInt(id, 10);
  const queryClient = useQueryClient();
  
  const [activeDoc, setActiveDoc] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [newNote, setNewNote] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Cross-document pair analysis state
  const [pairPrimary, setPairPrimary] = useState(null);
  const [pairSecondary, setPairSecondary] = useState(null);
  const [pairResult, setPairResult] = useState(null);
  const [isPairAnalyzing, setIsPairAnalyzing] = useState(false);

  // Tabs for the main view
  const [activeTab, setActiveTab] = useState('document'); // 'document', 'analysis', 'cross-doc'

  const fileInputRef = useRef(null);

  // ML analysis — fires when user explicitly clicks "Run AI Analysis"
  const runMLAnalysis = useCallback(async (doc) => {
    if (!doc?.file_path) {
      toast.warning('No file selected for analysis.');
      return;
    }
    setIsAnalyzing(true);
    setAnalysisResult(null);
    setActiveTab('analysis');
    try {
      const data = await runML(caseId, [doc.file_path], {});
      setAnalysisResult(data);
      
      // Auto-save the AI findings to the DB so "View Report" works
      if (data) {
        let findings = data.llm_report;
        if (!findings && data.top_risk_factors?.length > 0) {
           findings = data.top_risk_factors.map(f => f.factor + ': ' + f.detail).join('\n');
        }
        await api.createReport({
          case_id: caseId,
          risk_score: data.final_score_pct ?? data.risk_score ?? 0,
          fraud_category: data.risk_level === 'LOW' ? `Document Verified: ${doc.file_name}` : `Analysis Findings: ${doc.file_name}`,
          findings: findings || 'AI Analysis completed. No major fraud indicators found.',
          recommendation: data.recommendation || 'APPROVE',
          ml_result: JSON.stringify(data)
        });
        queryClient.invalidateQueries(['reports', caseId]);
      }
    } catch (err) {
      toast.error('ML analysis failed', { description: err.message });
    } finally {
      setIsAnalyzing(false);
    }
  }, [caseId, queryClient]);

  // Cross-document pair analysis
  const runPairAnalysis = useCallback(async () => {
    if (!pairPrimary || !pairSecondary) {
      toast.warning('Please select two documents for pair analysis.');
      return;
    }
    if (pairPrimary.id === pairSecondary.id) {
      toast.warning('Please select two different documents.');
      return;
    }
    setIsPairAnalyzing(true);
    setPairResult(null);
    try {
      const data = await runCrossDocAnalysis(caseId, pairPrimary.file_path, pairSecondary.file_path);
      setPairResult(data);
      toast.success('Cross-document analysis complete');
      
      // Auto-save cross-doc findings
      if (data) {
        await api.createReport({
          case_id: caseId,
          risk_score: data.final_score_pct ?? data.risk_score ?? 0,
          fraud_category: `Cross-Document: ${pairPrimary.file_name} vs ${pairSecondary.file_name}`,
          findings: data.llm_report || 'Cross-document analysis completed.',
          recommendation: data.recommendation || 'MANUAL_REVIEW',
          ml_result: JSON.stringify(data)
        });
        queryClient.invalidateQueries(['reports', caseId]);
      }
    } catch (err) {
      toast.error('Pair analysis failed', { description: err.message });
    } finally {
      setIsPairAnalyzing(false);
    }
  }, [caseId, pairPrimary, pairSecondary, queryClient]);

  // Queries
  const { data: cases = [], isLoading: loadingCases } = useQuery({
    queryKey: ['cases'],
    queryFn: api.getCases,
  });
  
  const { data: notes = [], isLoading: loadingNotes } = useQuery({
    queryKey: ['notes', caseId],
    queryFn: () => api.getNotesByCase(caseId),
    enabled: !!caseId,
  });

  const { data: reports = [], isLoading: loadingReports } = useQuery({
    queryKey: ['reports', caseId],
    queryFn: () => api.getReportsByCase(caseId),
    enabled: !!caseId,
  });

  const uploadMutation = useMutation({
    mutationFn: (file) => api.uploadDocument(caseId, file),
    onSuccess: () => {
      toast.success('Document uploaded successfully');
      queryClient.invalidateQueries({ queryKey: ['cases'] });
    },
    onError: (error) => {
      toast.error('Upload failed', {
        description: error.response?.data?.detail || 'An error occurred during upload'
      });
    }
  });

  const createNoteMutation = useMutation({
    mutationFn: (noteData) => api.createNote(noteData),
    onSuccess: () => {
      toast.success('Note added successfully');
      setNewNote('');
      queryClient.invalidateQueries({ queryKey: ['notes', caseId] });
    },
    onError: () => toast.error('Failed to add note')
  });

  const createReportMutation = useMutation({
    mutationFn: (reportData) => api.createReport(reportData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports', caseId] });
      queryClient.invalidateQueries({ queryKey: ['cases'] });
    },
    onError: () => toast.error('Failed to generate automated fraud report')
  });

  const updateStatusMutation = useMutation({
    mutationFn: (status) => api.updateCaseStatus(caseId, status),
    onSuccess: (data, status) => {
      toast.success(status === 'APPROVED' ? 'Case Approved' : 'Fraud Confirmed');
      
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      
      if (reports.length > 0) {
        toast.info("Report already exists for this case");
        return;
      }

      // Auto-generate report on status change
      let fraud_category, findings, recommendation, risk_score;
      if (status === 'APPROVED') {
        fraud_category = "Clear";
        findings = "No indicators of fraud found during investigation. All documents verified and authentic.";
        recommendation = "Proceed with standard processing and account creation.";
        risk_score = 10;
      } else {
        fraud_category = "High Risk Identified";
        findings = "Multiple indicators of fraud detected including potentially forged signatures or documents.";
        recommendation = "Reject application immediately and escalate to internal risk team.";
        risk_score = 95;
      }
      
      createReportMutation.mutate({
        case_id: caseId,
        fraud_category,
        findings,
        recommendation,
        risk_score
      });
    },
    onError: () => toast.error('Failed to update case status')
  });

  const currentCase = cases.find(c => c.id === caseId);
  const documents = currentCase?.documents || [];
  
  // Set default active doc when docs load
  if (documents.length > 0 && !activeDoc) {
    setActiveDoc(documents[0]);
  }

  const handleDocClick = (doc) => {
    setActiveDoc(doc);
    // Clear previous single-doc analysis when switching docs — do NOT auto-run analysis
    setAnalysisResult(null);
  };

  const getDocumentUrl = (filePath) => {
    if (!filePath) return '';
    if (filePath.startsWith('http')) return filePath;
    const cleanPath = filePath.replace('./storage/', '').replace(/\\/g, '/');
    // Use relative path — Vite proxy forwards /storage/* to the backend
    return '/storage/' + cleanPath;
  };

  const StatusIcon = ({ status }) => {
    if (status === 'PASS') return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
    if (status === 'FAIL') return <XCircle className="w-5 h-5 text-red-500" />;
    return <AlertTriangle className="w-5 h-5 text-amber-500" />;
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadMutation.mutate(e.dataTransfer.files[0]);
    }
  };

  const handleSaveNote = () => {
    if (!newNote.trim()) return;
    // user_id is intentionally omitted — the backend uses current_user.id from the JWT token
    createNoteMutation.mutate({ case_id: caseId, note: newNote });
  };

  const handleApprove = () => {
    updateStatusMutation.mutate('APPROVED');
  };

  const handleFlagFraud = () => {
    updateStatusMutation.mutate('FRAUD_CONFIRMED');
  };

  // Sort and aggregate timeline events
  const timelineEvents = [];
  
  if (currentCase) {
    timelineEvents.push({ type: 'CASE_CREATED', title: 'Case Created', date: currentCase.created_at, color: 'bg-slate-300' });
    
    if (currentCase.status === 'APPROVED' || currentCase.status === 'FRAUD_CONFIRMED') {
      timelineEvents.push({ 
        type: 'STATUS_CHANGED', 
        title: currentCase.status === 'APPROVED' ? 'Case Approved' : 'Fraud Confirmed', 
        date: currentCase.updated_at || currentCase.created_at,
        color: currentCase.status === 'APPROVED' ? 'bg-emerald-500' : 'bg-red-500' 
      });
    }
  }

  documents.forEach(doc => {
    timelineEvents.push({ type: 'DOC_UPLOAD', title: `Document Uploaded: ${doc.file_name}`, date: doc.upload_date, color: 'bg-blue-500' });
  });

  notes.forEach(note => {
    timelineEvents.push({ type: 'NOTE_ADDED', title: 'Investigation Note Added', date: note.created_at, color: 'bg-amber-500' });
  });

  reports.forEach(report => {
    timelineEvents.push({ type: 'REPORT_GEN', title: 'Fraud Report Generated', date: report.generated_at || report.created_at || new Date().toISOString(), color: 'bg-purple-500' });
  });

  timelineEvents.sort((a, b) => new Date(b.date) - new Date(a.date));

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      uploadMutation.mutate(e.target.files[0]);
    }
  };

  if (!caseId) {
    return (
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center -m-6 bg-slate-50">
        <div className="text-center max-w-md p-8 bg-white rounded-xl border border-slate-200 shadow-sm">
          <ShieldAlert className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">No Case Selected</h2>
          <p className="text-slate-500 mb-6">Please select a case from the Cases menu to view the investigation workspace.</p>
          <Button variant="primary" onClick={() => navigate('/cases')}>
            Go to Cases
          </Button>
        </div>
      </div>
    );
  }

  if (loadingCases || loadingNotes || loadingReports) {
    return (
      <div className="flex flex-col h-[calc(100vh-6rem)] -m-6 p-6 space-y-6 bg-slate-50 overflow-hidden">
        <div className="h-28 bg-slate-200 animate-pulse rounded-xl w-full border border-slate-200"></div>
        <div className="flex flex-1 space-x-6 overflow-hidden">
          <div className="w-1/4 h-full bg-slate-200 animate-pulse rounded-xl border border-slate-200"></div>
          <div className="w-1/2 h-full bg-slate-200 animate-pulse rounded-xl border border-slate-200"></div>
          <div className="w-1/4 h-full bg-slate-200 animate-pulse rounded-xl border border-slate-200"></div>
        </div>
      </div>
    );
  }

  if (!currentCase) {
    return <div className="p-8 text-center text-slate-500">Case not found.</div>;
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] -m-6 bg-slate-100">
      {/* Top Header Bar */}
      <div className="bg-white border-b border-slate-200 shadow-sm z-10">
        <div className="px-6 py-2 flex justify-between items-center border-b border-slate-100">
          <div className="flex items-center space-x-4">
            <div>
              <h1 className="text-lg font-bold text-slate-900">Investigation Workspace</h1>
              <p className="text-xs text-slate-500">CASE-{currentCase.id} • {currentCase.applicant_name}</p>
            </div>
          </div>
          <div className="flex space-x-2">
            <Button variant="secondary" icon={Printer} onClick={() => navigate(`/fraud-reports/${caseId}`)}>View Report</Button>
            <Button variant="danger" onClick={handleFlagFraud} disabled={updateStatusMutation.isPending}>Flag as Fraud</Button>
            <Button variant="primary" onClick={handleApprove} disabled={updateStatusMutation.isPending}>Approve</Button>
          </div>
        </div>
        
        {/* Case Summary Card */}
        <div className="px-6 py-2 grid grid-cols-6 gap-4 text-xs">
          <div>
            <p className="text-slate-400 font-medium mb-1 text-xs uppercase tracking-wider">Case Reference</p>
            <p className="font-bold text-slate-900">CASE-{currentCase.id}</p>
          </div>
          <div>
            <p className="text-slate-400 font-medium mb-1 text-xs uppercase tracking-wider">Applicant</p>
            <p className="font-medium text-slate-900 flex items-center"><User className="w-3.5 h-3.5 mr-1 text-slate-400"/>{currentCase.applicant_name}</p>
          </div>
          <div className="col-span-2">
            <p className="text-slate-400 font-medium mb-1 text-xs uppercase tracking-wider">Property Address</p>
            <p className="font-medium text-slate-900 truncate" title={currentCase.property_address}>{currentCase.property_address}</p>
          </div>
          <div>
            <p className="text-slate-400 font-medium mb-1 text-xs uppercase tracking-wider">Status & Risk</p>
            <div className="flex items-center space-x-2 mt-0.5">
              <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold uppercase", currentCase.status === 'Open' ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-700")}>{currentCase.status}</span>
              <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold flex items-center", currentCase.risk_score > 75 ? "bg-red-100 text-red-700" : currentCase.risk_score > 40 ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700")}>
                <ShieldAlert className="w-3 h-3 mr-1" />{currentCase.risk_score}
              </span>
            </div>
          </div>
          <div>
            <p className="text-slate-400 font-medium mb-1 text-xs uppercase tracking-wider">Created Date</p>
            <p className="font-medium text-slate-900 flex items-center"><Clock className="w-3.5 h-3.5 mr-1 text-slate-400"/>{formatDate(currentCase.created_at)}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Document List & Upload */}
        {activeTab === 'document' && (
          <div className="w-64 bg-white border-r border-slate-200 flex flex-col flex-shrink-0 transition-all duration-300">
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">

            <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Documents</h2>
            <span className="text-xs text-slate-400 bg-slate-200 px-2 py-0.5 rounded-full font-medium">{documents.length}</span>
          </div>
          
          {/* Upload Zone */}
          <div 
            className={cn(
              "m-3 border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer",
              isDragging ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-slate-400"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileSelect} />
            <UploadCloud className="w-6 h-6 text-slate-400 mx-auto mb-2" />
            <p className="text-xs font-medium text-slate-700">Click or drag document here</p>
            {uploadMutation.isPending && (
              <p className="text-xs text-blue-600 mt-2 flex items-center justify-center">
                <span className="animate-spin h-3 w-3 mr-1 border-b-2 border-blue-600 rounded-full"></span>
                Uploading...
              </p>
            )}
          </div>

          {/* Document List */}
          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
            {documents.length === 0 ? (
              <div className="text-xs text-slate-400 text-center py-4">No documents uploaded yet.</div>
            ) : (
              documents.map(doc => (
                <div 
                  key={doc.id}
                  onClick={() => handleDocClick(doc)}
                  className={cn(
                    "p-3 rounded-md cursor-pointer border transition-colors",
                    activeDoc?.id === doc.id 
                      ? "bg-blue-50 border-blue-200" 
                      : "bg-white border-transparent hover:bg-slate-50 hover:border-slate-200"
                  )}
                >
                  <div className="flex items-start">
                    <FileText className={cn("w-8 h-8 mr-3 flex-shrink-0 transition-colors", activeDoc?.id === doc.id ? "text-blue-600" : "text-slate-400")} />
                    <div className="overflow-hidden flex-1">
                      <p className={cn("text-sm font-semibold truncate transition-colors", activeDoc?.id === doc.id ? "text-blue-900" : "text-slate-700")} title={doc.file_name}>
                        {doc.file_name}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 flex justify-between items-center">
                        <span>{doc.file_type}</span>
                        <span className="text-[10px]">{formatDate(doc.upload_date)}</span>
                      </p>
                      {/* FIX: was doc.user_id, now using doc.uploaded_by (correct field from backend) */}
                      <p className="text-[10px] text-slate-400 mt-1 flex items-center"><User className="w-3 h-3 mr-1"/> Officer ID: {doc.uploaded_by ?? '—'}</p>
                    </div>
                  </div>
                  <div className="flex space-x-2 mt-2 pt-2 border-t border-slate-100">
                    <a 
                      href={getDocumentUrl(doc.file_path)} 
                      download={doc.file_name}
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 flex items-center justify-center text-xs font-medium text-slate-600 hover:text-blue-600 hover:bg-blue-50 py-1.5 rounded"
                    >
                      <Download className="w-3.5 h-3.5 mr-1" /> Download
                    </a>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        )}

        {/* Center Column: Document Viewer + ML Results */}
        <div className="flex-1 flex flex-col bg-slate-100 relative overflow-hidden">
          
          {/* Tab Bar & Toolbar */}
          <div className="sticky top-0 z-10 flex flex-col bg-white border-b border-slate-200">
            <div className="flex justify-between items-center px-4 py-2 bg-slate-50 border-b border-slate-200">
              <div className="flex space-x-1">
                <button
                  onClick={() => setActiveTab('document')}
                  className={cn("px-4 py-1.5 text-sm font-semibold rounded-md transition-colors", activeTab === 'document' ? "bg-white text-blue-700 shadow-sm border border-slate-200" : "text-slate-600 hover:bg-slate-200")}
                >
                  Document Viewer
                </button>
                <button
                  onClick={() => setActiveTab('analysis')}
                  className={cn("px-4 py-1.5 text-sm font-semibold rounded-md transition-colors flex items-center space-x-2", activeTab === 'analysis' ? "bg-white text-blue-700 shadow-sm border border-slate-200" : "text-slate-600 hover:bg-slate-200")}
                >
                  <span>AI Analysis</span>
                  {analysisResult && <span className="w-2 h-2 rounded-full bg-blue-500"></span>}
                </button>
                <button
                  onClick={() => setActiveTab('cross-doc')}
                  className={cn("px-4 py-1.5 text-sm font-semibold rounded-md transition-colors", activeTab === 'cross-doc' ? "bg-white text-blue-700 shadow-sm border border-slate-200" : "text-slate-600 hover:bg-slate-200")}
                >
                  Cross-Document Analysis
                </button>
              </div>

              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg">
                  <button className="p-1 hover:bg-white rounded text-slate-600"><ZoomOut className="w-4 h-4" /></button>
                  <span className="text-xs font-medium px-2 text-slate-700">100%</span>
                  <button className="p-1 hover:bg-white rounded text-slate-600"><ZoomIn className="w-4 h-4" /></button>
                </div>
                {/* Explicit "Run AI Analysis" button */}
                <button
                  onClick={() => runMLAnalysis(activeDoc)}
                  disabled={isAnalyzing || !activeDoc}
                  className={cn(
                    "flex items-center space-x-2 text-sm font-semibold px-4 py-1.5 rounded-lg transition-all",
                    isAnalyzing 
                      ? "bg-slate-200 text-slate-500 cursor-not-allowed"
                      : activeDoc 
                        ? "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                        : "bg-slate-100 text-slate-400 cursor-not-allowed"
                  )}
                >
                  {isAnalyzing ? (
                    <><span className="animate-spin h-4 w-4 border-b-2 border-slate-500 rounded-full inline-block"></span><span>Analyzing...</span></>
                  ) : (
                    <><Brain className="w-4 h-4" /><span>Run AI Analysis</span></>
                  )}
                </button>
                {activeDoc && (
                  <a href={getDocumentUrl(activeDoc.file_path)} download={activeDoc.file_name} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-600 bg-white border border-slate-200 shadow-sm">
                    <Download className="w-4 h-4" />
                  </a>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-slate-100">
            {/* Tab 1: Document Viewer */}
            {activeTab === 'document' && (
              <div className="h-full flex flex-col">
                {activeDoc ? (
                  <div className="bg-white shadow-sm border border-slate-200 w-full flex-1 flex flex-col relative overflow-hidden rounded-md h-full">
                    {activeDoc.file_type.toLowerCase().includes('pdf') || activeDoc.file_name.toLowerCase().endsWith('.pdf') ? (
                      <iframe src={getDocumentUrl(activeDoc.file_path)} className="w-full h-full border-none min-h-full" title="PDF Viewer" />
                    ) : activeDoc.file_type.toLowerCase().includes('image') || activeDoc.file_name.toLowerCase().match(/\.(jpg|jpeg|png|gif|webp)$/i) ? (
                      <div className="w-full h-full flex items-center justify-center bg-slate-100 overflow-auto min-h-full">
                        <img src={getDocumentUrl(activeDoc.file_path)} alt={activeDoc.file_name} className="max-w-full max-h-full object-contain" />
                      </div>
                    ) : (
                      <div className="text-center text-slate-400 m-auto py-16">
                        <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                        <p>Preview not available for this file type.</p>
                        <a href={getDocumentUrl(activeDoc.file_path)} download className="text-blue-600 hover:underline mt-2 inline-block">Download instead</a>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-400 text-sm bg-white border border-dashed border-slate-300 rounded-xl">Select a document to view</div>
                )}
              </div>
            )}

            {/* Tab 2: AI Analysis Report — full width, scrollable */}
            {activeTab === 'analysis' && (
              <div className="w-full">
                {isAnalyzing && (
                  <div className="bg-white border border-gray-200 rounded-xl p-12 flex flex-col items-center justify-center space-y-4 shadow-sm">
                    <Brain className="w-10 h-10 animate-pulse text-blue-600" />
                    <span className="text-lg font-semibold text-gray-800">Running deep AI fraud analysis...</span>
                    <p className="text-sm text-gray-500">Forensic · OCR · Behavioral · Trust Engine · AI Report</p>
                    <span className="flex space-x-2">
                      <span className="w-3 h-3 bg-blue-500 rounded-full animate-bounce" style={{animationDelay:'0ms'}}></span>
                      <span className="w-3 h-3 bg-blue-500 rounded-full animate-bounce" style={{animationDelay:'150ms'}}></span>
                      <span className="w-3 h-3 bg-blue-500 rounded-full animate-bounce" style={{animationDelay:'300ms'}}></span>
                    </span>
                  </div>
                )}
                {!isAnalyzing && analysisResult && (
                  <MLResultCard result={analysisResult} />
                )}
                {!isAnalyzing && !analysisResult && activeDoc && (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-500 text-center bg-white rounded-xl border border-dashed border-slate-300 shadow-sm">
                    <div className="text-4xl mb-3">🔍</div>
                    <p className="text-lg font-medium text-slate-700">No analysis yet</p>
                    <p className="text-sm mt-1 mb-4">Click <span className="text-blue-600 font-bold">Run AI Analysis</span> to analyze the selected document</p>
                    <Button variant="primary" onClick={() => runMLAnalysis(activeDoc)}>
                      Run AI Analysis Now
                    </Button>
                  </div>
                )}
                {!isAnalyzing && !activeDoc && (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-500 text-center bg-white rounded-xl border border-dashed border-slate-300 shadow-sm">
                    <div className="text-4xl mb-3">📄</div>
                    <p className="text-lg font-medium text-slate-700">No document selected</p>
                    <p className="text-sm mt-1">Select a document from the left panel first</p>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Cross-Document Analysis */}
            {activeTab === 'cross-doc' && (
              <div className="max-w-4xl mx-auto w-full">
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-8">
                  <h2 className="text-lg font-bold text-gray-900 mb-6 flex items-center">
                    <GitCompare className="w-5 h-5 mr-3 text-blue-600" />
                    Cross-Document Pair Analysis
                  </h2>
                  <div className="flex items-center space-x-6">
                    <div className="flex-1">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Primary Document</p>
                      <select
                        className="w-full bg-white border border-gray-300 text-gray-800 text-sm rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none focus:border-blue-500"
                        value={pairPrimary?.id ?? ''}
                        onChange={e => setPairPrimary(documents.find(d => d.id === parseInt(e.target.value)) || null)}
                      >
                        <option value="">— Select document —</option>
                        {documents.map(d => (
                          <option key={d.id} value={d.id}>{d.file_name}</option>
                        ))}
                      </select>
                    </div>
                    <GitCompare className="w-8 h-8 text-blue-400 flex-shrink-0 mt-6" />
                    <div className="flex-1">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Secondary Document</p>
                      <select
                        className="w-full bg-white border border-gray-300 text-gray-800 text-sm rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none focus:border-blue-500"
                        value={pairSecondary?.id ?? ''}
                        onChange={e => setPairSecondary(documents.find(d => d.id === parseInt(e.target.value)) || null)}
                      >
                        <option value="">— Select document —</option>
                        {documents.map(d => (
                          <option key={d.id} value={d.id}>{d.file_name}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  
                  <div className="mt-8 flex justify-center border-t border-gray-100 pt-8">
                    <button
                      onClick={runPairAnalysis}
                      disabled={isPairAnalyzing || !pairPrimary || !pairSecondary}
                      className="flex items-center space-x-2 bg-blue-700 hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold px-8 py-3 rounded-lg transition-colors shadow-sm"
                    >
                      {isPairAnalyzing ? (
                        <><span className="animate-spin h-5 w-5 border-b-2 border-white rounded-full inline-block"></span><span>Analyzing Pair...</span></>
                      ) : (
                        <><Play className="w-5 h-5" /><span>Run Pair Analysis</span></>
                      )}
                    </button>
                  </div>
                </div>

                {pairResult && (
                  <div className="mt-8">
                    <CrossDocComparisonCard result={pairResult} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Investigation Notes & Timeline */}
        {activeTab === 'document' && (
        <div className="w-64 bg-white border-l border-slate-200 flex flex-col flex-shrink-0 transition-all duration-300">
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Investigation Log</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-8 bg-slate-50/50">
            
            {/* Investigation Notes */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest flex items-center">
                  <FileText className="w-4 h-4 mr-1 text-slate-400" />
                  Notes
                </h3>
                <span className="bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full text-[10px] font-bold">{notes.length}</span>
              </div>
              
              <div className="mb-4 bg-white p-3 rounded-lg border border-slate-200 shadow-sm focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 transition-all">
                <textarea 
                  className="w-full text-sm text-slate-700 bg-transparent border-none focus:ring-0 resize-none p-0 placeholder-slate-400 h-16"
                  placeholder="Type a new investigation note..."
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                />
                <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-100">
                  <span className="text-[10px] text-slate-400 font-medium">Shift + Enter for new line</span>
                  <Button variant="primary" size="sm" onClick={handleSaveNote} disabled={createNoteMutation.isPending || !newNote.trim()}>
                    {createNoteMutation.isPending ? 'Saving...' : 'Save Note'}
                  </Button>
                </div>
              </div>
              
              <div className="space-y-3">
                {notes.length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-2">No notes yet.</p>
                )}
                {notes.map(note => (
                  <div key={note.id} className="p-3 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-slate-300 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center">
                        <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-[10px] font-bold mr-2 uppercase">
                          {note.user_id ? `U${note.user_id}` : 'DR'}
                        </div>
                        <span className="text-xs font-bold text-slate-700">Officer {note.user_id || 'System'}</span>
                      </div>
                      <span className="text-[10px] font-medium text-slate-400">{formatDate(note.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-600 leading-relaxed pl-7">{note.note}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Investigation Timeline */}
            <div>
              <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-4 flex items-center">
                <Clock className="w-4 h-4 mr-1 text-slate-400" />
                Timeline
              </h3>
              {timelineEvents.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-2">No events yet.</p>
              ) : (
                <div className="relative border-l-2 border-slate-200 ml-3 space-y-6 pb-2">
                  {timelineEvents.map((evt, idx) => (
                    <div key={idx} className="relative pl-6">
                      <div className={cn("absolute -left-[9px] top-1 w-4 h-4 rounded-full border-4 border-white shadow-sm", evt.color)}></div>
                      <p className={cn("text-sm font-bold", 
                        evt.type === 'STATUS_CHANGED' && evt.title === 'Fraud Confirmed' ? 'text-red-700' : 
                        evt.type === 'STATUS_CHANGED' && evt.title === 'Case Approved' ? 'text-emerald-700' : 
                        'text-slate-800'
                      )}>{evt.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{formatDate(evt.date)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        </div>
        )}
      </div>
    </div>
  );
}
