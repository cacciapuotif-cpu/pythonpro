/**
 * API Client - Typed Axios with Zod Validation
 * Features:
 * - Bearer token authentication
 * - Automatic retry on 401 with refresh token
 * - Error mapping to human-readable messages
 * - Response validation with Zod
 * - Mock mode support
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { z } from 'zod';
import {
  API_BASE_URL,
  USE_MOCK,
  STORAGE_KEYS,
  API_ENDPOINTS,
  ERROR_MESSAGES,
} from './constants';
import {
  MOCK_USER,
  MOCK_TOKEN,
  MOCK_ITEMS,
  delay,
} from './mockData';
import type {
  LoginRequest,
  TokenResponse,
  User,
  Item,
  ItemsListResponse,
  ApiError,
  Collaboratore,
  Ente,
  Progetto,
  Evento,
} from '../types/api';
import {
  LoginRequestSchema,
  TokenResponseSchema,
  UserSchema,
  ItemSchema,
  ItemsListResponseSchema,
  CollaboratoreSchema,
  EnteSchema,
  ProgettoSchema,
  EventoSchema,
} from '../types/api';

class ApiClient {
  private client: AxiosInstance;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value?: unknown) => void;
    reject: (reason?: unknown) => void;
  }> = [];

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
    this.logConfiguration();
  }

  private logConfiguration() {
    console.log('\n📡 API Client Configuration:');
    console.log(`🌐 Base URL: ${API_BASE_URL}`);
    console.log(`🎭 Mock Mode: ${USE_MOCK ? 'ENABLED' : 'DISABLED'}`);
    console.log('');
  }

  /**
   * Setup axios interceptors for auth and error handling
   */
  private setupInterceptors() {
    // Request interceptor - Add Bearer token
    this.client.interceptors.request.use(
      async (config) => {
        const token = await AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - Handle 401 and retry with refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as AxiosRequestConfig & {
          _retry?: boolean;
        };

        // Handle 401 Unauthorized
        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            // Queue the request while refreshing
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then(() => this.client(originalRequest))
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            const refreshToken = await AsyncStorage.getItem(
              STORAGE_KEYS.REFRESH_TOKEN
            );

            if (refreshToken) {
              // Try to refresh token
              const newTokens = await this.refreshToken(refreshToken);
              await this.saveTokens(newTokens);

              // Retry all queued requests
              this.failedQueue.forEach((prom) => prom.resolve());
              this.failedQueue = [];

              return this.client(originalRequest);
            }
          } catch (refreshError) {
            // Refresh failed - clear auth and reject
            this.failedQueue.forEach((prom) => prom.reject(refreshError));
            this.failedQueue = [];
            await this.clearAuth();
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(this.mapError(error));
      }
    );
  }

  /**
   * Map axios errors to human-readable messages
   */
  private mapError(error: AxiosError): Error {
    if (!error.response) {
      return new Error(ERROR_MESSAGES.NETWORK);
    }

    const status = error.response.status;
    const data = error.response.data as ApiError | undefined;

    switch (status) {
      case 401:
        return new Error(ERROR_MESSAGES.UNAUTHORIZED);
      case 403:
        return new Error(ERROR_MESSAGES.FORBIDDEN);
      case 404:
        return new Error(ERROR_MESSAGES.NOT_FOUND);
      case 422:
        // Validation error
        if (data && typeof data.detail === 'object') {
          const firstError = data.detail[0];
          return new Error(firstError?.msg || ERROR_MESSAGES.VALIDATION);
        }
        return new Error(
          typeof data?.detail === 'string'
            ? data.detail
            : ERROR_MESSAGES.VALIDATION
        );
      case 500:
      case 502:
      case 503:
        return new Error(ERROR_MESSAGES.SERVER_ERROR);
      default:
        return new Error(
          typeof data?.detail === 'string'
            ? data.detail
            : ERROR_MESSAGES.UNKNOWN
        );
    }
  }

  /**
   * Validate response with Zod schema
   */
  private validate<T>(schema: z.ZodSchema<T>, data: unknown): T {
    try {
      return schema.parse(data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.error('Validation error:', error.errors);
        throw new Error('Risposta del server non valida');
      }
      throw error;
    }
  }

  /**
   * Save tokens to AsyncStorage
   */
  private async saveTokens(tokens: TokenResponse) {
    await AsyncStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, tokens.access_token);
    if (tokens.refresh_token) {
      await AsyncStorage.setItem(
        STORAGE_KEYS.REFRESH_TOKEN,
        tokens.refresh_token
      );
    }
  }

  /**
   * Clear authentication data
   */
  private async clearAuth() {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.ACCESS_TOKEN,
      STORAGE_KEYS.REFRESH_TOKEN,
      STORAGE_KEYS.USER,
    ]);
  }

  // ============== AUTH ENDPOINTS ==============

  /**
   * Login with email and password
   */
  async login(credentials: LoginRequest): Promise<{
    tokens: TokenResponse;
    user: User;
  }> {
    if (USE_MOCK) {
      await delay();
      return { tokens: MOCK_TOKEN, user: MOCK_USER };
    }

    // Validate request
    const validatedCredentials = this.validate(
      LoginRequestSchema,
      credentials
    );

    // Send as form data (common for OAuth2)
    const formData = new URLSearchParams();
    formData.append('username', validatedCredentials.email);
    formData.append('password', validatedCredentials.password);

    const response = await this.client.post(API_ENDPOINTS.LOGIN, formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    const tokens = this.validate(TokenResponseSchema, response.data);
    await this.saveTokens(tokens);

    // Fetch user info
    const user = await this.getMe();

    return { tokens, user };
  }

  /**
   * Refresh access token
   */
  private async refreshToken(refreshToken: string): Promise<TokenResponse> {
    const response = await this.client.post(API_ENDPOINTS.REFRESH, {
      refresh_token: refreshToken,
    });

    return this.validate(TokenResponseSchema, response.data);
  }

  /**
   * Get current user
   */
  async getMe(): Promise<User> {
    if (USE_MOCK) {
      await delay();
      return MOCK_USER;
    }

    const response = await this.client.get(API_ENDPOINTS.ME);
    return this.validate(UserSchema, response.data);
  }

  /**
   * Logout
   */
  async logout(): Promise<void> {
    await this.clearAuth();
  }

  // ============== ITEMS ENDPOINTS ==============

  /**
   * Get all items
   */
  async getItems(): Promise<Item[]> {
    if (USE_MOCK) {
      await delay();
      return MOCK_ITEMS;
    }

    const response = await this.client.get(API_ENDPOINTS.ITEMS);

    // Handle both array and paginated response
    if (Array.isArray(response.data)) {
      return z.array(ItemSchema).parse(response.data);
    }

    const validated = this.validate(ItemsListResponseSchema, response.data);
    return validated.items;
  }

  /**
   * Get single item by ID
   */
  async getItem(id: number): Promise<Item> {
    if (USE_MOCK) {
      await delay();
      const item = MOCK_ITEMS.find((i) => i.id === id);
      if (!item) throw new Error(ERROR_MESSAGES.NOT_FOUND);
      return item;
    }

    const response = await this.client.get(API_ENDPOINTS.ITEM_DETAIL(id));
    return this.validate(ItemSchema, response.data);
  }

  /**
   * Update item
   */
  async updateItem(id: number, data: Partial<Item>): Promise<Item> {
    if (USE_MOCK) {
      await delay();
      const item = MOCK_ITEMS.find((i) => i.id === id);
      if (!item) throw new Error(ERROR_MESSAGES.NOT_FOUND);
      return { ...item, ...data, id };
    }

    const response = await this.client.put(
      API_ENDPOINTS.ITEM_DETAIL(id),
      data
    );
    return this.validate(ItemSchema, response.data);
  }

  /**
   * Create item
   */
  async createItem(data: Omit<Item, 'id'>): Promise<Item> {
    if (USE_MOCK) {
      await delay();
      const newItem: Item = {
        ...data,
        id: Math.max(...MOCK_ITEMS.map((i) => i.id)) + 1,
        data_creazione: new Date().toISOString(),
        data_modifica: new Date().toISOString(),
      };
      MOCK_ITEMS.push(newItem);
      return newItem;
    }

    const response = await this.client.post(API_ENDPOINTS.ITEMS, data);
    return this.validate(ItemSchema, response.data);
  }

  /**
   * Delete item
   */
  async deleteItem(id: number): Promise<void> {
    if (USE_MOCK) {
      await delay();
      const index = MOCK_ITEMS.findIndex((i) => i.id === id);
      if (index === -1) throw new Error(ERROR_MESSAGES.NOT_FOUND);
      MOCK_ITEMS.splice(index, 1);
      return;
    }

    await this.client.delete(API_ENDPOINTS.ITEM_DETAIL(id));
  }

  // ============== GESTIONALE ENDPOINTS ==============

  /**
   * Get all collaboratori
   */
  async getCollaboratori(): Promise<Collaboratore[]> {
    if (USE_MOCK) {
      await delay();
      return [
        { id: 1, nome: 'Mario', cognome: 'Rossi', email: 'm.rossi@example.com', ruolo: 'Formatore' },
        { id: 2, nome: 'Giulia', cognome: 'Verde', email: 'g.verde@example.com', ruolo: 'PM' },
      ];
    }

    const response = await this.client.get(API_ENDPOINTS.COLLABORATORI);

    // Handle both array and nested response
    if (Array.isArray(response.data)) {
      return z.array(CollaboratoreSchema).parse(response.data);
    }

    return z.array(CollaboratoreSchema).parse(response.data);
  }

  /**
   * Get all enti
   */
  async getEnti(): Promise<Ente[]> {
    if (USE_MOCK) {
      await delay();
      return [
        { id: 1, ragione_sociale: 'Ente Formazione S.r.l.', partita_iva: '12345678901', citta: 'Milano' },
        { id: 2, ragione_sociale: 'Istituto Tecnico', partita_iva: '98765432109', citta: 'Roma' },
      ];
    }

    const response = await this.client.get(API_ENDPOINTS.ENTI);

    // Handle both array and nested response
    if (Array.isArray(response.data)) {
      return z.array(EnteSchema).parse(response.data);
    }

    return z.array(EnteSchema).parse(response.data);
  }

  /**
   * Get all progetti
   */
  async getProgetti(): Promise<Progetto[]> {
    if (USE_MOCK) {
      await delay();
      return [
        { id: 1, titolo: 'Corso Python Base', stato: 'active', ore_previste: 40 },
        { id: 2, titolo: 'Workshop React', stato: 'completed', ore_previste: 20 },
      ];
    }

    const response = await this.client.get(API_ENDPOINTS.PROGETTI);

    // Handle both array and nested response
    if (Array.isArray(response.data)) {
      return z.array(ProgettoSchema).parse(response.data);
    }

    return z.array(ProgettoSchema).parse(response.data);
  }

  /**
   * Get all eventi calendario (presenze)
   */
  async getCalendario(): Promise<Evento[]> {
    if (USE_MOCK) {
      await delay();
      return [
        {
          id: 1,
          collaborator_id: 1,
          project_id: 1,
          data: '2025-11-02',
          ora_inizio: '09:00',
          ora_fine: '13:00',
          ore_lavorate: 4,
          luogo: 'Aula A',
          tipo_attivita: 'Lezione'
        },
        {
          id: 2,
          collaborator_id: 2,
          project_id: 2,
          data: '2025-11-03',
          ora_inizio: '14:00',
          ora_fine: '18:00',
          ore_lavorate: 4,
          luogo: 'Online',
          tipo_attivita: 'Workshop'
        },
      ];
    }

    const response = await this.client.get(API_ENDPOINTS.CALENDARIO);

    // Handle both array and nested response
    if (Array.isArray(response.data)) {
      return z.array(EventoSchema).parse(response.data);
    }

    return z.array(EventoSchema).parse(response.data);
  }
}

// Export singleton instance
export const api = new ApiClient();
