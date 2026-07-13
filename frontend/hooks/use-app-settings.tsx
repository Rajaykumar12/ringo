import React, { createContext, useContext, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Language } from '@/components/language-selector';
import { useColorScheme } from '@/hooks/use-color-scheme';

export type ThemeMode = 'system' | 'light' | 'dark';

interface AppSettings {
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  /** Resolved 'light' | 'dark' after applying the system scheme when themeMode is 'system'. */
  effectiveScheme: 'light' | 'dark';
  defaultLanguage: Language | 'auto';
  setDefaultLanguage: (lang: Language | 'auto') => void;
  streamingEnabled: boolean;
  setStreamingEnabled: (enabled: boolean) => void;
  loaded: boolean;
}

const STORAGE_KEY = 'ringo:settings';

const SettingsContext = createContext<AppSettings | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [themeMode, setThemeModeState] = useState<ThemeMode>('system');
  const [defaultLanguage, setDefaultLanguageState] = useState<Language | 'auto'>('auto');
  const [streamingEnabled, setStreamingEnabledState] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed.themeMode) setThemeModeState(parsed.themeMode);
          if (parsed.defaultLanguage) setDefaultLanguageState(parsed.defaultLanguage);
          if (typeof parsed.streamingEnabled === 'boolean') setStreamingEnabledState(parsed.streamingEnabled);
        }
      } catch {
        // Corrupt/missing settings — fall back to defaults silently.
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const persist = (next: Partial<{ themeMode: ThemeMode; defaultLanguage: Language | 'auto'; streamingEnabled: boolean }>) => {
    AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ themeMode, defaultLanguage, streamingEnabled, ...next })
    ).catch(() => {});
  };

  const setThemeMode = (mode: ThemeMode) => { setThemeModeState(mode); persist({ themeMode: mode }); };
  const setDefaultLanguage = (lang: Language | 'auto') => { setDefaultLanguageState(lang); persist({ defaultLanguage: lang }); };
  const setStreamingEnabled = (enabled: boolean) => { setStreamingEnabledState(enabled); persist({ streamingEnabled: enabled }); };

  const systemScheme = useColorScheme();
  const effectiveScheme: 'light' | 'dark' =
    themeMode === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : themeMode;

  return (
    <SettingsContext.Provider
      value={{
        themeMode, setThemeMode, effectiveScheme,
        defaultLanguage, setDefaultLanguage,
        streamingEnabled, setStreamingEnabled,
        loaded,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useAppSettings(): AppSettings {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within a SettingsProvider');
  return ctx;
}
