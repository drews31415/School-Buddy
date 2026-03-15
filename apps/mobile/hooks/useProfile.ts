import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export interface UserProfile {
  userId:   string;
  email:    string;
  languageCode: string;
  notificationSettings: { pushEnabled: boolean; emailEnabled: boolean };
}

export function useProfile() {
  return useQuery<UserProfile>({
    queryKey: ['profile'],
    queryFn:  () => api.get<{ data: UserProfile }>('/users/me').then((r) => r.data.data),
    staleTime: 10 * 60 * 1000,
  });
}
