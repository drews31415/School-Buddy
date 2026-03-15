import React from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  TouchableOpacityProps,
  ViewStyle,
} from 'react-native';
import { Colors } from '@/constants/Colors';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

interface ButtonProps extends TouchableOpacityProps {
  title: string;
  variant?: Variant;
  loading?: boolean;
  fullWidth?: boolean;
}

export function Button({
  title,
  variant = 'primary',
  loading = false,
  fullWidth = false,
  disabled,
  style,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      activeOpacity={0.8}
      disabled={isDisabled}
      style={[
        styles.base,
        styles[variant],
        fullWidth && styles.fullWidth,
        isDisabled && styles.disabled,
        style as ViewStyle,
      ]}
      {...rest}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={variant === 'ghost' ? Colors.primary : Colors.surface}
        />
      ) : (
        <Text style={[styles.text, styles[`text_${variant}`]]}>{title}</Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight:     48,   // 44pt 접근성 기준 이상
    paddingHorizontal: 20,
    paddingVertical:   12,
    borderRadius:  10,
    alignItems:    'center',
    justifyContent: 'center',
  },
  fullWidth: { alignSelf: 'stretch' },
  disabled:  { opacity: 0.5 },

  primary:   { backgroundColor: Colors.primary },
  secondary: { backgroundColor: Colors.primaryLight, borderWidth: 1, borderColor: Colors.primary },
  danger:    { backgroundColor: Colors.danger },
  ghost:     { backgroundColor: 'transparent', borderWidth: 1, borderColor: Colors.border },

  text: { fontSize: 16, fontWeight: '600' },
  text_primary:   { color: Colors.surface },
  text_secondary: { color: Colors.primary },
  text_danger:    { color: Colors.surface },
  text_ghost:     { color: Colors.textPrimary },
});
