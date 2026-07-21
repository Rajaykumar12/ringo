import { useAppSettings } from '@/hooks/use-app-settings';

export const LightColors = {
  bg: '#F9F9F8',
  surface: '#FFFFFF',
  surfaceWarm: '#F3F4F6',
  surfaceMid: '#E5E7EB',

  amber: '#4B5563',
  amberDark: '#374151',
  amberLight: '#E5E7EB',

  teal: '#6B7280',
  tealLight: '#F3F4F6',

  text: '#111827',
  textMuted: '#6B7280',
  textFaint: '#9CA3AF',

  border: '#E5E7EB',
  borderMid: '#D1D5DB',

  error: '#DC2626',
  errorLight: '#FEE2E2',
  success: '#16A34A',
};

export const DarkColors: typeof LightColors = {
  bg: '#0E1116',
  surface: '#181C23',
  surfaceWarm: '#20252D',
  surfaceMid: '#2A303A',

  amber: '#9CA3AF',
  amberDark: '#D1D5DB',
  amberLight: '#2A303A',

  teal: '#9CA3AF',
  tealLight: '#20252D',

  text: '#F3F4F6',
  textMuted: '#9CA3AF',
  textFaint: '#6B7280',

  border: '#2A303A',
  borderMid: '#3A414D',

  error: '#F87171',
  errorLight: '#3F1D1D',
  success: '#4ADE80',
};

/** Default/light palette — for any call site outside a component (e.g. constants). */
export const Colors = LightColors;

/**
 * Returns the JS color palette matching the current effective theme, for spots
 * that need a raw color value (icon `color` props etc). CSS itself should prefer
 * the custom properties defined in `theme.css` instead of this hook.
 */
export function useThemeColors(): typeof LightColors {
  const { effectiveScheme } = useAppSettings();
  return effectiveScheme === 'dark' ? DarkColors : LightColors;
}

export const Radii = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
  full: 9999,
};
