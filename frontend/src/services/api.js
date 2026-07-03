import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const ML_BASE_URL = '/api/ml';

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

// No 401 handling needed — auth is fully bypassed on the backend
apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error)
);

// API Service Methods
export const api = {
  // Auth — kept for interface compatibility but login is not needed
  login: async () => {},
  

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
  },

  // User Management
  createUser: async (userData) => {
    const response = await apiClient.post('/users/', userData);
    return response.data;
  },

  // ML Pipeline — Single document analysis
  mlAnalyze: async (caseId, filePaths, behaviorData = {}, ruleBaseScore = 0) => {
    const response = await apiClient.post(`${ML_BASE_URL}/analyze`, {
      case_id: String(caseId),
      file_paths: filePaths,
      behavior_data: behaviorData,
      rule_base_score: ruleBaseScore,
    });
    return response.data;
  },

  // ML Pipeline — Cross-document pair analysis (e.g. ITR vs Bank Statement)
  mlAnalyzePair: async ({
    caseId,
    primaryPath,
    secondaryPath,
    primaryType = 'Document A',
    secondaryType = 'Document B',
    behaviorData = {},
    ruleBaseScore = 0,
    incomeItr = null,
    incomeBankMonthly = null,
  }) => {
    const response = await apiClient.post(`${ML_BASE_URL}/analyze-pair`, {
      case_id: String(caseId),
      primary_path: primaryPath,
      secondary_path: secondaryPath,
      primary_type: primaryType,
      secondary_type: secondaryType,
      behavior_data: behaviorData,
      rule_base_score: ruleBaseScore,
      income_bank_monthly: incomeBankMonthly,
    });
    return response.data;
  },
};

export const runMLAnalysis = async (caseId, filePaths, behaviorData = {}) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 300 seconds timeout
  try {
    const response = await fetch('/api/ml/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case_id: String(caseId),
        file_paths: filePaths,
        behavior_data: behaviorData
      }),
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      const err = await response.text();
      throw new Error(`ML Analysis failed: ${response.status} - ${err}`);
    }
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') throw new Error('ML Analysis timed out after 300 seconds. Backend may be hung.');
    throw error;
  }
};

export const runCrossDocAnalysis = async (caseId, primaryPath, secondaryPath) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000);
  try {
    const response = await fetch('/api/ml/analyze-pair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case_id: String(caseId),
        primary_path: primaryPath,
        secondary_path: secondaryPath
      }),
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    if (!response.ok) throw new Error('Cross-doc analysis failed');
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') throw new Error('Cross-doc Analysis timed out after 300 seconds.');
    throw error;
  }
};
