import axios from 'axios';

const API_BASE_URL = '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach JWT Token & Active Organization ID
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('profitpilot_token');
  const activeOrgId = localStorage.getItem('profitpilot_active_org_id');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (activeOrgId) {
    config.headers['X-Organization-ID'] = activeOrgId;
  }
  return config;
});

// Response Interceptor: Handle 401 unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token if expired or invalid
      localStorage.removeItem('profitpilot_token');
    }
    return Promise.reject(error);
  }
);
