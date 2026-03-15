import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Colors } from '@/constants/Colors';

type BadgeVariant = 'HIGH' | 'MEDIUM' | 'LOW' | 'default';

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
}

const VARIANT_COLORS: Record<BadgeVariant, { bg: string; text: string }> = {
  HIGH:    { bg: '#FADBD8', text: Colors.danger  },
  MEDIUM:  { bg: '#FDEBD0', text: Colors.warning },
  LOW:     { bg: '#D5F5E3', text: Colors.success },
  default: { bg: Colors.primaryLight, text: Colors.primary },
};

export function Badge({ label, variant = 'default' }: BadgeProps) {
  const { bg, text } = VARIANT_COLORS[variant];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.text, { color: text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical:   3,
    borderRadius:      6,
    alignSelf:         'flex-start',
  },
  text: {
    fontSize:   12,
    fontWeight: '600',
  },
});
