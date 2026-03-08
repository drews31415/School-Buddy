import { ChatRole } from "./enums";
export interface ChatMessage {
    messageId: string;
    userId: string;
    sessionId: string;
    role: ChatRole;
    content: string;
    /** 공지와 연관된 대화인 경우 */
    noticeId?: string;
    createdAt: string;
}
//# sourceMappingURL=chat.d.ts.map