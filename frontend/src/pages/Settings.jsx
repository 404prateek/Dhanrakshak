import { Save } from 'lucide-react';
import { Button } from '../components/ui/Button';

export function Settings() {
  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">System Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Manage application preferences and configurations.</p>
      </div>

      <div className="enterprise-card bg-white p-6">
        <h3 className="text-lg font-medium text-slate-900 border-b border-slate-200 pb-4 mb-4">Risk Assessment Rules</h3>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">Strict Metadata Matching</p>
              <p className="text-sm text-slate-500">Flag documents if PDF creation date is more than 30 days apart from content date.</p>
            </div>
            <div className="flex items-center">
              <input type="checkbox" defaultChecked className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded" />
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">Auto-flag Duplicate Names</p>
              <p className="text-sm text-slate-500">Automatically flag applications sharing the same applicant name across branches.</p>
            </div>
            <div className="flex items-center">
              <input type="checkbox" defaultChecked className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded" />
            </div>
          </div>
        </div>

        <div className="mt-8 pt-4 border-t border-slate-200 flex justify-end">
          <Button icon={Save} variant="primary">Save Changes</Button>
        </div>
      </div>
    </div>
  );
}
