import React from 'react';
import { UploadCloud, FileText, XCircle, Plus, RotateCw, CheckCircle2 } from 'lucide-react';
import { cn } from '../../utils/helpers';

export function FileUploader({
  files,
  fileInputRef,
  isDragging,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleFileSelect,
  removeFile,
  onRetry,
  onCancel,
}) {
  const handleRemoveConfirm = (f) => {
    const ok = window.confirm(`Remove file "${f.name}"?`);
    if (ok) removeFile(f.id);
  };

  const handleCancelConfirm = (f) => {
    const ok = window.confirm(`Cancel upload for "${f.name}"?`);
    if (ok) onCancel?.(f.id);
  };
  return (
    <div>
      <div
        className={cn(
          "border-2 border-dashed rounded-[20px] p-10 text-center transition duration-200 ease-in-out cursor-pointer bg-white shadow-sm hover:shadow-lg",
          isDragging ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-slate-400"
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
              <div key={f.id} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-[24px] shadow-sm transition duration-200 ease-in-out hover:shadow-lg">
                <div className="flex items-center space-x-3 overflow-hidden">
                  <FileText className="w-6 h-6 text-blue-500 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate" title={f.name}>{f.name}</p>
                    <p className="text-xs text-slate-500">{f.size}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-28">
                    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-2 bg-blue-500 transition-all" style={{ width: `${f.progress ?? 0}%` }} />
                    </div>
                    <div className="text-xs text-slate-400 mt-1">{f.uploaded ? 'Uploaded' : f.error ? 'Failed' : `${f.progress ?? 0}%`}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${f.uploaded ? 'bg-green-100 text-green-700' : f.error ? 'bg-red-100 text-red-700' : 'bg-amber-50 text-amber-700'}`}>{f.uploaded ? 'Uploaded' : f.error ? 'Error' : f.uploading ? 'Uploading' : 'Queued'}</span>
                    {f.uploaded ? (
                      <span className="text-green-600" title="Uploaded"><CheckCircle2 className="w-5 h-5" /></span>
                    ) : f.uploading ? (
                      <button type="button" onClick={() => handleCancelConfirm(f)} title={`Cancel upload ${f.name}`} aria-label={`Cancel upload ${f.name}`} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                        <XCircle className="w-5 h-5" />
                      </button>
                    ) : f.error ? (
                      <>
                        <button type="button" onClick={() => onRetry?.(f.id)} title={`Retry upload ${f.name}`} aria-label={`Retry upload ${f.name}`} className="p-1 text-slate-500 hover:text-slate-700 transition-colors">
                          <RotateCw className="w-5 h-5" />
                        </button>
                        <button type="button" onClick={() => handleRemoveConfirm(f)} title={`Remove ${f.name}`} aria-label={`Remove ${f.name}`} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                          <XCircle className="w-5 h-5" />
                        </button>
                      </>
                    ) : (
                      <button type="button" onClick={() => handleRemoveConfirm(f)} title={`Remove ${f.name}`} aria-label={`Remove ${f.name}`} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                        <XCircle className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div className="flex items-center justify-center p-3 border border-dashed border-slate-200 rounded-[24px] bg-gray-50 hover:bg-gray-100 cursor-pointer" onClick={() => fileInputRef.current?.click()}>
              <Plus className="w-5 h-5 text-slate-600 mr-2" />
              <span className="text-sm text-slate-600">Add more files</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default FileUploader;
