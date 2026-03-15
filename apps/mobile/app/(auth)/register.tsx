import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Link, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { Colors } from '@/constants/Colors';
import api from '@/lib/api';

export default function RegisterScreen() {
  const { t }   = useTranslation();
  const router  = useRouter();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleRegister() {
    if (!email.trim())    { setError(t('auth.emailRequired'));    return; }
    if (!password.trim()) { setError(t('auth.passwordRequired')); return; }

    setLoading(true);
    setError(null);
    try {
      await api.post('/auth/register', { email, password });
      // 회원가입 성공 → 언어 선택 화면으로 이동
      router.replace('/(auth)/language-select');
    } catch {
      setError(t('auth.loginFailed'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.title}>{t('auth.registerTitle')}</Text>
        </View>

        <View style={styles.form}>
          <Text style={styles.label}>{t('auth.email')}</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            placeholder="example@email.com"
            placeholderTextColor={Colors.disabled}
          />

          <Text style={styles.label}>{t('auth.password')}</Text>
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="new-password"
            placeholder="••••••••"
            placeholderTextColor={Colors.disabled}
          />

          {error && <Text style={styles.error}>{error}</Text>}

          <Button
            title={t('auth.registerBtn')}
            onPress={handleRegister}
            loading={loading}
            fullWidth
            style={styles.submitBtn}
          />
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>{t('auth.haveAccount')} </Text>
          <Link href="/(auth)/login" style={styles.link}>
            {t('auth.loginBtn')}
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  header:    { marginBottom: 32 },
  title:     { fontSize: 26, fontWeight: '800', color: Colors.primary },
  form:      { gap: 8 },
  label:     { fontSize: 14, fontWeight: '600', color: Colors.textPrimary, marginTop: 12 },
  input: {
    height: 52, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 10, paddingHorizontal: 14,
    fontSize: 16, backgroundColor: Colors.surface, color: Colors.textPrimary,
  },
  error:     { color: Colors.danger, fontSize: 13, marginTop: 4 },
  submitBtn: { marginTop: 24 },
  footer:    { flexDirection: 'row', justifyContent: 'center', marginTop: 24 },
  footerText:{ color: Colors.textSecondary, fontSize: 14 },
  link:      { color: Colors.primary, fontSize: 14, fontWeight: '600' },
});
