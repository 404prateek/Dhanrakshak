import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { 
  FileText, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, Download, Printer, ShieldAlert,
  CheckCircle2, XCircle, AlertTriangle, UploadCloud, Clock, User
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { api } from '../services/api';
import { cn, formatDate } from '../utils/helpers';

export function Investigation() {
  const { id } = useParams();
  const navigate = useNavigate();
  const caseId = parseInt(id, 10);
  const queryClient = useQueryClient();
  
  const [activeDoc, setActiveDoc] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [newNote, setNewNote] = useState('');
  const fileInputRef = useRef(null);

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

      // Auto-generate report
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

  const getDocumentUrl = (filePath) => {
    if (!filePath) return '';
    if (filePath.startsWith('http')) return filePath;
    const cleanPath = filePath.replace('./storage/', '').replace(/\\/g, '/');
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    return baseUrl.replace('/api/v1', '') + '/storage/' + cleanPath;
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
    createNoteMutation.mutate({ case_id: caseId, user_id: 1, note: newNote });
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

  timelineEvents.sort((a, b) => new Date(b.date) - new Date(a.date)); // Newest first

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      uploadMutation.mutate(e.target.files[0]);
    }
  };

  if (!caseId) {
    return (
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center -m-6 bg-slate-50">
        <div className="text-center max-w-md p-8 bg-white rounded-xl border border-slate-200 shadow-sm">
          <Search className="w-16 h-16 text-slate-300 mx-auto mb-4" />
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
      <div className="bg-white border-b border-slate-200 shadow-sm z-10">
        <div className="px-6 py-3 flex justify-between items-center border-b border-slate-100">
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
        
        {/* SECTION A — CASE SUMMARY CARD */}
        <div className="px-6 py-4 grid grid-cols-6 gap-6 text-sm">
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
        <div className="w-72 bg-white border-r border-slate-200 flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
            <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Documents</h2>
          </div>
          
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

          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
            {documents.length === 0 ? (
              <div className="text-xs text-slate-400 text-center py-4">No documents uploaded yet.</div>
            ) : (
              documents.map(doc => (
                <div 
                  key={doc.id}
                  onClick={() => setActiveDoc(doc)}
                  className={cn(
                    "p-3 rounded-md cursor-pointer border transition-colors flex items-start",
                    activeDoc?.id === doc.id 
                      ? "bg-blue-50 border-blue-200" 
                      : "bg-white border-transparent hover:bg-slate-50"
                  )}
                >
                  <div className="flex items-start">
                    <FileText className={cn("w-8 h-8 mr-3 flex-shrink-0 transition-colors", activeDoc?.id === doc.id ? "text-blue-600" : "text-slate-400 group-hover:text-blue-500")} />
                    <div className="overflow-hidden flex-1">
                      <p className={cn("text-sm font-semibold truncate transition-colors", activeDoc?.id === doc.id ? "text-blue-900" : "text-slate-700 group-hover:text-blue-700")} title={doc.file_name}>
                        {doc.file_name}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 flex justify-between items-center">
                        <span>{doc.file_type}</span>
                        <span className="text-[10px]">{formatDate(doc.upload_date)}</span>
                      </p>
                      <p className="text-[10px] text-slate-400 mt-1 flex items-center"><User className="w-3 h-3 mr-1"/> Uploaded by ID: {doc.user_id || 1}</p>
                    </div>
                  </div>
                  <div className="flex space-x-2 mt-3 pt-2 border-t border-slate-100 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button className="flex-1 flex items-center justify-center text-xs font-medium text-slate-600 hover:text-blue-600 hover:bg-blue-50 py-1.5 rounded" onClick={(e) => { e.stopPropagation(); setActiveDoc(doc); }}>
                      <ZoomIn className="w-3.5 h-3.5 mr-1" /> View
                    </button>
                    <button className="flex-1 flex items-center justify-center text-xs font-medium text-slate-600 hover:text-blue-600 hover:bg-blue-50 py-1.5 rounded" onClick={(e) => e.stopPropagation()}>
                      <Download className="w-3.5 h-3.5 mr-1" /> Download
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Center Column: Document Viewer Placeholder */}
        <div className="flex-1 flex flex-col bg-slate-100 relative">
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-white rounded-lg shadow border border-slate-200 p-1.5 flex items-center space-x-1 z-10">
            <button className="p-1.5 hover:bg-slate-100 rounded text-slate-600"><ZoomOut className="w-4 h-4" /></button>
            <span className="text-xs font-medium px-2 text-slate-700">100%</span>
            <button className="p-1.5 hover:bg-slate-100 rounded text-slate-600"><ZoomIn className="w-4 h-4" /></button>
            <div className="w-px h-4 bg-slate-300 mx-1"></div>
            <button className="p-1.5 hover:bg-slate-100 rounded text-slate-600"><Download className="w-4 h-4" /></button>
          </div>
          
          <div className="flex-1 overflow-auto p-4 md:p-8 flex items-center justify-center">
            {activeDoc ? (
              <div className="bg-white shadow-lg border border-slate-200 w-full h-full flex flex-col relative overflow-hidden rounded-md group">
                {activeDoc.file_type.toLowerCase().includes('pdf') || activeDoc.file_name.toLowerCase().endsWith('.pdf') ? (
                  <iframe src={getDocumentUrl(activeDoc.file_path)} className="w-full h-full border-none" title="PDF Viewer" />
                ) : activeDoc.file_type.toLowerCase().includes('image') || activeDoc.file_name.toLowerCase().match(/\.(jpg|jpeg|png)$/i) ? (
                  <div className="w-full h-full flex items-center justify-center bg-slate-100 overflow-auto">
                    <img src={getDocumentUrl(activeDoc.file_path)} alt={activeDoc.file_name} className="max-w-full max-h-full object-contain" />
                  </div>
                ) : (
                  <div className="text-center text-slate-400 m-auto">
                    <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p>Preview not available for this file type.</p>
                    <a href={getDocumentUrl(activeDoc.file_path)} download className="text-blue-600 hover:underline mt-2 inline-block">Download instead</a>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-slate-400 text-sm">Select a document to view</div>
            )}
          </div>
        </div>

        {/* Right Column: Investigation Notes & Timeline */}
        <div className="w-80 bg-white border-l border-slate-200 flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Investigation Log</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-8 bg-slate-50/50">
            
            {/* SECTION C — INVESTIGATION NOTES */}
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

            {/* SECTION D — INVESTIGATION TIMELINE */}
            <div>
              <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-4 flex items-center">
                <Clock className="w-4 h-4 mr-1 text-slate-400" />
                Timeline
              </h3>
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
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
