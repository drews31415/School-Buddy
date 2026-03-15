import { Stack } from 'expo-router';
import { Colors } from '@/constants/Colors';

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle:     { backgroundColor: Colors.primary },
        headerTintColor: Colors.surface,
        headerTitleStyle: { fontWeight: '700' },
        contentStyle:    { backgroundColor: Colors.background },
        headerBackVisible: true,
      }}
    >
      <Stack.Screen name="login"           options={{ headerShown: false }} />
      <Stack.Screen name="register"        options={{ headerShown: false }} />
      <Stack.Screen name="language-select" options={{ headerShown: false }} />
    </Stack>
  );
}
