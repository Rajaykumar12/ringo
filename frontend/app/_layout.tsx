import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import 'react-native-reanimated';
import React, { Component, ReactNode } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';

import { Radii, useThemeColors } from '@/constants/theme';
import { SettingsProvider, useAppSettings } from '@/hooks/use-app-settings';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<{ children: ReactNode; colors: ReturnType<typeof useThemeColors> }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode; colors: ReturnType<typeof useThemeColors> }) {
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
      return (
        <View style={styles.container}>
          <View style={styles.iconWrap}>
            <Text style={styles.icon}>⚠️</Text>
          </View>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>An unexpected error occurred. Please try again.</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => this.setState({ hasError: false, error: null })}
            accessibilityLabel="Try again"
          >
            <Text style={styles.buttonText}>Try Again</Text>
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
      <RootLayoutInner />
    </SettingsProvider>
  );
}

function RootLayoutInner() {
  const { effectiveScheme } = useAppSettings();
  const colors = useThemeColors();

  return (
    <ErrorBoundary colors={colors}>
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
  icon: { fontSize: 32 },
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
