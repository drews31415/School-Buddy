import { Tabs } from 'expo-router';
import { Platform, Text } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Colors } from '@/constants/Colors';

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: focused ? 26 : 22, opacity: focused ? 1 : 0.6 }}>
      {emoji}
    </Text>
  );
}

export default function TabLayout() {
  const { t } = useTranslation();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor:   Colors.primary,
        tabBarInactiveTintColor: Colors.textSecondary,
        tabBarStyle: {
          backgroundColor: Colors.surface,
          borderTopColor:  Colors.border,
          height:          Platform.OS === 'ios' ? 88 : 64,
          paddingBottom:   Platform.OS === 'ios' ? 28 : 8,
          paddingTop:      8,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        headerStyle:      { backgroundColor: Colors.primary },
        headerTintColor:  Colors.surface,
        headerTitleStyle: { fontWeight: '700', fontSize: 18 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title:         t('tabs.home'),
          tabBarIcon:    ({ focused }) => <TabIcon emoji="📋" focused={focused} />,
          headerTitle:   t('home.title'),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          title:       t('tabs.chat'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="💬" focused={focused} />,
          headerTitle: t('chat.title'),
        }}
      />
      <Tabs.Screen
        name="documents"
        options={{
          title:       t('tabs.documents'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="📄" focused={focused} />,
          headerTitle: t('documents.title'),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title:       t('tabs.settings'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="⚙️" focused={focused} />,
          headerTitle: t('settings.title'),
        }}
      />
    </Tabs>
  );
}
