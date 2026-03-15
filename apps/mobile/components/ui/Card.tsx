import React from 'react';
import { StyleProp, StyleSheet, View, ViewProps, ViewStyle } from 'react-native';
import { Colors } from '@/constants/Colors';

interface CardProps extends ViewProps {
  elevated?: boolean;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function Card({ elevated = false, children, style, ...rest }: CardProps) {
  return (
    <View
      style={[styles.card, elevated && styles.elevated, style]}
      {...rest}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius:    12,
    padding:         16,
    borderWidth:     1,
    borderColor:     Colors.border,
  },
  elevated: {
    borderWidth: 0,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,   // Android
  },
});
