import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { UploadCloud, FileText, CheckCircle2, XCircle, Plus } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { api } from '../services/api';
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
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const createMutation = useMutation({
    mutationFn: (data) => api.createCase(data),
    onSuccess: async (newCase) => {
      // Upload all files to this new case
      if (files.length > 0) {
        setIsUploading(true);
        let successCount = 0;
        for (const fileObj of files) {
          try {
            await api.uploadDocument(newCase.id, fileObj.file);
            successCount++;
          } catch (err) {
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
      }
      queryClient.invalidateQueries({ queryKey: ['cases'] });
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
        size: (f.size / 1024 / 1024).toFixed(2) + ' MB'
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
        size: (f.size / 1024 / 1024).toFixed(2) + ' MB'
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

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Data Ingestion</h1>
        <p className="mt-1 text-sm text-slate-500">Create a new case and upload documents for AI analysis.</p>
      </div>

      <div className="bg-white shadow-lg border border-slate-200 rounded-xl overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="p-8 space-y-8">
            
            {/* Case Details Section */}
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs mr-2">1</span>
                Case Details
              </h2>
              <div className="grid grid-cols-2 gap-6 bg-slate-50 p-6 rounded-xl border border-slate-200">
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
              
              <div 
                className={cn(
                  "border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer",
                  isDragging ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-slate-400 bg-slate-50"
                )}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input type="file" multiple ref={fileInputRef} className="hidden" onChange={handleFileSelect} />
                <UploadCloud className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                <h3 className="text-lg font-bold text-slate-700 mb-1">Drag & Drop files here</h3>
                <p className="text-sm text-slate-500">or click to browse from your computer</p>
                <p className="text-xs text-slate-400 mt-4">Supported formats: PDF, JPG, PNG (Max 50MB per file)</p>
              </div>

              {files.length > 0 && (
                <div className="mt-6 space-y-2">
                  <h3 className="text-sm font-bold text-slate-700">Selected Files ({files.length})</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {files.map(f => (
                      <div key={f.id} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-sm">
                        <div className="flex items-center space-x-3 overflow-hidden">
                          <FileText className="w-6 h-6 text-blue-500 flex-shrink-0" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-800 truncate" title={f.name}>{f.name}</p>
                            <p className="text-xs text-slate-500">{f.size}</p>
                          </div>
                        </div>
                        <button type="button" onClick={() => removeFile(f.id)} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                          <XCircle className="w-5 h-5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
