export interface Notification {
  notificationId: string;
  userId: string;
  noticeId: string;
  sentAt: string;  // ISO 8601
  isRead: boolean;
}
