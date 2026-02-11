import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useItem, useUpdateItem } from '../../../src/hooks/useItems';
import {
  Button,
  Input,
  LoadingSpinner,
  EmptyState,
} from '../../../src/components';
import { colors, spacing, typography } from '../../../src/styles/tokens';
import type { Item } from '../../../src/types/api';

// Form schema
const ItemFormSchema = z.object({
  nome: z.string().min(1, 'Nome obbligatorio'),
  descrizione: z.string().optional(),
  stato: z.string().optional(),
});

type ItemForm = z.infer<typeof ItemFormSchema>;

export default function ItemDetailScreen() {
  const params = useLocalSearchParams();
  const router = useRouter();
  const itemId = parseInt(params.id as string, 10);

  const { data: item, isLoading, error } = useItem(itemId);
  const updateMutation = useUpdateItem();

  const {
    control,
    handleSubmit,
    formState: { errors, touchedFields, isDirty },
  } = useForm<ItemForm>({
    resolver: zodResolver(ItemFormSchema),
    values: item
      ? {
          nome: item.nome,
          descrizione: item.descrizione || '',
          stato: item.stato || '',
        }
      : undefined,
  });

  const onSubmit = async (data: ItemForm) => {
    try {
      await updateMutation.mutateAsync({
        id: itemId,
        data,
      });
      router.back();
    } catch (error) {
      // Error is handled by mutation
    }
  };

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Caricamento dettagli..." />;
  }

  if (error || !item) {
    return (
      <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
        <View style={styles.container}>
          <EmptyState
            icon="alert-circle-outline"
            title="Errore"
            description={error?.message || 'Item non trovato'}
            actionLabel="Indietro"
            onAction={() => router.back()}
          />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <>
      <Stack.Screen
        options={{
          title: item.nome,
          headerBackTitle: 'Lista',
        }}
      />
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.container}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
          >
            <View style={styles.form}>
              <Controller
                control={control}
                name="nome"
                render={({ field: { onChange, onBlur, value } }) => (
                  <Input
                    label="Nome"
                    placeholder="Inserisci nome"
                    value={value}
                    onChangeText={onChange}
                    onBlur={onBlur}
                    error={errors.nome?.message}
                    touched={touchedFields.nome}
                    required
                  />
                )}
              />

              <Controller
                control={control}
                name="descrizione"
                render={({ field: { onChange, onBlur, value } }) => (
                  <Input
                    label="Descrizione"
                    placeholder="Inserisci descrizione (opzionale)"
                    value={value}
                    onChangeText={onChange}
                    onBlur={onBlur}
                    error={errors.descrizione?.message}
                    touched={touchedFields.descrizione}
                    multiline
                    numberOfLines={4}
                    style={styles.textArea}
                  />
                )}
              />

              <Controller
                control={control}
                name="stato"
                render={({ field: { onChange, onBlur, value } }) => (
                  <Input
                    label="Stato"
                    placeholder="Inserisci stato (opzionale)"
                    value={value}
                    onChangeText={onChange}
                    onBlur={onBlur}
                    error={errors.stato?.message}
                    touched={touchedFields.stato}
                  />
                )}
              />

              {item.data_creazione && (
                <View style={styles.metadata}>
                  <Text style={styles.metadataLabel}>Creato il:</Text>
                  <Text style={styles.metadataValue}>
                    {new Date(item.data_creazione).toLocaleString('it-IT')}
                  </Text>
                </View>
              )}

              {item.data_modifica && (
                <View style={styles.metadata}>
                  <Text style={styles.metadataLabel}>Modificato il:</Text>
                  <Text style={styles.metadataValue}>
                    {new Date(item.data_modifica).toLocaleString('it-IT')}
                  </Text>
                </View>
              )}
            </View>
          </ScrollView>

          <View style={styles.actions}>
            <Button
              title="Salva modifiche"
              onPress={handleSubmit(onSubmit)}
              loading={updateMutation.isPending}
              disabled={!isDirty || updateMutation.isPending}
              fullWidth
            />
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: spacing.lg,
  },
  form: {
    flex: 1,
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: 'top',
  },
  metadata: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  metadataLabel: {
    fontSize: typography.sizes.sm,
    color: colors.gray600,
  },
  metadataValue: {
    fontSize: typography.sizes.sm,
    color: colors.gray900,
    fontWeight: typography.weights.medium,
  },
  actions: {
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
    backgroundColor: colors.white,
  },
});
