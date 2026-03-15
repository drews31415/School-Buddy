import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export interface Child {
  childId:  string;
  name:     string;
  grade:    number;
  schoolId: string;
}

export function useChildren() {
  return useQuery<Child[]>({
    queryKey: ['children'],
    queryFn:  () => api.get<{ data: Child[] }>('/children').then((r) => r.data.data),
    staleTime: 10 * 60 * 1000,
  });
}
