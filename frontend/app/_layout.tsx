import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import 'react-native-reanimated';
import React, { Component, ReactNode } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { Radii, useThemeColors } from '@/constants/theme';
import { SettingsProvider, useAppSettings } from '@/hooks/use-app-settings';
import { ConversationsProvider } from '@/hooks/use-conversations';
import { NetworkStatusProvider } from '@/hooks/use-network-status';
import { useTranslation } from '@/hooks/use-translation';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

type ErrorBoundaryProps = {
  children: ReactNode;
  colors: ReturnType<typeof useThemeColors>;
  t: (key: string) => string;
};

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Uncaught rendering error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      const styles = createStyles(this.props.colors);
      const { t } = this.props;
      return (
        <View style={styles.container}>
          <View style={styles.iconWrap}>
            <Ionicons name="alert-circle-outline" size={32} color={this.props.colors.amber} />
          </View>
          <Text style={styles.title}>{t('errorBoundary.title')}</Text>
          <Text style={styles.message}>{t('errorBoundary.message')}</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => this.setState({ hasError: false, error: null })}
            accessibilityLabel={t('errorBoundary.tryAgain')}
            accessibilityRole="button"
          >
            <Text style={styles.buttonText}>{t('errorBoundary.tryAgain')}</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}

export default function RootLayout() {
  return (
    <SettingsProvider>
      <NetworkStatusProvider>
        <ConversationsProvider>
          <RootLayoutInner />
        </ConversationsProvider>
      </NetworkStatusProvider>
    </SettingsProvider>
  );
}

function RootLayoutInner() {
  const { effectiveScheme } = useAppSettings();
  const colors = useThemeColors();
  const { t } = useTranslation();

  return (
    <ErrorBoundary colors={colors} t={t}>
      <ThemeProvider value={effectiveScheme === 'dark' ? DarkTheme : DefaultTheme}>
        <Stack>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="settings" options={{ headerShown: false, presentation: 'modal' }} />
        </Stack>
        <StatusBar style={effectiveScheme === 'dark' ? 'light' : 'dark'} backgroundColor={colors.bg} />
      </ThemeProvider>
    </ErrorBoundary>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32, backgroundColor: Colors.bg },
  iconWrap: {
    width: 72,
    height: 72,
    borderRadius: Radii.xl,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: { fontSize: 20, fontWeight: '700', color: Colors.text, marginBottom: 8, textAlign: 'center' },
  message: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', marginBottom: 28, lineHeight: 20 },
  button: {
    backgroundColor: Colors.amber,
    paddingHorizontal: 28,
    paddingVertical: 13,
    borderRadius: Radii.md,
  },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
