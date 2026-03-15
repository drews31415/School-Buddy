import { Alert, ScrollView, StyleSheet, Switch, Text, TouchableOpacity, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { Colors } from '@/constants/Colors';
import { useAuth } from '@/hooks/useAuth';

const LANGUAGE_LABELS: Record<string, string> = {
  vi:    '🇻🇳 Tiếng Việt',
  'zh-CN': '🇨🇳 简体中文',
  'zh-TW': '🇹🇼 繁體中文',
  en:    '🇺🇸 English',
  ja:    '🇯🇵 日本語',
  th:    '🇹🇭 ภาษาไทย',
  mn:    '🇲🇳 Монгол',
  tl:    '🇵🇭 Filipino',
};

function SettingsRow({
  icon, label, value, onPress, isSwitch, switchValue, onSwitchChange,
}: {
  icon:    string;
  label:   string;
  value?:  string;
  onPress?:() => void;
  isSwitch?: boolean;
  switchValue?: boolean;
  onSwitchChange?: (v: boolean) => void;
}) {
  return (
    <TouchableOpacity
      style={styles.row}
      onPress={onPress}
      disabled={isSwitch}
      activeOpacity={0.7}
    >
      <Text style={styles.rowIcon}>{icon}</Text>
      <View style={styles.rowBody}>
        <Text style={styles.rowLabel}>{label}</Text>
        {value && <Text style={styles.rowValue}>{value}</Text>}
      </View>
      {isSwitch ? (
        <Switch
          value={switchValue}
          onValueChange={onSwitchChange}
          trackColor={{ true: Colors.primary }}
          thumbColor={Colors.surface}
        />
      ) : (
        <Text style={styles.chevron}>›</Text>
      )}
    </TouchableOpacity>
  );
}

export default function SettingsScreen() {
  const { t } = useTranslation();
  const { languageCode, logout } = useAuth();

  function handleLogout() {
    Alert.alert(
      t('settings.logout'),
      t('settings.logoutConfirm'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        { text: t('settings.logout'), style: 'destructive', onPress: logout },
      ]
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.section}>
        <SettingsRow
          icon="🌐"
          label={t('settings.language')}
          value={LANGUAGE_LABELS[languageCode] ?? languageCode}
          onPress={() => { /* TODO: 언어 변경 모달 */ }}
        />
        <SettingsRow
          icon="🔔"
          label={t('settings.notifications')}
          isSwitch
          switchValue={true}
          onSwitchChange={() => {}}
        />
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>{t('settings.logout')}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content:   { padding: 16, gap: 24 },
  section:   { backgroundColor: Colors.surface, borderRadius: 12, borderWidth: 1, borderColor: Colors.border, overflow: 'hidden' },
  row: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, gap: 12,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  rowIcon:  { fontSize: 22 },
  rowBody:  { flex: 1 },
  rowLabel: { fontSize: 16, color: Colors.textPrimary, fontWeight: '500' },
  rowValue: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  chevron:  { fontSize: 22, color: Colors.disabled },
  logoutBtn:{ alignItems: 'center', padding: 16, backgroundColor: Colors.surface, borderRadius: 12, borderWidth: 1, borderColor: Colors.danger },
  logoutText:{ fontSize: 16, fontWeight: '600', color: Colors.danger },
});
