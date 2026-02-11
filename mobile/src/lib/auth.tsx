/**
 * Authentication Context and Hooks
 * Manages auth state, token persistence, and user session
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from './api';
import { STORAGE_KEYS } from './constants';
import type { User, LoginRequest } from '../types/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  /**
   * Check if user has valid token and restore session
   */
  const checkAuthStatus = async () => {
    try {
      const [token, userJson] = await AsyncStorage.multiGet([
        STORAGE_KEYS.ACCESS_TOKEN,
        STORAGE_KEYS.USER,
      ]);

      const accessToken = token[1];
      const savedUser = userJson[1];

      if (accessToken && savedUser) {
        setUser(JSON.parse(savedUser));

        // Optionally validate token by fetching fresh user data
        try {
          const freshUser = await api.getMe();
          setUser(freshUser);
          await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(freshUser));
        } catch (error) {
          // Token might be invalid, clear session
          console.warn('Failed to validate token:', error);
          await clearSession();
        }
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Login user
   */
  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      const { user: loggedInUser } = await api.login(credentials);
      setUser(loggedInUser);
      await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(loggedInUser));
    } catch (error) {
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Logout user and clear session
   */
  const logout = async () => {
    setIsLoading(true);
    try {
      await api.logout();
      await clearSession();
    } catch (error) {
      console.error('Logout error:', error);
      // Clear local state anyway
      await clearSession();
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Refresh user data
   */
  const refreshUser = async () => {
    try {
      const freshUser = await api.getMe();
      setUser(freshUser);
      await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(freshUser));
    } catch (error) {
      console.error('Error refreshing user:', error);
      throw error;
    }
  };

  /**
   * Clear local session
   */
  const clearSession = async () => {
    setUser(null);
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.ACCESS_TOKEN,
      STORAGE_KEYS.REFRESH_TOKEN,
      STORAGE_KEYS.USER,
    ]);
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Hook to access auth context
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

/**
 * Hook to get current session
 */
export const useSession = () => {
  const { user, isAuthenticated } = useAuth();
  return { user, isAuthenticated };
};
