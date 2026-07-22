import React, { createContext, useContext, useEffect, useState } from 'react';
import { useColorScheme } from '@/hooks/use-color-scheme';

export type ThemeMode = 'system' | 'light' | 'dark';

interface AppSettings {
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  /** Resolved 'light' | 'dark' after applying the system scheme when themeMode is 'system'. */
  effectiveScheme: 'light' | 'dark';
  streamingEnabled: boolean;
  setStreamingEnabled: (enabled: boolean) => void;
  loaded: boolean;
}

const STORAGE_KEY = 'ringo:settings';

const SettingsContext = createContext<AppSettings | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [themeMode, setThemeModeState] = useState<ThemeMode>('system');
  const [streamingEnabled, setStreamingEnabledState] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.themeMode) setThemeModeState(parsed.themeMode);
        if (typeof parsed.streamingEnabled === 'boolean') setStreamingEnabledState(parsed.streamingEnabled);
      }
    } catch {
      // Corrupt/missing settings — fall back to defaults silently.
    } finally {
      setLoaded(true);
    }
  }, []);

  const persist = (next: Partial<{ themeMode: ThemeMode; streamingEnabled: boolean }>) => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ themeMode, streamingEnabled, ...next })
      );
    } catch {
      // Storage unavailable/full — settings just won't persist this time.
    }
  };

  const setThemeMode = (mode: ThemeMode) => { setThemeModeState(mode); persist({ themeMode: mode }); };
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
