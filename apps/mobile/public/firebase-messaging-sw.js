/**
 * Firebase Cloud Messaging Service Worker
 * 경로: /public/firebase-messaging-sw.js → 빌드 후 /firebase-messaging-sw.js
 *
 * 초기화 방식: 앱에서 postMessage({ type: 'FIREBASE_CONFIG', config: {...} }) 로 설정값 주입
 * (process.env를 SW에서 직접 읽을 수 없으므로 메시지 방식 사용)
 */

importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-messaging-compat.js');

let messaging = null;

// ── Firebase 초기화 (앱에서 config postMessage 수신 후) ────────
self.addEventListener('message', (event) => {
  if (!event.data || event.data.type !== 'FIREBASE_CONFIG') return;

  const config = event.data.config;
  if (!config || !config.apiKey) return;

  try {
    if (!firebase.apps.length) {
      firebase.initializeApp(config);
    }
    messaging = firebase.messaging();

    // ── 백그라운드 메시지 수신 ─────────────────────────────
    messaging.onBackgroundMessage((payload) => {
      const { notification, data } = payload;

      const title = notification?.title ?? '학교 공지';
      const body  = notification?.body  ?? '새 공지가 도착했습니다.';
      const noticeId = data?.noticeId;

      self.registration.showNotification(title, {
        body,
        icon:  '/assets/icon.png',
        badge: '/assets/notification-icon.png',
        tag:   noticeId ?? 'school-buddy-notification',
        data:  { noticeId, url: noticeId ? `/notices/${noticeId}` : '/' },
        actions: [
          { action: 'view',    title: '보기' },
          { action: 'dismiss', title: '닫기' },
        ],
      });
    });
  } catch (err) {
    console.error('[SW] Firebase 초기화 실패:', err);
  }
});

// ── 알림 클릭 → 해당 공지 상세 페이지 이동 ────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = event.notification.data?.url ?? '/';

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((windowClients) => {
        // 이미 열린 탭이 있으면 포커스 후 이동
        for (const client of windowClients) {
          if ('focus' in client) {
            client.focus();
            client.navigate(targetUrl);
            return;
          }
        }
        // 열린 탭 없으면 새 탭 열기
        return clients.openWindow(targetUrl);
      })
  );
});

// ── SW 설치 & 활성화 ────────────────────────────────────────────
self.addEventListener('install',  () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});
