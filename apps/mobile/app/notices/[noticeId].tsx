/**
 * 공지 상세 화면
 * expo-router 동적 세그먼트: /notices/[noticeId]
 */
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useLocalSearchParams, useNavigation, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { LoadingIndicator } from '@/components/ui/LoadingIndicator';
import { Colors } from '@/constants/Colors';
import { useNotice } from '@/hooks/useNotices';
import { useAuthStore } from '@/store/authStore';

export default function NoticeDetailScreen() {
  const { t }        = useTranslation();
  const router       = useRouter();
  const navigation   = useNavigation();
  const { noticeId } = useLocalSearchParams<{ noticeId: string }>();
  const { languageCode, markAsRead } = useAuthStore();

  const { data: notice, isLoading } = useNotice(noticeId);

  const [checkedItems, setCheckedItems] = useState<boolean[]>([]);
  const [showOriginal, setShowOriginal] = useState(false);

  // 헤더 타이틀 동적 설정 + 읽음 표시
  useEffect(() => {
    if (notice) {
      navigation.setOptions({ title: notice.title });
      markAsRead(notice.noticeId);
      const translated = notice.translations?.[languageCode];
      if (translated?.checklistItems) {
        setCheckedItems(new Array(translated.checklistItems.length).fill(false));
      }
    }
  }, [notice, navigation, languageCode, markAsRead]);

  function toggleCheck(index: number) {
    setCheckedItems((prev) => prev.map((v, i) => (i === index ? !v : v)));
  }

  if (isLoading) return <LoadingIndicator fullScreen />;
  if (!notice) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{t('common.error')}</Text>
      </View>
    );
  }

  const translated = notice.translations?.[languageCode];
  const doneCount  = checkedItems.filter(Boolean).length;
  const totalCount = checkedItems.length;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* 헤더 */}
      <View style={styles.header}>
        <Badge
          label={t(`home.importance.${notice.importance}`)}
          variant={notice.importance}
        />
        <Text style={styles.date}>
          {new Date(notice.publishedAt).toLocaleDateString()}
        </Text>
      </View>

      {translated && (
        <>
          {/* 번역 요약 */}
          <Card elevated style={styles.card}>
            <Text style={styles.sectionLabel}>{t('notice.summary')}</Text>
            <Text style={styles.bodyText}>{translated.translation}</Text>
          </Card>

          {/* 문화 팁 */}
          {translated.culturalTip ? (
            <Card style={[styles.card, styles.tipCard]}>
              <Text style={styles.sectionLabel}>💡 {t('notice.culturalTip')}</Text>
              <Text style={styles.bodyText}>{translated.culturalTip}</Text>
            </Card>
          ) : null}

          {/* 체크리스트 (interactive) */}
          {translated.checklistItems.length > 0 && (
            <Card style={styles.card}>
              <View style={styles.checklistHeader}>
                <Text style={styles.sectionLabel}>✅ {t('notice.checklist')}</Text>
                <Text style={styles.progressText}>
                  {t('notice.checklistProgress', { done: doneCount, total: totalCount })}
                </Text>
              </View>
              {translated.checklistItems.map((item, i) => (
                <TouchableOpacity
                  key={i}
                  style={styles.checkItem}
                  onPress={() => toggleCheck(i)}
                  activeOpacity={0.7}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: checkedItems[i] }}
                >
                  <View style={[styles.checkbox, checkedItems[i] && styles.checkboxChecked]}>
                    {checkedItems[i] && <Text style={styles.checkboxTick}>✓</Text>}
                  </View>
                  <Text style={[styles.checkItemText, checkedItems[i] && styles.checkItemDone]}>
                    {item}
                  </Text>
                </TouchableOpacity>
              ))}
            </Card>
          )}
        </>
      )}

      {/* 원문 토글 */}
      <Card style={styles.card}>
        <TouchableOpacity
          style={styles.originalToggle}
          onPress={() => setShowOriginal((v) => !v)}
          activeOpacity={0.7}
        >
          <Text style={styles.sectionLabel}>{t('notice.original')}</Text>
          <Text style={styles.toggleLink}>
            {showOriginal ? t('notice.hideOriginal') : t('notice.showOriginal')}
          </Text>
        </TouchableOpacity>
        {showOriginal && (
          <Text style={[styles.bodyText, styles.original]}>{notice.summary}</Text>
        )}
      </Card>

      {/* 더 물어보기 버튼 */}
      <TouchableOpacity
        style={styles.askMoreBtn}
        onPress={() => router.push({ pathname: '/(tabs)/chat', params: { noticeId } })}
        activeOpacity={0.8}
      >
        <Text style={styles.askMoreText}>💬 {t('notice.askMore')}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content:   { padding: 16, gap: 12, paddingBottom: 32 },
  center:    { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  date:      { fontSize: 13, color: Colors.textSecondary },
  card:      { gap: 8 },
  tipCard:   { backgroundColor: '#FFFDE7', borderColor: Colors.warning },
  sectionLabel: {
    fontSize:  12,
    fontWeight: '700',
    color:     Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  bodyText:  { fontSize: 15, color: Colors.textPrimary, lineHeight: 24 },
  original:  { color: Colors.textSecondary, fontSize: 14 },
  errorText: { color: Colors.danger, fontSize: 16 },

  checklistHeader: {
    flexDirection:  'row',
    justifyContent: 'space-between',
    alignItems:     'center',
  },
  progressText: { fontSize: 12, color: Colors.textSecondary },
  checkItem:  {
    flexDirection: 'row',
    alignItems:    'center',
    gap:           10,
    paddingVertical: 6,
  },
  checkbox: {
    width:       24,
    height:      24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: Colors.border,
    alignItems:  'center',
    justifyContent: 'center',
    backgroundColor: Colors.surface,
  },
  checkboxChecked: {
    backgroundColor: Colors.success,
    borderColor:     Colors.success,
  },
  checkboxTick:   { color: Colors.surface, fontSize: 14, fontWeight: '800' },
  checkItemText:  { flex: 1, fontSize: 14, color: Colors.textPrimary, lineHeight: 22 },
  checkItemDone:  { textDecorationLine: 'line-through', color: Colors.textSecondary },

  originalToggle: {
    flexDirection:  'row',
    justifyContent: 'space-between',
    alignItems:     'center',
  },
  toggleLink: { fontSize: 13, color: Colors.primary, fontWeight: '600' },

  askMoreBtn: {
    backgroundColor: Colors.primary,
    borderRadius:    12,
    paddingVertical: 15,
    alignItems:      'center',
    marginTop:       4,
  },
  askMoreText: { color: Colors.surface, fontSize: 16, fontWeight: '700' },
});
