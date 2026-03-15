/**
 * 웹 푸시 알림 유틸 (브라우저 전용)
 *
 * 네이티브(iOS/Android) 푸시는 expo-notifications가 담당하므로,
 * 이 파일의 함수들은 Platform.OS === 'web' 조건에서만 호출한다.
 *
 * 동작 흐름:
 *   1. requestWebPushPermission() — 브라우저 권한 요청
 *   2. getWebFcmToken()           — FCM VAPID 토큰 발급
 *   3. 토큰을 PUT /users/me (fcmTokenWeb 필드) 로 서버에 등록
 *   4. onForegroundMessage()      — 포그라운드 메시지 수신 처리
 */
import { Platform } from 'react-native';
import api from '@/lib/api';

const isWeb = Platform.OS === 'web';

// Firebase config (EXPO_PUBLIC_ 접두사 → 클라이언트에 노출 허용)
const firebaseConfig = {
  apiKey:            process.env.EXPO_PUBLIC_FIREBASE_API_KEY            ?? '',
  authDomain:        process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN        ?? '',
  projectId:         process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID         ?? '',
  storageBucket:     process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET     ?? '',
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? '',
  appId:             process.env.EXPO_PUBLIC_FIREBASE_APP_ID              ?? '',
};
const VAPID_KEY = process.env.EXPO_PUBLIC_FIREBASE_VAPID_KEY ?? '';

// 동적 import로 네이티브 번들에서 Firebase 제외
async function getMessaging() {
  if (!isWeb) return null;
  const { initializeApp, getApps } = await import('firebase/app');
  const { getMessaging: _getMessaging, isSupported } = await import('firebase/messaging');
  if (!(await isSupported())) return null;

  const app = getApps().length === 0
    ? initializeApp(firebaseConfig)
    : getApps()[0];

  return _getMessaging(app);
}

/**
 * 서비스 워커 등록 + Firebase 설정 메시지 전송
 * (firebase-messaging-sw.js에 config 주입)
 */
async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return null;

  try {
    const reg = await navigator.serviceWorker.register('/firebase-messaging-sw.js', {
      scope: '/',
    });
    // SW가 active 상태가 되면 Firebase config 전송
    const sw = reg.active ?? reg.installing ?? reg.waiting;
    sw?.postMessage({ type: 'FIREBASE_CONFIG', config: firebaseConfig });
    return reg;
  } catch (err) {
    console.warn('[webPush] SW 등록 실패:', err);
    return null;
  }
}

/**
 * 브라우저 푸시 권한 요청.
 * 권한 부여 시 FCM 토큰 발급 + 서버 등록까지 수행.
 */
export async function requestWebPushPermission(): Promise<boolean> {
  if (!isWeb || typeof Notification === 'undefined') return false;

  if (Notification.permission === 'denied') return false;

  const permission = Notification.permission === 'granted'
    ? 'granted'
    : await Notification.requestPermission();

  if (permission !== 'granted') return false;

  await registerServiceWorker();
  const token = await getWebFcmToken();
  if (token) await registerTokenToServer(token);

  return true;
}

/**
 * FCM 웹 푸시 토큰 발급.
 */
export async function getWebFcmToken(): Promise<string | null> {
  if (!isWeb || !VAPID_KEY) return null;
  try {
    const { getToken } = await import('firebase/messaging');
    const messaging = await getMessaging();
    if (!messaging) return null;
    const token = await getToken(messaging, { vapidKey: VAPID_KEY });
    return token || null;
  } catch (err) {
    console.warn('[webPush] FCM 토큰 발급 실패:', err);
    return null;
  }
}

/**
 * 발급된 FCM 웹 토큰을 서버에 등록 (PUT /users/me).
 */
async function registerTokenToServer(fcmTokenWeb: string): Promise<void> {
  try {
    await api.put('/users/me', { fcmTokenWeb });
  } catch (err) {
    console.warn('[webPush] 서버 토큰 등록 실패:', err);
  }
}

/**
 * 포그라운드 메시지 수신 처리.
 * 앱이 열린 상태에서 메시지 도착 시 in-app 토스트 표시용 콜백 등록.
 *
 * @param onMessage 메시지 수신 시 호출될 콜백
 * @returns 구독 해제 함수
 */
export async function onForegroundMessage(
  onMessage: (payload: { title?: string; body?: string; data?: Record<string, string> }) => void
): Promise<() => void> {
  if (!isWeb) return () => {};

  try {
    const { onMessage: _onMessage } = await import('firebase/messaging');
    const messaging = await getMessaging();
    if (!messaging) return () => {};

    const unsubscribe = _onMessage(messaging, (payload) => {
      onMessage({
        title: payload.notification?.title,
        body:  payload.notification?.body,
        data:  payload.data as Record<string, string>,
      });
    });
    return unsubscribe;
  } catch {
    return () => {};
  }
}
