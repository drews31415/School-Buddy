/**
 * axios 인스턴스 — Cognito JWT 자동 첨부 인터셉터 포함
 *
 * 토큰 저장:
 *   네이티브 → expo-secure-store
 *   웹       → localStorage (SecureStore API 미지원)
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { Platform } from 'react-native';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? '';

// ── 토큰 스토리지 추상화 ─────────────────────────────────────
async function getStoredToken(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    return typeof window !== 'undefined'
      ? window.localStorage.getItem(key)
      : null;
  }
  // 네이티브: expo-secure-store (동적 import — 웹 번들에서 제외)
  const SecureStore = await import('expo-secure-store');
  return SecureStore.getItemAsync(key);
}

export async function storeToken(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') {
    window.localStorage.setItem(key, value);
    return;
  }
  const SecureStore = await import('expo-secure-store');
  await SecureStore.setItemAsync(key, value);
}

export async function removeToken(key: string): Promise<void> {
  if (Platform.OS === 'web') {
    window.localStorage.removeItem(key);
    return;
  }
  const SecureStore = await import('expo-secure-store');
  await SecureStore.deleteItemAsync(key);
}

// ── axios 인스턴스 ────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// 요청 인터셉터 — Authorization 헤더 자동 첨부
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await getStoredToken('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터 — 401 시 토큰 삭제 후 로그인 화면 이동
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await removeToken('accessToken');
      await removeToken('refreshToken');
      // authStore.clearAuth()는 훅에서 처리 (axios는 React 컨텍스트 밖)
    }
    return Promise.reject(error);
  }
);

export default api;
