import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../../src/lib/auth';
import { useItems } from '../../../src/hooks/useItems';
import {
  Button,
  EmptyState,
  LoadingSpinner,
  showToast,
} from '../../../src/components';
import { colors, spacing, typography, borderRadius, shadows } from '../../../src/styles/tokens';
import type { Item } from '../../../src/types/api';

export default function ItemsListScreen() {
  const router = useRouter();
  const { logout, user } = useAuth();
  const { data: items, isLoading, error, refetch, isRefetching } = useItems();

  React.useLayoutEffect(() => {
    router.setParams({});
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      showToast({
        message: 'Logout effettuato',
        type: 'info',
      });
    } catch (error) {
      showToast({
        message: 'Errore durante il logout',
        type: 'error',
      });
    }
  };

  const renderItem = ({ item }: { item: Item }) => (
    <TouchableOpacity
      style={styles.itemCard}
      onPress={() => router.push(`/(app)/items/${item.id}`)}
      activeOpacity={0.7}
    >
      <View style={styles.itemHeader}>
        <Text style={styles.itemTitle} numberOfLines={1}>
          {item.nome}
        </Text>
        <Ionicons name="chevron-forward" size={20} color={colors.gray400} />
      </View>

      {item.descrizione && (
        <Text style={styles.itemDescription} numberOfLines={2}>
          {item.descrizione}
        </Text>
      )}

      <View style={styles.itemFooter}>
        {item.stato && (
          <View style={styles.statusBadge}>
            <Text style={styles.statusText}>{item.stato}</Text>
          </View>
        )}
        {item.data_modifica && (
          <Text style={styles.itemDate}>
            Modificato: {new Date(item.data_modifica).toLocaleDateString('it-IT')}
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Caricamento items..." />;
  }

  if (error) {
    return (
      <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
        <View style={styles.container}>
          <EmptyState
            icon="alert-circle-outline"
            title="Errore di caricamento"
            description={error.message}
            actionLabel="Riprova"
            onAction={() => refetch()}
          />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Ciao, {user?.nome || 'User'}!</Text>
            <Text style={styles.subGreeting}>Ecco i tuoi items</Text>
          </View>
          <TouchableOpacity onPress={handleLogout} style={styles.logoutButton}>
            <Ionicons name="log-out-outline" size={24} color={colors.error} />
          </TouchableOpacity>
        </View>

        {/* List */}
        <FlatList
          data={items}
          renderItem={renderItem}
          keyExtractor={(item) => item.id.toString()}
          contentContainerStyle={[
            styles.listContent,
            !items?.length && styles.listEmpty,
          ]}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              tintColor={colors.primary}
            />
          }
          ListEmptyComponent={
            <EmptyState
              icon="folder-open-outline"
              title="Nessun item"
              description="Non ci sono items da visualizzare"
            />
          }
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bgSecondary,
  },
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    backgroundColor: colors.white,
  },
  greeting: {
    fontSize: typography.sizes.xxl,
    fontWeight: typography.weights.bold,
    color: colors.gray900,
  },
  subGreeting: {
    fontSize: typography.sizes.base,
    color: colors.gray600,
    marginTop: spacing.xs,
  },
  logoutButton: {
    padding: spacing.sm,
  },
  listContent: {
    padding: spacing.md,
  },
  listEmpty: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  itemCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    ...shadows.sm,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  itemTitle: {
    flex: 1,
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold,
    color: colors.gray900,
  },
  itemDescription: {
    fontSize: typography.sizes.base,
    color: colors.gray600,
    marginBottom: spacing.md,
    lineHeight: typography.sizes.base * typography.lineHeights.normal,
  },
  itemFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statusBadge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs / 2,
    borderRadius: borderRadius.sm,
  },
  statusText: {
    fontSize: typography.sizes.xs,
    color: colors.white,
    fontWeight: typography.weights.medium,
  },
  itemDate: {
    fontSize: typography.sizes.xs,
    color: colors.gray500,
  },
});
