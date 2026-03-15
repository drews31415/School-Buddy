import { useCallback } from 'react';
import { useRouter } from 'expo-router';
import { useAuthStore } from '@/store/authStore';
import { removeToken, storeToken } from '@/lib/api';
import i18n from '@/i18n';

export function useAuth() {
  const router = useRouter();
  const { userId, accessToken, languageCode, setAuth, setLanguageCode, clearAuth } =
    useAuthStore();

  const isAuthenticated = Boolean(userId && accessToken);

  const login = useCallback(
    async (params: {
      userId:       string;
      accessToken:  string;
      refreshToken: string;
      languageCode: string;
    }) => {
      await storeToken('accessToken',  params.accessToken);
      await storeToken('refreshToken', params.refreshToken);
      setAuth({
        userId:       params.userId,
        accessToken:  params.accessToken,
        refreshToken: params.refreshToken,
      });
      setLanguageCode(params.languageCode);
      await i18n.changeLanguage(params.languageCode);
    },
    [setAuth, setLanguageCode]
  );

  const logout = useCallback(async () => {
    await removeToken('accessToken');
    await removeToken('refreshToken');
    clearAuth();
    router.replace('/(auth)/login');
  }, [clearAuth, router]);

  const changeLanguage = useCallback(
    async (code: string) => {
      setLanguageCode(code);
      await i18n.changeLanguage(code);
    },
    [setLanguageCode]
  );

  return { isAuthenticated, userId, languageCode, login, logout, changeLanguage };
}
