import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { UploadCloud, FileText, CheckCircle2, XCircle, Plus } from 'lucide-react';
import { Button } from '../components/ui/Button';
import FileUploader from '../components/ui/FileUploader';
import { api } from '../services/api';
import backgroundUploader from '../services/backgroundUploader';
import { cn } from '../utils/helpers';

export function Ingest() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef(null);
  
  const [form, setForm] = useState({
    case_ref: '',
    applicant_name: '',
    property_address: '',
    status: 'Pending Review',
    risk_score: 0,
  });
  
  const [files, setFiles] = useState([]);
  const [backgroundMode, setBackgroundMode] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [createdCaseId, setCreatedCaseId] = useState(null);
  const uploadControllers = useRef({});

  const createMutation = useMutation({
    mutationFn: (data) => api.createCase(data),
    onSuccess: async (newCase) => {
      setCreatedCaseId(newCase.id);
      // If backgroundMode enabled, start background uploads and navigate immediately
      if (files.length > 0 && backgroundMode) {
        // start background uploads (non-blocking)
        backgroundUploader.startUploads(newCase.id, files);
        toast.success('Case created. Documents uploading in background.');
        queryClient.invalidateQueries({ queryKey: ['cases'] });
        navigate('/cases');
        return;
      }

      // Upload all files to this new case with progress (synchronous)
      if (files.length > 0) {
        setIsUploading(true);
        let successCount = 0;
        for (const fileObj of files) {
          try {
            // create abort controller for this file
            const controller = new AbortController();
            uploadControllers.current[fileObj.id] = controller;
            setFiles(prev => prev.map(f => f.id === fileObj.id ? { ...f, uploading: true, error: false } : f));
            await api.uploadDocument(newCase.id, fileObj.file, (pct) => {
              setFiles(prev => prev.map(f => f.id === fileObj.id ? { ...f, progress: pct } : f));
            }, controller.signal);
            // mark uploaded
            setFiles(prev => prev.map(f => f.id === fileObj.id ? { ...f, uploaded: true, uploading: false, progress: 100 } : f));
            delete uploadControllers.current[fileObj.id];
            successCount++;
          } catch (err) {
            setFiles(prev => prev.map(f => f.id === fileObj.id ? { ...f, error: true, uploading: false } : f));
            delete uploadControllers.current[fileObj.id];
            toast.error(`Failed to upload ${fileObj.file.name}`);
          }
        }
        setIsUploading(false);
        if (successCount === files.length) {
          toast.success('Case created and all documents uploaded!');
        } else if (successCount > 0) {
          toast.warning(`Case created, but only ${successCount}/${files.length} documents uploaded.`);
        }
      } else {
        toast.success('Case created successfully without documents.');
        queryClient.invalidateQueries({ queryKey: ['cases'] });
        navigate('/cases');
        return;
      }
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      navigate(`/fraud-reports/${newCase.id}`);
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
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files).map(f => ({
        id: Math.random().toString(36).substr(2, 9),
        file: f,
        name: f.name,
        size: (f.size / 1024 / 1024).toFixed(2) + ' MB',
        progress: 0,
        uploaded: false,
        error: false,
      }));
      setFiles(prev => [...prev, ...newFiles]);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
        const newFiles = Array.from(e.target.files).map(f => ({
          id: Math.random().toString(36).substr(2, 9),
          file: f,
          name: f.name,
          size: (f.size / 1024 / 1024).toFixed(2) + ' MB',
          progress: 0,
          uploaded: false,
          error: false,
        }));
        setFiles(prev => [...prev, ...newFiles]);
    }
  };

  const removeFile = (id) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.case_ref.trim() || !form.applicant_name.trim() || !form.property_address.trim()) {
      toast.warning('Please fill in all required case details.');
      return;
    }
    createMutation.mutate(form);
  };

  const cancelUpload = (fileId) => {
    const controller = uploadControllers.current[fileId];
    if (controller) {
      try { controller.abort(); } catch (e) { /* ignore */ }
      delete uploadControllers.current[fileId];
      setFiles(prev => prev.map(f => f.id === fileId ? { ...f, uploading: false, error: true } : f));
    } else {
      // not started or queued — just remove
      removeFile(fileId);
    }
  };

  const retryUpload = async (fileId) => {
    const fileObj = files.find(f => f.id === fileId);
    if (!fileObj || !createdCaseId) return;
    setFiles(prev => prev.map(f => f.id === fileId ? { ...f, uploading: true, error: false, progress: 0 } : f));
    const controller = new AbortController();
    uploadControllers.current[fileId] = controller;
    try {
      await api.uploadDocument(createdCaseId, fileObj.file, (pct) => {
        setFiles(prev => prev.map(f => f.id === fileId ? { ...f, progress: pct } : f));
      }, controller.signal);
      setFiles(prev => prev.map(f => f.id === fileId ? { ...f, uploaded: true, uploading: false, progress: 100 } : f));
      delete uploadControllers.current[fileId];
      toast.success(`Uploaded ${fileObj.name}`);
    } catch (err) {
      setFiles(prev => prev.map(f => f.id === fileId ? { ...f, error: true, uploading: false } : f));
      delete uploadControllers.current[fileId];
      toast.error(`Retry failed for ${fileObj.name}`);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Data Ingestion</h1>
        <p className="mt-1 text-sm text-slate-500">Create a new case and upload documents for AI analysis.</p>
      </div>

      <div className="enterprise-card overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="p-8 space-y-8">
            
            {/* Case Details Section */}
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs mr-2">1</span>
                Case Details
              </h2>
              <div className="grid grid-cols-2 gap-6 bg-slate-50 p-6 rounded-[24px] border border-slate-200">
                <div>
                  <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                    Case Reference <span className="text-red-500">*</span>
                  </label>
                  <input
                    name="case_ref"
                    value={form.case_ref}
                    onChange={handleChange}
                    placeholder="e.g. CASE-2024-001"
                    className="enterprise-input w-full bg-white"
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
                    className="enterprise-input w-full bg-white"
                    required
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                    Property Address <span className="text-red-500">*</span>
                  </label>
                  <input
                    name="property_address"
                    value={form.property_address}
                    onChange={handleChange}
                    placeholder="Full property address"
                    className="enterprise-input w-full bg-white"
                    required
                  />
                </div>
              </div>
            </div>

            {/* Document Upload Section */}
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs mr-2">2</span>
                Upload Documents
              </h2>
              
              <FileUploader
                files={files}
                fileInputRef={fileInputRef}
                isDragging={isDragging}
                handleDragOver={handleDragOver}
                handleDragLeave={handleDragLeave}
                handleDrop={handleDrop}
                handleFileSelect={handleFileSelect}
                removeFile={removeFile}
                onCancel={cancelUpload}
                onRetry={retryUpload}
              />
              <div className="mt-3 flex items-center space-x-3">
                <input id="bgUploads" type="checkbox" className="h-4 w-4" checked={backgroundMode} onChange={(e) => setBackgroundMode(e.target.checked)} />
                <label htmlFor="bgUploads" className="text-sm text-slate-600">Enable background uploads (start and navigate immediately)</label>
              </div>
            </div>
            
          </div>
          
          <div className="bg-slate-50 border-t border-slate-200 p-6 flex justify-end space-x-4">
            <Button type="button" variant="secondary" onClick={() => navigate('/cases')}>Cancel</Button>
            <Button 
              type="submit" 
              variant="primary" 
              className="px-8"
              disabled={createMutation.isPending || isUploading}
            >
              {createMutation.isPending || isUploading ? (
                <span className="flex items-center space-x-2">
                  <span className="animate-spin h-4 w-4 border-b-2 border-white rounded-full"></span>
                  <span>Processing...</span>
                </span>
              ) : (
                <span className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Create Case & Ingest</span>
                </span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
