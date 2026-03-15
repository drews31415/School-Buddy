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
import { Link } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { Colors } from '@/constants/Colors';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';

export default function LoginScreen() {
  const { t }  = useTranslation();
  const { login } = useAuth();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleLogin() {
    if (!email.trim())    { setError(t('auth.emailRequired'));    return; }
    if (!password.trim()) { setError(t('auth.passwordRequired')); return; }

    setLoading(true);
    setError(null);
    try {
      // Cognito SRP 인증 → 실제 구현 시 amazon-cognito-identity-js 또는 Amplify 사용
      // 현재는 API Gateway 직접 호출 패턴 (백엔드 인증 프록시)
      const { data } = await api.post<{
        data: { userId: string; accessToken: string; refreshToken: string; languageCode: string };
      }>('/auth/register', { email, password, action: 'LOGIN' });

      await login(data.data);
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
        {/* 로고 영역 */}
        <View style={styles.logoArea}>
          <Text style={styles.logoIcon}>🏫</Text>
          <Text style={styles.appName}>School Buddy</Text>
          <Text style={styles.tagline}>다문화가정 학부모 AI 비서</Text>
        </View>

        {/* 폼 */}
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
            autoComplete="current-password"
            placeholder="••••••••"
            placeholderTextColor={Colors.disabled}
          />

          {error && <Text style={styles.error}>{error}</Text>}

          <Button
            title={t('auth.loginBtn')}
            onPress={handleLogin}
            loading={loading}
            fullWidth
            style={styles.submitBtn}
          />
        </View>

        {/* 하단 링크 */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>{t('auth.noAccount')} </Text>
          <Link href="/(auth)/register" style={styles.link}>
            {t('auth.registerBtn')}
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: {
    flexGrow:       1,
    justifyContent: 'center',
    padding:        24,
  },
  logoArea: { alignItems: 'center', marginBottom: 40 },
  logoIcon: { fontSize: 64, marginBottom: 8 },
  appName:  { fontSize: 28, fontWeight: '800', color: Colors.primary },
  tagline:  { fontSize: 14, color: Colors.textSecondary, marginTop: 4 },

  form:       { gap: 8 },
  label:      { fontSize: 14, fontWeight: '600', color: Colors.textPrimary, marginTop: 12 },
  input: {
    height:        52,
    borderWidth:   1,
    borderColor:   Colors.border,
    borderRadius:  10,
    paddingHorizontal: 14,
    fontSize:      16,
    backgroundColor: Colors.surface,
    color:         Colors.textPrimary,
  },
  error:     { color: Colors.danger, fontSize: 13, marginTop: 4 },
  submitBtn: { marginTop: 24 },

  footer:     { flexDirection: 'row', justifyContent: 'center', marginTop: 24 },
  footerText: { color: Colors.textSecondary, fontSize: 14 },
  link:       { color: Colors.primary, fontSize: 14, fontWeight: '600' },
});
