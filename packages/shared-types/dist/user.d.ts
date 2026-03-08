import { LanguageCode } from "./enums";
export interface User {
    userId: string;
    languageCode: LanguageCode;
    children: Child[];
    notificationSettings: NotificationSettings;
    fcmToken: string;
    createdAt: string;
}
export interface Child {
    childId: string;
    name: string;
    schoolId: string;
    grade: number;
    className: string;
}
export interface NotificationSettings {
    enabled: boolean;
    /** 알림 허용 시간대 시작 (예: "08:00") */
    quietHoursStart?: string;
    /** 알림 허용 시간대 종료 (예: "22:00") */
    quietHoursEnd?: string;
    importanceThreshold: "LOW" | "MEDIUM" | "HIGH";
}
//# sourceMappingURL=user.d.ts.map