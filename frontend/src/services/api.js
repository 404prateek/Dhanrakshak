import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to attach JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('dhanrakshak_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle global 401s
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token and emit a custom event to trigger logout without circular dependencies
      localStorage.removeItem('dhanrakshak_token');
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    return Promise.reject(error);
  }
);

// API Service Methods
export const api = {
  // Auth
  login: async (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    // Auth endpoint requires application/x-www-form-urlencoded
    const response = await apiClient.post('/auth/token', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return response.data;
  },
  
  // Users
  getCurrentUser: async () => {
    const response = await apiClient.get('/users/me');
    return response.data;
  },
  getUsers: async () => {
    const response = await apiClient.get('/users/');
    return response.data;
  },
  
  // Cases
  getCases: async () => {
    const response = await apiClient.get('/cases/');
    return response.data;
  },
  createCase: async (caseData) => {
    const response = await apiClient.post('/cases/', caseData);
    return response.data;
  },
  updateCaseStatus: async (caseId, status) => {
    const response = await apiClient.patch(`/cases/${caseId}/status`, { status });
    return response.data;
  },
  
  // Documents
  uploadDocument: async (caseId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(`/cases/${caseId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },
  
  // Notes
  getNotesByCase: async (caseId) => {
    const response = await apiClient.get(`/notes/case/${caseId}`);
    return response.data;
  },
  createNote: async (noteData) => {
    const response = await apiClient.post('/notes/', noteData);
    return response.data;
  },
  
  // Fraud Reports
  getReportsByCase: async (caseId) => {
    const response = await apiClient.get(`/reports/case/${caseId}`);
    return response.data;
  },
  createReport: async (reportData) => {
    const response = await apiClient.post('/reports/', reportData);
    return response.data;
  },
  
  // Audit Logs
  getAuditLogs: async () => {
    const response = await apiClient.get('/audit/');
    return response.data;
  }
};
