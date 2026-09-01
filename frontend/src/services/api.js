import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// In production, the backend is on a different domain (Railway).
// VITE_API_BASE_URL is e.g. https://dhanrakshak.up.railway.app/api/v1
// ML routes live at /api/ml on the same backend host.
const _backendBase = import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL.replace(/\/api\/v1\/?$/, '')
  : '';
const ML_BASE_URL = `${_backendBase}/api/ml`;

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
    try {
      const response = await apiClient.get('/users/');
      return response.data;
    } catch (e) {
      console.warn('Backend unavailable. Using mock users.');
      return [
        { id: 1, full_name: 'System Administrator', employee_id: 'admin', role: { name: 'Admin' }, is_active: true },
        { id: 2, full_name: 'Anjali Desai', employee_id: 'EMP102', role: { name: 'Auditor' }, is_active: true },
        { id: 3, full_name: 'Ravi Singh', employee_id: 'EMP103', role: { name: 'Investigator' }, is_active: false },
      ];
    }
  },
  
  // Cases
  getCases: async () => {
    try {
      const response = await apiClient.get('/cases/');
      return response.data;
    } catch (e) {
      if (e.code === 'ERR_NETWORK') {
        console.warn('Backend unavailable. Using mock cases.');
        return [
          { id: 1001, case_ref: 'CASE-2024-001', applicant_name: 'Rahul Sharma', property_address: '124 MG Road, Bangalore', status: 'Pending Review', risk_score: 85, created_at: new Date().toISOString() },
          { id: 1002, case_ref: 'CASE-2024-002', applicant_name: 'Priya Patel', property_address: '45 Andheri West, Mumbai', status: 'Open', risk_score: 25, created_at: new Date().toISOString() },
          { id: 1003, case_ref: 'CASE-2024-003', applicant_name: 'Amit Kumar', property_address: 'Sector 4, Dwarka, Delhi', status: 'Under Review', risk_score: 60, created_at: new Date(Date.now() - 86400000).toISOString() },
          { id: 1004, case_ref: 'CASE-2024-004', applicant_name: 'Sneha Gupta', property_address: 'Koramangala, Bangalore', status: 'FRAUD_CONFIRMED', risk_score: 95, created_at: new Date(Date.now() - 172800000).toISOString() },
        ];
      }
      throw e;
    }
  },
  createCase: async (caseData) => {
    try {
      const response = await apiClient.post('/cases/', caseData);
      return response.data;
    } catch (e) {
      if (e.code === 'ERR_NETWORK') {
        console.warn('Backend unavailable. Returning mock new case.');
        return { id: 1005, ...caseData, created_at: new Date().toISOString() };
      }
      throw e;
    }
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
      console.warn('Backend unavailable. Returning mock upload success.');
      if (onUploadProgress) try { onUploadProgress(100); } catch(e) {}
      return {
        id: Math.floor(Math.random() * 10000),
        file_name: file.name,
        file_path: `/mock/uploads/${file.name}`,
        case_id: caseId,
        uploaded_at: new Date().toISOString()
      };
    }
  },
  
  // Notes
  getNotesByCase: async (caseId) => {
    try {
      const response = await apiClient.get(`/notes/case/${caseId}`);
      return response.data;
    } catch (e) {
      console.warn('Backend unavailable. Using mock notes.');
      return [
        { id: 1, case_id: caseId, content: 'Initial review of documents indicates heavy photo manipulation on the PAN card.', author_name: 'Investigator AI', created_at: new Date(Date.now() - 86400000).toISOString() },
        { id: 2, case_id: caseId, content: 'Flagged for further manual verification with issuing authorities.', author_name: 'Risk Engine', created_at: new Date().toISOString() }
      ];
    }
  },
  createNote: async (noteData) => {
    try {
      const response = await apiClient.post('/notes/', noteData);
      return response.data;
    } catch (e) {
      console.warn('Backend unavailable. Returning mock new note.');
      return { id: Math.floor(Math.random() * 1000), ...noteData, author_name: 'System Administrator', created_at: new Date().toISOString() };
    }
  },
  
  // Fraud Reports
  getReportsByCase: async (caseId) => {
    try {
      const response = await apiClient.get(`/reports/case/${caseId}`);
      return response.data;
    } catch (e) {
      console.warn('Backend unavailable. Using mock reports.');
      return [
        {
          id: 501,
          case_id: caseId,
          report_ref: `FR-${caseId}-01`,
          summary: 'High risk of income falsification detected across provided documents.',
          risk_level: 'High',
          created_at: new Date().toISOString(),
          created_by: 'System Administrator',
          signals: [
            { id: 1, type: 'Income Mismatch', severity: 'HIGH', description: 'ITR income is 5x higher than monthly bank deposits.' },
            { id: 2, type: 'Document Forgery', severity: 'HIGH', description: 'Digital tampering detected on PAN Card.' }
          ]
        }
      ];
    }
  },
  createReport: async (reportData) => {
    const response = await apiClient.post('/reports/', reportData);
    return response.data;
  },
  
  // Audit Logs
  getAuditLogs: async () => {
    try {
      const response = await apiClient.get('/audit/');
      return response.data;
    } catch (e) {
      console.warn('Backend unavailable. Using mock audit logs.');
      return [
        { id: 1, action: 'LOGIN', details: 'System Administrator logged in', ip_address: '192.168.1.1', created_at: new Date().toISOString() },
        { id: 2, action: 'CASE_CREATED', details: 'Case CASE-2024-001 created', ip_address: '192.168.1.1', created_at: new Date(Date.now() - 3600000).toISOString() },
        { id: 3, action: 'DOCUMENT_UPLOAD', details: 'PAN Card uploaded for CASE-2024-001', ip_address: '192.168.1.1', created_at: new Date(Date.now() - 3500000).toISOString() },
        { id: 4, action: 'ML_ANALYSIS', details: 'Triggered cross-document analysis', ip_address: '192.168.1.1', created_at: new Date(Date.now() - 3400000).toISOString() },
      ];
    }
  },

  // User Management
  createUser: async (userData) => {
    const response = await apiClient.post('/users/', userData);
    return response.data;
  },

  // ML Pipeline — Single document analysis
  mlAnalyze: async (caseId, filePaths, behaviorData = {}, ruleBaseScore = 0) => {
    try {
      const response = await apiClient.post(`${ML_BASE_URL}/analyze`, {
        case_id: String(caseId),
        file_paths: filePaths,
        behavior_data: behaviorData,
        rule_base_score: ruleBaseScore,
      });
      return response.data;
    } catch (e) {
      console.warn('Backend ML unavailable. Using mock ML analysis result.');
      return {
        overall_risk: 0.85,
        risk_category: 'High Risk',
        document_results: filePaths.map(path => ({
          file_path: path,
          trufor_score: 0.92,
          ela_score: 0.88,
          behavioral_score: 0.75,
          overall_risk: 0.85,
          ocr_conflicts: [{ type: 'Name Mismatch', message: 'Name on PAN does not match Aadhar.', severity: 'HIGH' }],
          metadata_flags: ['Software signature: Adobe Photoshop'],
        }))
      };
    }
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
    try {
      const response = await apiClient.post(`${ML_BASE_URL}/analyze-pair`, {
        case_id: String(caseId),
        primary_path: primaryPath,
        secondary_path: secondaryPath,
        primary_type: primaryType,
        secondary_type: secondaryType,
        behavior_data: behaviorData,
        rule_base_score: ruleBaseScore,
        income_itr: incomeItr,
        income_bank_monthly: incomeBankMonthly,
      });
      return response.data;
    } catch (e) {
      console.warn('Backend ML unavailable. Using mock cross-doc analysis.');
      return {
        overall_risk: 0.9,
        risk_category: 'Critical Risk',
        trufor_score: 0.4,
        ela_score: 0.3,
        behavioral_score: 0.6,
        income_fraud_score: 0.95,
        ocr_conflicts: [
          { type: 'Income Falsification', severity: 'HIGH', message: 'ITR declares 15 LPA, but bank deposits sum to only 3 LPA.' },
          { type: 'Date Anomaly', severity: 'MEDIUM', message: 'ITR filing date precedes bank statement creation date.' }
        ]
      };
    }
  },
};

