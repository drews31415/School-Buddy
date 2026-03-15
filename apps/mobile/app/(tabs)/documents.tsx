/**
 * 문서 탭 — 이미지/PDF 분석
 */
import { useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Colors } from '@/constants/Colors';
import { useAuthStore } from '@/store/authStore';
import api from '@/lib/api';

interface AnalysisResult {
  analysis: {
    summary:    string;
    materials:  string[];
    importance: 'HIGH' | 'MEDIUM' | 'LOW';
    schedule:   Array<{ date: string; description: string }>;
  };
  translated: {
    translation:    string;
    culturalTip:    string;
    checklistItems: string[];
  };
  fileType: string;
}

export default function DocumentsScreen() {
  const { t } = useTranslation();
  const { languageCode } = useAuthStore();
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const analyzeMutation = useMutation({
    mutationFn: async (params: { fileData: string; filename: string }) => {
      const { data } = await api.post<{ data: AnalysisResult }>('/documents/analyze', {
        fileData:     params.fileData,
        filename:     params.filename,
        languageCode,
      });
      return data.data;
    },
    onSuccess: setResult,
    onError: () => Alert.alert(t('common.error'), t('common.retry')),
  });

  async function pickImage(fromCamera: boolean) {
    const fn = fromCamera
      ? ImagePicker.launchCameraAsync
      : ImagePicker.launchImageLibraryAsync;

    const res = await fn({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      base64:     true,
      quality:    0.8,
    });

    if (res.canceled || !res.assets[0]) return;
    const asset = res.assets[0];
    if (!asset.base64) return;

    const ext      = asset.uri.split('.').pop()?.toLowerCase() ?? 'jpg';
    const filename = `document_${Date.now()}.${ext}`;
    analyzeMutation.mutate({ fileData: asset.base64, filename });
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.actions}>
        <Button
          title={`📷  ${t('documents.uploadPhoto')}`}
          onPress={() => pickImage(true)}
          loading={analyzeMutation.isPending}
          fullWidth
        />
        <Button
          title={`🖼️  ${t('documents.uploadFile')}`}
          variant="secondary"
          onPress={() => pickImage(false)}
          loading={analyzeMutation.isPending}
          fullWidth
        />
      </View>

      {analyzeMutation.isPending && (
        <Card style={styles.loadingCard}>
          <Text style={styles.loadingText}>🔍  {t('documents.analyzing')}</Text>
        </Card>
      )}

      {result && !analyzeMutation.isPending && (
        <View style={styles.results}>
          <View style={styles.resultHeader}>
            <Text style={styles.resultTitle}>{t('documents.result')}</Text>
            <Badge label={t(`home.importance.${result.analysis.importance}`)} variant={result.analysis.importance} />
          </View>

          {/* 번역 요약 */}
          <Card elevated style={styles.resultCard}>
            <Text style={styles.sectionLabel}>{t('notice.summary')}</Text>
            <Text style={styles.bodyText}>{result.translated.translation}</Text>
          </Card>

          {/* 문화 팁 */}
          {result.translated.culturalTip ? (
            <Card style={[styles.resultCard, styles.tipCard]}>
              <Text style={styles.sectionLabel}>💡 {t('notice.culturalTip')}</Text>
              <Text style={styles.bodyText}>{result.translated.culturalTip}</Text>
            </Card>
          ) : null}

          {/* 준비물 */}
          {result.translated.checklistItems.length > 0 && (
            <Card style={styles.resultCard}>
              <Text style={styles.sectionLabel}>✅ {t('notice.checklist')}</Text>
              {result.translated.checklistItems.map((item, i) => (
                <Text key={i} style={styles.listItem}>• {item}</Text>
              ))}
            </Card>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container:    { flex: 1, backgroundColor: Colors.background },
  content:      { padding: 16, gap: 16 },
  actions:      { gap: 10 },
  loadingCard:  { alignItems: 'center', padding: 24 },
  loadingText:  { fontSize: 16, color: Colors.textSecondary },
  results:      { gap: 12 },
  resultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  resultTitle:  { fontSize: 18, fontWeight: '700', color: Colors.textPrimary },
  resultCard:   { gap: 8 },
  tipCard:      { backgroundColor: '#FFFDE7', borderColor: Colors.warning },
  sectionLabel: { fontSize: 13, fontWeight: '700', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5 },
  bodyText:     { fontSize: 15, color: Colors.textPrimary, lineHeight: 22 },
  listItem:     { fontSize: 14, color: Colors.textPrimary, lineHeight: 22 },
});
