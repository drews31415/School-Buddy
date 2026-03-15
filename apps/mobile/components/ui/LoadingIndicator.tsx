import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { Colors } from '@/constants/Colors';
import { useTranslation } from 'react-i18next';

interface LoadingIndicatorProps {
  size?: 'small' | 'large';
  message?: string;
  fullScreen?: boolean;
}

export function LoadingIndicator({
  size = 'large',
  message,
  fullScreen = false,
}: LoadingIndicatorProps) {
  const { t } = useTranslation();

  return (
    <View style={[styles.container, fullScreen && styles.fullScreen]}>
      <ActivityIndicator size={size} color={Colors.primary} />
      {(message ?? t('common.loading')) ? (
        <Text style={styles.message}>{message ?? t('common.loading')}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems:     'center',
    justifyContent: 'center',
    padding:        24,
    gap:            12,
  },
  fullScreen: {
    flex:            1,
    backgroundColor: Colors.background,
  },
  message: {
    color:    Colors.textSecondary,
    fontSize: 14,
  },
});
