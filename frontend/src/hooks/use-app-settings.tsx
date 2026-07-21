import React, { createContext, useContext, useEffect, useState } from 'react';
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
  uiLanguage: Exclude<Language, 'auto'>;
  setUiLanguage: (lang: Exclude<Language, 'auto'>) => void;
  streamingEnabled: boolean;
  setStreamingEnabled: (enabled: boolean) => void;
  loaded: boolean;
}

const STORAGE_KEY = 'ringo:settings';

const SettingsContext = createContext<AppSettings | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [themeMode, setThemeModeState] = useState<ThemeMode>('system');
  const [defaultLanguage, setDefaultLanguageState] = useState<Language | 'auto'>('auto');
  const [uiLanguage, setUiLanguageState] = useState<Exclude<Language, 'auto'>>('en');
  const [streamingEnabled, setStreamingEnabledState] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.themeMode) setThemeModeState(parsed.themeMode);
        if (parsed.defaultLanguage) setDefaultLanguageState(parsed.defaultLanguage);
        if (parsed.uiLanguage) setUiLanguageState(parsed.uiLanguage);
        if (typeof parsed.streamingEnabled === 'boolean') setStreamingEnabledState(parsed.streamingEnabled);
      }
    } catch {
      // Corrupt/missing settings — fall back to defaults silently.
    } finally {
      setLoaded(true);
    }
  }, []);

  const persist = (next: Partial<{ themeMode: ThemeMode; defaultLanguage: Language | 'auto'; uiLanguage: Exclude<Language, 'auto'>; streamingEnabled: boolean }>) => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ themeMode, defaultLanguage, uiLanguage, streamingEnabled, ...next })
      );
    } catch {
      // Storage unavailable/full — settings just won't persist this time.
    }
  };

  const setThemeMode = (mode: ThemeMode) => { setThemeModeState(mode); persist({ themeMode: mode }); };
  const setDefaultLanguage = (lang: Language | 'auto') => { setDefaultLanguageState(lang); persist({ defaultLanguage: lang }); };
  const setUiLanguage = (lang: Exclude<Language, 'auto'>) => { setUiLanguageState(lang); persist({ uiLanguage: lang }); };
  const setStreamingEnabled = (enabled: boolean) => { setStreamingEnabledState(enabled); persist({ streamingEnabled: enabled }); };

  const systemScheme = useColorScheme();
  const effectiveScheme: 'light' | 'dark' =
    themeMode === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : themeMode;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', effectiveScheme);
  }, [effectiveScheme]);

  return (
    <SettingsContext.Provider
      value={{
        themeMode, setThemeMode, effectiveScheme,
        defaultLanguage, setDefaultLanguage,
        uiLanguage, setUiLanguage,
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
