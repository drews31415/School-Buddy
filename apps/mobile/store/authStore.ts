import { create } from 'zustand';

interface AuthState {
  userId:        string | null;
  accessToken:   string | null;
  refreshToken:  string | null;
  languageCode:  string;
  isLoading:     boolean;
  readNoticeIds: string[];   // 읽은 공지 ID 목록 (언읽음 배지 계산용)

  setAuth: (params: {
    userId:       string;
    accessToken:  string;
    refreshToken: string;
  }) => void;
  setLanguageCode: (code: string) => void;
  setLoading:      (loading: boolean) => void;
  clearAuth:       () => void;
  markAsRead:      (noticeId: string) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  userId:        null,
  accessToken:   null,
  refreshToken:  null,
  languageCode:  'vi',   // 기본 언어: 베트남어 (가장 많은 다문화가정)
  isLoading:     true,
  readNoticeIds: [],

  setAuth: ({ userId, accessToken, refreshToken }) =>
    set({ userId, accessToken, refreshToken }),

  setLanguageCode: (languageCode) =>
    set({ languageCode }),

  setLoading: (isLoading) =>
    set({ isLoading }),

  clearAuth: () =>
    set({ userId: null, accessToken: null, refreshToken: null, readNoticeIds: [] }),

  markAsRead: (noticeId) =>
    set((state) => ({
      readNoticeIds: state.readNoticeIds.includes(noticeId)
        ? state.readNoticeIds
        : [...state.readNoticeIds, noticeId],
    })),
}));
