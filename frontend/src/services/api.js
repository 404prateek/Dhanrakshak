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
  // Accepts optional onUploadProgress callback for progress UI
  uploadDocument: async (caseId, file, onUploadProgress, signal) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      if (onUploadProgress) {
        try { onUploadProgress(0); } catch (e) { /* swallow callback errors */ }
      }
      const response = await fetch(`${API_BASE_URL}/cases/${caseId}/documents`, {
        method: 'POST',
        body: formData,
        signal,
        headers: {
          Authorization: apiClient.defaults.headers.Authorization || `Bearer ${localStorage.getItem('dhanrakshak_token') || ''}`,
        },
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Upload failed with status ${response.status}`);
      }
      const data = await response.json();
      if (onUploadProgress) {
        try { onUploadProgress(100); } catch (e) { /* swallow callback errors */ }
      }
      return data;
    } catch (error) {
      throw error;
    }
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
      income_itr: incomeItr,                  // was missing — now included
      income_bank_monthly: incomeBankMonthly,
    });
    return response.data;
  },
};

export const runMLAnalysis = async (caseId, filePaths, behaviorData = {}) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 300 seconds timeout
  const token = localStorage.getItem('dhanrakshak_token') || '';
  try {
    const response = await fetch('/api/ml/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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
  const token = localStorage.getItem('dhanrakshak_token') || '';
  try {
    const response = await fetch('/api/ml/analyze-pair', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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
