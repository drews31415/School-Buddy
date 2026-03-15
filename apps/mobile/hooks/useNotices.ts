import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export interface Notice {
  noticeId:   string;
  schoolId:   string;
  title:      string;
  summary:    string;
  importance: 'HIGH' | 'MEDIUM' | 'LOW';
  publishedAt: string;
  translations?: Record<string, { translation: string; culturalTip: string; checklistItems: string[] }>;
}

interface NoticesResponse {
  data:  Notice[];
  meta: { nextCursor?: string; count: number };
}

export function useNotices(langCode: string) {
  return useQuery<Notice[]>({
    queryKey: ['notices', langCode],
    queryFn: async () => {
      const { data } = await api.get<NoticesResponse>('/notices', {
        params: { limit: 30 },
      });
      return data.data;
    },
    staleTime: 5 * 60 * 1000,   // 5분 캐시
    retry: 2,
  });
}

export function useNotice(noticeId: string) {
  return useQuery<Notice>({
    queryKey: ['notice', noticeId],
    queryFn: async () => {
      const { data } = await api.get<{ data: Notice }>(`/notices/${noticeId}`);
      return data.data;
    },
    staleTime: 10 * 60 * 1000,
  });
}
