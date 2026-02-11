/**
 * Centralized HTTP client for PythonPro
 * Configured with correct base URL and trailing slash handling
 */

import axios from 'axios';

// Get API base URL and strip trailing slashes
const base = (process.env.REACT_APP_API_URL || 'http://localhost:8001').replace(/\/+$/, '');

// Create axios instance with normalized baseURL including /api/v1 prefix
export const http = axios.create({
  baseURL: `${base}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth
http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add request ID for tracking
    config.headers['X-Request-ID'] = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 (token expired)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const formData = new FormData();
          formData.append('refresh_token', refreshToken);

          const response = await axios.post(`${base}/api/v1/auth/refresh`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });

          localStorage.setItem('access_token', response.data.access_token);
          originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;
          return http(originalRequest);
        }
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    // Handle network errors
    if (!error.response) {
      error.message = 'Errore di connessione. Verifica la tua connessione internet.';
    }

    return Promise.reject(error);
  }
);

export default http;
