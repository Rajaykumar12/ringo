import en from '@/locales/en.json';
import hi from '@/locales/hi.json';
import ta from '@/locales/ta.json';
import te from '@/locales/te.json';
import { useAppSettings } from '@/hooks/use-app-settings';

type Dictionary = typeof en;
const DICTIONARIES: Record<string, Dictionary> = { en, hi, ta, te };

function resolveKey(dict: Dictionary, key: string): string | undefined {
  return key.split('.').reduce<any>((node, segment) => node?.[segment], dict);
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) =>
    name in vars ? String(vars[name]) : match
  );
}

export function useTranslation() {
  const { uiLanguage } = useAppSettings();

  const t = (key: string, vars?: Record<string, string | number>): string => {
    const dict = DICTIONARIES[uiLanguage] ?? en;
    const template = resolveKey(dict, key) ?? resolveKey(en, key) ?? key;
    return interpolate(template, vars);
  };

  return { t };
}
