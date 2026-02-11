import { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Slot, useRouter, useSegments } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../src/lib/auth';
import { Toast, setToastRef, LoadingSpinner } from '../src/components';
import * as SplashScreen from 'expo-splash-screen';

// Prevent the splash screen from auto-hiding
SplashScreen.preventAutoHideAsync();

// Create QueryClient
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: true,
    },
  },
});

// Auth Protection
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(app)';

    if (!isAuthenticated && inAuthGroup) {
      // Redirect to login
      router.replace('/(public)/login');
    } else if (isAuthenticated && !inAuthGroup) {
      // Redirect to app
      router.replace('/(app)/items');
    }
  }, [isAuthenticated, isLoading, segments]);

  useEffect(() => {
    if (!isLoading) {
      SplashScreen.hideAsync();
    }
  }, [isLoading]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Caricamento..." />;
  }

  return <>{children}</>;
}

// Toast Provider
function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toastProps, setToastProps] = useState<{
    message: string;
    type?: 'success' | 'error' | 'info' | 'warning';
    duration?: number;
  } | null>(null);

  useEffect(() => {
    setToastRef((props) => setToastProps(props));
  }, []);

  return (
    <View style={{ flex: 1 }}>
      {children}
      {toastProps && (
        <Toast
          {...toastProps}
          visible={!!toastProps}
          onHide={() => setToastProps(null)}
        />
      )}
    </View>
  );
}

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGuard>
          <ToastProvider>
            <Slot />
          </ToastProvider>
        </AuthGuard>
      </AuthProvider>
    </QueryClientProvider>
  );
}
