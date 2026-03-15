import { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { Colors } from '@/constants/Colors';
import { useAuthStore } from '@/store/authStore';
import i18n from '@/i18n';

const LANGUAGES = [
  { code: 'vi',    flag: '🇻🇳', name: 'Tiếng Việt' },
  { code: 'zh-CN', flag: '🇨🇳', name: '简体中文' },
  { code: 'zh-TW', flag: '🇹🇼', name: '繁體中文' },
  { code: 'en',    flag: '🇺🇸', name: 'English' },
  { code: 'ja',    flag: '🇯🇵', name: '日本語' },
  { code: 'th',    flag: '🇹🇭', name: 'ภาษาไทย' },
  { code: 'mn',    flag: '🇲🇳', name: 'Монгол' },
  { code: 'tl',    flag: '🇵🇭', name: 'Filipino' },
] as const;

export default function LanguageSelectScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { languageCode, setLanguageCode } = useAuthStore();

  const [selected, setSelected] = useState<string>(languageCode);

  async function handleSelect(code: string) {
    setSelected(code);
    setLanguageCode(code);
    await i18n.changeLanguage(code);
  }

  function handleStart() {
    router.replace('/(auth)/login');
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{t('languageSelect.title')}</Text>
        <Text style={styles.subtitle}>{t('languageSelect.subtitle')}</Text>
      </View>

      <ScrollView contentContainerStyle={styles.grid}>
        {LANGUAGES.map((lang) => {
          const isSelected = selected === lang.code;
          return (
            <TouchableOpacity
              key={lang.code}
              style={[styles.tile, isSelected && styles.tileSelected]}
              onPress={() => handleSelect(lang.code)}
              activeOpacity={0.7}
              accessibilityState={{ selected: isSelected }}
            >
              <Text style={styles.flag}>{lang.flag}</Text>
              <Text style={[styles.langName, isSelected && styles.langNameSelected]}>
                {lang.name}
              </Text>
              {isSelected && <Text style={styles.checkmark}>✓</Text>}
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          style={styles.startBtn}
          onPress={handleStart}
          activeOpacity={0.8}
        >
          <Text style={styles.startBtnText}>{t('languageSelect.startBtn')}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    padding: 24,
    paddingTop: 48,
    backgroundColor: Colors.primary,
  },
  title:    { fontSize: 24, fontWeight: '800', color: Colors.surface },
  subtitle: { fontSize: 14, color: Colors.primaryLight, marginTop: 6 },

  grid: {
    flexDirection:  'row',
    flexWrap:       'wrap',
    padding:        12,
    gap:            10,
  },
  tile: {
    width:           '47%',
    alignItems:      'center',
    justifyContent:  'center',
    backgroundColor: Colors.surface,
    borderRadius:    16,
    paddingVertical: 20,
    paddingHorizontal: 12,
    borderWidth:     2,
    borderColor:     Colors.border,
    gap:             6,
  },
  tileSelected: {
    borderColor:     Colors.primary,
    backgroundColor: Colors.primaryLight,
  },
  flag:     { fontSize: 36 },
  langName: {
    fontSize:    15,
    fontWeight:  '700',
    color:       Colors.textPrimary,
    textAlign:   'center',
  },
  langNameSelected: { color: Colors.primary },
  checkmark: {
    position:   'absolute',
    top:        8,
    right:      10,
    fontSize:   16,
    color:      Colors.primary,
    fontWeight: '800',
  },

  footer: {
    padding:         16,
    paddingBottom:   32,
    backgroundColor: Colors.surface,
    borderTopWidth:  1,
    borderTopColor:  Colors.border,
  },
  startBtn: {
    backgroundColor: Colors.primary,
    borderRadius:    12,
    paddingVertical: 16,
    alignItems:      'center',
  },
  startBtnText: {
    color:      Colors.surface,
    fontSize:   17,
    fontWeight: '700',
  },
});
