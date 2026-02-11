import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { api } from '@/src/lib/api';
import { Progetto } from '@/src/types/api';
import { colors, spacing, typography, borderRadius, shadows } from '@/src/styles/tokens';
import { API_BASE_URL } from '@/src/lib/constants';

export default function ProgettiScreen() {
  const [data, setData] = useState<Progetto[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const loadData = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(undefined);

      console.log(`📡 Fetching progetti from: ${API_BASE_URL}`);
      const result = await api.getProgetti();
      setData(result);
      console.log(`✅ Loaded ${result.length} progetti`);
    } catch (err) {
      console.error('❌ Error loading progetti:', err);
      setError('Offline: dati di esempio');
      // Fallback data
      setData([
        { id: 1, titolo: 'Corso Python Base', stato: 'active', ore_previste: 40, ore_effettive: 20 },
        { id: 2, titolo: 'Workshop React', stato: 'completed', ore_previste: 20, ore_effettive: 20 },
      ]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData(true);
  }, [loadData]);

  const getStatoColor = (stato?: string | null) => {
    switch (stato?.toLowerCase()) {
      case 'active':
        return colors.success;
      case 'completed':
        return colors.gray500;
      case 'paused':
        return colors.warning;
      case 'cancelled':
        return colors.error;
      default:
        return colors.gray400;
    }
  };

  const getStatoLabel = (stato?: string | null) => {
    switch (stato?.toLowerCase()) {
      case 'active':
        return 'Attivo';
      case 'completed':
        return 'Completato';
      case 'paused':
        return 'In pausa';
      case 'cancelled':
        return 'Annullato';
      default:
        return stato || 'N/A';
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}
      <FlatList
        data={data}
        keyExtractor={(item) => String(item.id)}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card} activeOpacity={0.7}>
            <View style={styles.cardContent}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>{item.titolo}</Text>
                <View
                  style={[
                    styles.statoBadge,
                    { backgroundColor: getStatoColor(item.stato) },
                  ]}
                >
                  <Text style={styles.statoText}>{getStatoLabel(item.stato)}</Text>
                </View>
              </View>
              {item.codice_progetto && (
                <Text style={styles.cardSubtitle}>Cod: {item.codice_progetto}</Text>
              )}
              {item.descrizione && (
                <Text style={styles.cardDetail} numberOfLines={2}>
                  {item.descrizione}
                </Text>
              )}
              <View style={styles.statsRow}>
                {item.ore_previste !== null && item.ore_previste !== undefined && (
                  <View style={styles.statItem}>
                    <Text style={styles.statLabel}>Ore previste</Text>
                    <Text style={styles.statValue}>{item.ore_previste}h</Text>
                  </View>
                )}
                {item.ore_effettive !== null && item.ore_effettive !== undefined && (
                  <View style={styles.statItem}>
                    <Text style={styles.statLabel}>Ore effettive</Text>
                    <Text style={styles.statValue}>{item.ore_effettive}h</Text>
                  </View>
                )}
                {item.budget !== null && item.budget !== undefined && (
                  <View style={styles.statItem}>
                    <Text style={styles.statLabel}>Budget</Text>
                    <Text style={styles.statValue}>€{item.budget.toLocaleString()}</Text>
                  </View>
                )}
              </View>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nessun progetto</Text>
          </View>
        }
        contentContainerStyle={data.length === 0 ? styles.emptyList : undefined}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgSecondary,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgSecondary,
  },
  errorBanner: {
    backgroundColor: colors.warning,
    padding: spacing.md,
    alignItems: 'center',
  },
  errorText: {
    color: colors.white,
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.medium,
  },
  card: {
    backgroundColor: colors.white,
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
    borderRadius: borderRadius.lg,
    ...shadows.md,
  },
  cardContent: {
    padding: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.xs,
  },
  cardTitle: {
    flex: 1,
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold,
    color: colors.gray900,
    marginRight: spacing.sm,
  },
  cardSubtitle: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.medium,
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  cardDetail: {
    fontSize: typography.sizes.sm,
    color: colors.gray600,
    marginTop: spacing.xs,
    lineHeight: typography.sizes.sm * typography.lineHeights.normal,
  },
  statoBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  statoText: {
    fontSize: typography.sizes.xs,
    color: colors.white,
    fontWeight: typography.weights.semibold,
  },
  statsRow: {
    flexDirection: 'row',
    marginTop: spacing.md,
    gap: spacing.md,
  },
  statItem: {
    flex: 1,
  },
  statLabel: {
    fontSize: typography.sizes.xs,
    color: colors.gray500,
    marginBottom: spacing.xs / 2,
  },
  statValue: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.semibold,
    color: colors.gray900,
  },
  emptyList: {
    flex: 1,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyText: {
    fontSize: typography.sizes.base,
    color: colors.gray500,
  },
});
