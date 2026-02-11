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
import { Evento } from '@/src/types/api';
import { colors, spacing, typography, borderRadius, shadows } from '@/src/styles/tokens';
import { API_BASE_URL } from '@/src/lib/constants';

export default function CalendarioScreen() {
  const [data, setData] = useState<Evento[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const loadData = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(undefined);

      console.log(`📡 Fetching calendario from: ${API_BASE_URL}`);
      const result = await api.getCalendario();

      // Ordina per data (ISO format)
      const sorted = result.sort((a, b) => {
        const dateA = new Date(a.data).getTime();
        const dateB = new Date(b.data).getTime();
        return dateB - dateA; // Più recenti prima
      });

      setData(sorted);
      console.log(`✅ Loaded ${result.length} eventi`);
    } catch (err) {
      console.error('❌ Error loading calendario:', err);
      setError('Offline: dati di esempio');
      // Fallback data
      setData([
        {
          id: 1,
          collaborator_id: 1,
          project_id: 1,
          data: '2025-11-02',
          ora_inizio: '09:00',
          ora_fine: '13:00',
          ore_lavorate: 4,
          luogo: 'Aula A',
          tipo_attivita: 'Lezione',
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
          tipo_attivita: 'Workshop',
        },
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

  const formatDate = (isoDate: string) => {
    try {
      const date = new Date(isoDate);
      return new Intl.DateTimeFormat('it-IT', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }).format(date);
    } catch {
      return isoDate;
    }
  };

  const formatTime = (time?: string | null) => {
    if (!time) return '';
    return time.substring(0, 5); // HH:MM
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
              <View style={styles.dateSection}>
                <Text style={styles.dateText}>{formatDate(item.data)}</Text>
                {item.ora_inizio && item.ora_fine && (
                  <Text style={styles.timeText}>
                    {formatTime(item.ora_inizio)} - {formatTime(item.ora_fine)}
                  </Text>
                )}
              </View>

              {item.tipo_attivita && (
                <View style={styles.tipoBadge}>
                  <Text style={styles.tipoText}>{item.tipo_attivita}</Text>
                </View>
              )}

              {item.luogo && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoIcon}>📍</Text>
                  <Text style={styles.infoText}>{item.luogo}</Text>
                </View>
              )}

              {item.ore_lavorate !== null && item.ore_lavorate !== undefined && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoIcon}>⏱️</Text>
                  <Text style={styles.infoText}>{item.ore_lavorate}h lavorate</Text>
                </View>
              )}

              {item.note && (
                <Text style={styles.noteText} numberOfLines={2}>
                  {item.note}
                </Text>
              )}

              <View style={styles.footer}>
                <Text style={styles.footerText}>
                  Collaboratore ID: {item.collaborator_id} • Progetto ID: {item.project_id}
                </Text>
              </View>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nessun evento in calendario</Text>
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
  dateSection: {
    marginBottom: spacing.sm,
  },
  dateText: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.semibold,
    color: colors.gray900,
  },
  timeText: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.primary,
    marginTop: spacing.xs,
  },
  tipoBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primaryLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
    marginBottom: spacing.sm,
  },
  tipoText: {
    fontSize: typography.sizes.xs,
    color: colors.white,
    fontWeight: typography.weights.semibold,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  infoIcon: {
    fontSize: typography.sizes.base,
    marginRight: spacing.xs,
  },
  infoText: {
    fontSize: typography.sizes.sm,
    color: colors.gray700,
  },
  noteText: {
    fontSize: typography.sizes.sm,
    color: colors.gray600,
    fontStyle: 'italic',
    marginTop: spacing.sm,
    lineHeight: typography.sizes.sm * typography.lineHeights.normal,
  },
  footer: {
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  footerText: {
    fontSize: typography.sizes.xs,
    color: colors.gray400,
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
