/**
 * 루트 레이아웃
 * - QueryClient Provider
 * - i18n 초기화
 * - 웹 환경: 자동으로 requestWebPushPermission 호출
 * - 인증 상태에 따른 초기 라우팅
 */
import '../i18n';  // i18n 최초 초기화 (사이드 이펙트)

import { useEffect } from 'react';
import { Platform } from 'react-native';
import { Stack, useRouter, useSegments } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';

import { useAuthStore } from '@/store/authStore';
import { storeToken } from '@/lib/api';
import { Colors } from '@/constants/Colors';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry:           2,
      staleTime:       5 * 60 * 1000,
      gcTime:          30 * 60 * 1000,
    },
  },
});

// ── 인증 가드 ─────────────────────────────────────────────────
function AuthGate() {
  const segments       = useSegments();
  const router         = useRouter();
  const { userId, isLoading, setLoading, setAuth, setLanguageCode } = useAuthStore();

  // 저장된 토큰 복원
  useEffect(() => {
    (async () => {
      try {
        const { getStoredToken } = await import('@/lib/api').then(m => ({ getStoredToken: m.storeToken }));
        // 실제로는 lib/api에서 getStoredToken을 export해야 하지만
        // 여기서는 간단히 localStorage/SecureStore 직접 접근
        let accessToken: string | null = null;
        let languageCode = 'vi';

        if (Platform.OS === 'web') {
          accessToken  = window.localStorage.getItem('accessToken');
          languageCode = window.localStorage.getItem('languageCode') ?? 'vi';
        } else {
          const SecureStore = await import('expo-secure-store');
          accessToken  = await SecureStore.getItemAsync('accessToken');
          languageCode = (await SecureStore.getItemAsync('languageCode')) ?? 'vi';
        }

        if (accessToken) {
          // userId를 JWT payload에서 파싱
          const payload = JSON.parse(
            atob(accessToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
          );
          setAuth({ userId: payload.sub, accessToken, refreshToken: '' });
          setLanguageCode(languageCode);
          const { default: i18n } = await import('@/i18n');
          await i18n.changeLanguage(languageCode);
        }
      } catch {
        // 토큰 없음 or 파싱 실패 — 로그인으로 이동
      } finally {
        setLoading(false);
      }
    })();
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // 라우팅 가드
  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';
    if (!userId && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (userId && inAuthGroup) {
      router.replace('/(tabs)');
    }
  }, [userId, isLoading, segments, router]);

  // 웹 환경: 인증 후 자동 웹 푸시 권한 요청
  useEffect(() => {
    if (!userId || Platform.OS !== 'web') return;
    import('@/utils/webPush').then(({ requestWebPushPermission }) => {
      requestWebPushPermission().catch(console.warn);
    });
  }, [userId]);

  return null;
}

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
      <StatusBar style="light" backgroundColor={Colors.primary} />
      <Stack
        screenOptions={{
          headerStyle:      { backgroundColor: Colors.primary },
          headerTintColor:  Colors.surface,
          headerTitleStyle: { fontWeight: '700', fontSize: 18 },
          contentStyle:     { backgroundColor: Colors.background },
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen name="(auth)"    options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)"    options={{ headerShown: false }} />
        <Stack.Screen
          name="notices/[noticeId]"
          options={{ title: '' }}
        />
      </Stack>
    </QueryClientProvider>
  );
}
