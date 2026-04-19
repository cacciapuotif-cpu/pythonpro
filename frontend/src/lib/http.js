/**
 * Centralized HTTP client for PythonPro
 * Configured with correct base URL and trailing slash handling
 */

import axios from 'axios';

const isPrivateIpv4Host = (hostname) => (
  /^192\.168\.\d{1,3}\.\d{1,3}$/.test(hostname)
  || /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname)
  || /^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(hostname)
  || /^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname)
);

const normalizeApiBase = (rawBase) => {
  const trimmedBase = (rawBase || '').trim().replace(/\/+$/, '');

  const isBrowserRuntime = typeof window !== 'undefined';
  const isLocalDevServer = isBrowserRuntime
    && ['localhost', '127.0.0.1'].includes(window.location.hostname)
    && window.location.port !== '8001';
  const isLanDevServer = isBrowserRuntime
    && isPrivateIpv4Host(window.location.hostname)
    && window.location.port === '3001';

  const inferredBase = isLocalDevServer
    ? 'http://localhost:8001'
    : isLanDevServer
      ? `http://${window.location.hostname}:8001`
      : '';

  const base = trimmedBase || inferredBase;

  if (!base) {
    return '/api/v1';
  }

  if (base.endsWith('/api/v1')) {
    return base;
  }

  if (base.endsWith('/api')) {
    return `${base}/v1`;
  }

  return `${base}/api/v1`;
};

const apiBaseUrl = normalizeApiBase(process.env.REACT_APP_API_URL);
export const apiRootUrl = apiBaseUrl.endsWith('/api/v1')
  ? apiBaseUrl.slice(0, -'/api/v1'.length) || ''
  : apiBaseUrl;

const decodeJwtPayload = (token) => {
  if (!token) return null;

  try {
    const [, payload = ''] = token.split('.');
    if (!payload) return null;

    const normalizedPayload = payload.replace(/-/g, '+').replace(/_/g, '/');
    const base64Payload = normalizedPayload.padEnd(
      normalizedPayload.length + ((4 - (normalizedPayload.length % 4)) % 4),
      '='
    );

    return JSON.parse(window.atob(base64Payload));
  } catch {
    return null;
  }
};

export const isJwtExpired = (token, leewaySeconds = 30) => {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) {
    return true;
  }

  const nowInSeconds = Math.floor(Date.now() / 1000);
  return payload.exp <= nowInSeconds + leewaySeconds;
};

export const clearStoredAuthTokens = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

export const refreshAccessToken = async () => {
  const storedRefreshToken = localStorage.getItem('refresh_token');
  if (!storedRefreshToken) {
    throw new Error('Refresh token non disponibile');
  }

  const formData = new FormData();
  formData.append('refresh_token', storedRefreshToken);

  const response = await axios.post(`${apiBaseUrl}/auth/refresh`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  localStorage.setItem('access_token', response.data.access_token);
  return response.data.access_token;
};

export const ensureValidAccessToken = async () => {
  const storedAccessToken = localStorage.getItem('access_token');
  if (!storedAccessToken) {
    return null;
  }

  if (!isJwtExpired(storedAccessToken)) {
    return storedAccessToken;
  }

  const storedRefreshToken = localStorage.getItem('refresh_token');
  if (!storedRefreshToken || isJwtExpired(storedRefreshToken)) {
    clearStoredAuthTokens();
    return null;
  }

  try {
    return await refreshAccessToken();
  } catch {
    clearStoredAuthTokens();
    return null;
  }
};

// Create axios instance with normalized baseURL including /api/v1 prefix
export const http = axios.create({
  baseURL: apiBaseUrl,
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
          const accessToken = await refreshAccessToken();
          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
          return http(originalRequest);
        }
      } catch (refreshError) {
        clearStoredAuthTokens();
        window.location.href = '/';
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
