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
import { Ente } from '@/src/types/api';
import { colors, spacing, typography, borderRadius, shadows } from '@/src/styles/tokens';
import { API_BASE_URL } from '@/src/lib/constants';

export default function EntiScreen() {
  const [data, setData] = useState<Ente[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const loadData = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(undefined);

      console.log(`📡 Fetching enti from: ${API_BASE_URL}`);
      const result = await api.getEnti();
      setData(result);
      console.log(`✅ Loaded ${result.length} enti`);
    } catch (err) {
      console.error('❌ Error loading enti:', err);
      setError('Offline: dati di esempio');
      // Fallback data
      setData([
        { id: 1, ragione_sociale: 'Ente Formazione S.r.l.', partita_iva: '12345678901', citta: 'Milano', is_active: true },
        { id: 2, ragione_sociale: 'Istituto Tecnico', partita_iva: '98765432109', citta: 'Roma', is_active: true },
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
              <Text style={styles.cardTitle}>{item.ragione_sociale}</Text>
              <Text style={styles.cardSubtitle}>P.IVA: {item.partita_iva}</Text>
              {item.citta && (
                <Text style={styles.cardDetail}>📍 {item.citta}</Text>
              )}
              {item.email && (
                <Text style={styles.cardDetail}>✉️ {item.email}</Text>
              )}
              {item.telefono && (
                <Text style={styles.cardDetail}>📞 {item.telefono}</Text>
              )}
              {!item.is_active && (
                <View style={styles.inactiveBadge}>
                  <Text style={styles.inactiveText}>Non attivo</Text>
                </View>
              )}
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nessun ente</Text>
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
  cardTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold,
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  cardSubtitle: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  cardDetail: {
    fontSize: typography.sizes.sm,
    color: colors.gray600,
    marginTop: spacing.xs,
  },
  inactiveBadge: {
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
    backgroundColor: colors.gray200,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  inactiveText: {
    fontSize: typography.sizes.xs,
    color: colors.gray700,
    fontWeight: typography.weights.medium,
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
