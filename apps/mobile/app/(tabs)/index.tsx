/**
 * 홈 탭 — 공지 목록
 * FlashList 사용 (CLAUDE.md: FlatList 사용 금지)
 */
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useRouter } from 'expo-router';
import { FlashList } from '@shopify/flash-list';
import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { LoadingIndicator } from '@/components/ui/LoadingIndicator';
import { Colors } from '@/constants/Colors';
import { useNotices, type Notice } from '@/hooks/useNotices';
import { useProfile } from '@/hooks/useProfile';
import { useChildren } from '@/hooks/useChildren';
import { useAuthStore } from '@/store/authStore';

function NoticeCard({ notice }: { notice: Notice }) {
  const { t }  = useTranslation();
  const router = useRouter();
  const { languageCode, readNoticeIds } = useAuthStore();

  const translated = notice.translations?.[languageCode];
  const displaySummary = translated?.translation ?? notice.summary;
  const hasCulturalTip = Boolean(translated?.culturalTip);
  const isRead = readNoticeIds.includes(notice.noticeId);

  return (
    <TouchableOpacity
      onPress={() => router.push(`/notices/${notice.noticeId}`)}
      activeOpacity={0.8}
    >
      <Card style={[styles.card, !isRead && styles.cardUnread]}>
        <View style={styles.cardHeader}>
          <Badge label={t(`home.importance.${notice.importance}`)} variant={notice.importance} />
          <View style={styles.cardMeta}>
            {hasCulturalTip && <Text style={styles.tipIcon}>💡</Text>}
            {!isRead && <View style={styles.unreadDot} />}
            <Text style={styles.date}>
              {new Date(notice.publishedAt).toLocaleDateString()}
            </Text>
          </View>
        </View>
        <Text style={styles.cardTitle} numberOfLines={2}>{notice.title}</Text>
        <Text style={styles.cardSummary} numberOfLines={3}>{displaySummary}</Text>
      </Card>
    </TouchableOpacity>
  );
}

function GreetingHeader({ notices }: { notices: Notice[] }) {
  const { t } = useTranslation();
  const { readNoticeIds } = useAuthStore();
  const { data: profile } = useProfile();
  const { data: children } = useChildren();

  const unreadCount = notices.filter((n) => !readNoticeIds.includes(n.noticeId)).length;
  const firstName = profile?.email?.split('@')[0] ?? '';

  return (
    <View style={styles.greeting}>
      <Text style={styles.greetingText}>
        {t('home.greeting', { name: firstName })}
      </Text>
      {unreadCount > 0 && (
        <View style={styles.unreadBadge}>
          <Text style={styles.unreadBadgeText}>
            {t('home.unreadCount', { count: unreadCount })}
          </Text>
        </View>
      )}
      {children && children.length > 0 && (
        <View style={styles.childTags}>
          {children.map((child) => (
            <View key={child.childId} style={styles.childTag}>
              <Text style={styles.childTagText}>🎒 {child.name}</Text>
            </View>
          ))}
        </View>
      )}
      {children && children.length === 0 && (
        <Text style={styles.noChildText}>{t('home.noChild')}</Text>
      )}
    </View>
  );
}

export default function HomeScreen() {
  const { t } = useTranslation();
  const { languageCode } = useAuthStore();
  const { data: notices, isLoading, isError, refetch } = useNotices(languageCode);

  if (isLoading) return <LoadingIndicator fullScreen />;

  if (isError) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{t('common.error')}</Text>
        <TouchableOpacity onPress={() => refetch()} style={styles.retryBtn}>
          <Text style={styles.retryText}>{t('common.retry')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const noticeList = notices ?? [];

  return (
    <View style={styles.container}>
      <FlashList
        data={noticeList}
        keyExtractor={(item) => item.noticeId}
        renderItem={({ item }) => <NoticeCard notice={item} />}
        estimatedItemSize={150}
        contentContainerStyle={styles.list}
        ListHeaderComponent={<GreetingHeader notices={noticeList} />}
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>{t('home.noNotices')}</Text>
          </View>
        }
        onRefresh={refetch}
        refreshing={isLoading}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list:      { padding: 16 },

  greeting: {
    backgroundColor: Colors.primary,
    borderRadius:    16,
    padding:         16,
    marginBottom:    16,
    gap:             8,
  },
  greetingText: { fontSize: 20, fontWeight: '700', color: Colors.surface },
  unreadBadge: {
    alignSelf:       'flex-start',
    backgroundColor: Colors.accent,
    borderRadius:    12,
    paddingVertical:   4,
    paddingHorizontal: 10,
  },
  unreadBadgeText: { color: Colors.surface, fontSize: 13, fontWeight: '700' },
  childTags:   { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  childTag: {
    backgroundColor: Colors.primaryLight,
    borderRadius:    20,
    paddingVertical:   4,
    paddingHorizontal: 10,
  },
  childTagText: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
  noChildText:  { fontSize: 13, color: Colors.primaryLight },

  card:       { marginBottom: 12 },
  cardUnread: { borderLeftWidth: 3, borderLeftColor: Colors.accent },
  cardHeader: {
    flexDirection:  'row',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginBottom:   8,
  },
  cardMeta:    { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tipIcon:     { fontSize: 14 },
  unreadDot:   { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.accent },
  date:        { fontSize: 12, color: Colors.textSecondary },
  cardTitle:   { fontSize: 16, fontWeight: '700', color: Colors.textPrimary, marginBottom: 6 },
  cardSummary: { fontSize: 14, color: Colors.textSecondary, lineHeight: 20 },

  center:    { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyText: { fontSize: 16, color: Colors.textSecondary, textAlign: 'center' },
  errorText: { fontSize: 16, color: Colors.danger, marginBottom: 12 },
  retryBtn:  { padding: 12 },
  retryText: { color: Colors.primary, fontSize: 15, fontWeight: '600' },
});
