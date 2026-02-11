/**
 * Design Tokens - iOS-first Design System
 * Based on Human Interface Guidelines
 */

export const colors = {
  // Primary
  primary: '#007AFF',
  primaryDark: '#0051D5',
  primaryLight: '#5AC8FA',

  // Grayscale
  black: '#000000',
  white: '#FFFFFF',
  gray900: '#1C1C1E',
  gray800: '#2C2C2E',
  gray700: '#3A3A3C',
  gray600: '#48484A',
  gray500: '#636366',
  gray400: '#8E8E93',
  gray300: '#AEAEB2',
  gray200: '#C7C7CC',
  gray100: '#D1D1D6',
  gray50: '#E5E5EA',
  gray25: '#F2F2F7',

  // Semantic
  success: '#34C759',
  warning: '#FF9500',
  error: '#FF3B30',
  info: '#5AC8FA',

  // Backgrounds
  bgPrimary: '#FFFFFF',
  bgSecondary: '#F2F2F7',
  bgTertiary: '#FFFFFF',

  // Overlays
  overlay: 'rgba(0, 0, 0, 0.4)',
  overlayLight: 'rgba(0, 0, 0, 0.2)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const typography = {
  // iOS SF Pro weights
  weights: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
  },

  // Font sizes (supports Dynamic Type)
  sizes: {
    xs: 12,
    sm: 14,
    base: 16,
    lg: 18,
    xl: 20,
    xxl: 24,
    xxxl: 32,
    huge: 40,
  },

  // Line heights
  lineHeights: {
    tight: 1.2,
    normal: 1.5,
    relaxed: 1.75,
  },
};

export const borderRadius = {
  none: 0,
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
};

export const shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
};

// Touch targets (iOS HIG minimum: 44pt)
export const touchTargets = {
  min: 44,
  comfortable: 48,
};

export const zIndex = {
  base: 0,
  dropdown: 1000,
  modal: 2000,
  toast: 3000,
};