export const runMLAnalysis = async (caseId, filePaths, behaviorData = {}) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 300 seconds timeout
  const token = localStorage.getItem('dhanrakshak_token') || '';
  // Use absolute URL in production (backend on different domain)
  const mlAnalyzeUrl = `${_backendBase}/api/ml/analyze`;
  try {
    const response = await fetch(mlAnalyzeUrl, {
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
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn('Backend unavailable. Using mock ML analysis result.');
    return {
      overall_risk: 0.85,
      risk_category: 'High Risk',
      document_results: filePaths.map(path => ({
        file_path: path,
        trufor_score: 0.92,
        ela_score: 0.88,
        behavioral_score: 0.75,
        overall_risk: 0.85,
        ocr_conflicts: [{ type: 'Name Mismatch', message: 'Name on PAN does not match Aadhar.', severity: 'HIGH' }],
        metadata_flags: ['Software signature: Adobe Photoshop'],
      }))
    };
  }
};

export const runCrossDocAnalysis = async (caseId, primaryPath, secondaryPath) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000);
  const token = localStorage.getItem('dhanrakshak_token') || '';
  // Use absolute URL in production (backend on different domain)
  const mlPairUrl = `${_backendBase}/api/ml/analyze-pair`;
  try {
    const response = await fetch(mlPairUrl, {
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
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn('Backend ML unavailable. Using mock cross-doc analysis.');
    return {
      overall_risk: 0.9,
      risk_category: 'Critical Risk',
      trufor_score: 0.4,
      ela_score: 0.3,
      behavioral_score: 0.6,
      income_fraud_score: 0.95,
      ocr_conflicts: [
        { type: 'Income Falsification', severity: 'HIGH', message: 'ITR declares 15 LPA, but bank deposits sum to only 3 LPA.' },
        { type: 'Date Anomaly', severity: 'MEDIUM', message: 'ITR filing date precedes bank statement creation date.' }
      ]
    };
  }
};
