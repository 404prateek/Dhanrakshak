import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Plus, UserPlus, Shield, MoreVertical } from 'lucide-react';
import { Table } from '../components/ui/Table';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { StatusPill } from '../components/ui/Badges';
import { api } from '../services/api';

export function UserManagement() {
  const [searchTerm, setSearchTerm] = useState('');

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: api.getUsers,
  });

  const filteredUsers = users.filter(user => 
    user.employee_id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    user.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (user.role?.name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns = [
    { header: 'Employee ID', accessorKey: 'employee_id' },
    { header: 'Name', accessorKey: 'full_name' },
    { header: 'Role', cell: (row) => {
      const roleName = row.role?.name || 'N/A';
      return (
        <span className="flex items-center text-sm">
          {(roleName.includes('Analyst') || roleName.includes('Underwriter') || roleName.includes('Admin')) ? 
            <Shield className="w-4 h-4 mr-1 text-blue-500" /> : null}
          {roleName}
        </span>
      );
    }},
    { header: 'Branch', accessorKey: 'branch', cell: (row) => row.branch || 'N/A' },
    { header: 'Status', cell: (row) => <StatusPill status={row.is_active ? 'Active' : 'Inactive'} /> },
    { header: 'Actions', cell: () => (
      <button className="text-slate-400 hover:text-slate-600">
        <MoreVertical className="w-5 h-5" />
      </button>
    ) },
  ];

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-6rem)]">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
          <p className="mt-1 text-sm text-slate-500">Manage employee access, roles, and branch assignments.</p>
        </div>
        <Button icon={UserPlus} variant="primary">Add New User</Button>
      </div>

      <div className="enterprise-card flex-1 flex flex-col min-h-0">
        <div className="p-4 border-b border-slate-200 bg-white flex flex-wrap gap-4 items-center justify-between">
          <div className="w-full sm:max-w-md">
            <Input 
              icon={Search} 
              placeholder="Search by Employee ID, Name or Role..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex items-center space-x-2">
            <select className="enterprise-input w-40">
              <option>All Branches</option>
              <option>Mumbai HQ</option>
              <option>Delhi Branch</option>
              <option>Bengaluru Branch</option>
            </select>
            <select className="enterprise-input w-40">
              <option>All Roles</option>
              <option>Admin</option>
              <option>Fraud Analyst</option>
              <option>Underwriter</option>
              <option>Investigator</option>
              <option>Compliance</option>
            </select>
          </div>
        </div>
        
        <div className="flex-1 overflow-auto bg-slate-50">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : users.length === 0 ? (
            <div className="flex h-full items-center justify-center text-slate-500">
              No users found.
            </div>
          ) : (
            <Table columns={columns} data={filteredUsers} className="h-full bg-white" />
          )}
        </div>
      </div>
    </div>
  );
}
