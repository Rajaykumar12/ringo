import { Platform } from 'react-native';
import { useAppSettings } from '@/hooks/use-app-settings';

export const LightColors = {
  // Backgrounds
  bg:          '#F9F9F8',
  surface:     '#FFFFFF',
  surfaceWarm: '#F3F4F6',
  surfaceMid:  '#E5E7EB',

  // Dark gray — primary actions
  amber:       '#4B5563',
  amberDark:   '#374151',
  amberLight:  '#E5E7EB',

  // Mid gray — secondary actions
  teal:        '#6B7280',
  tealLight:   '#F3F4F6',

  // Text
  text:        '#111827',
  textMuted:   '#6B7280',
  textFaint:   '#9CA3AF',

  // Borders
  border:      '#E5E7EB',
  borderMid:   '#D1D5DB',

  // Status
  error:       '#DC2626',
  errorLight:  '#FEE2E2',
  success:     '#16A34A',
};

export const DarkColors: typeof LightColors = {
  // Backgrounds
  bg:          '#0E1116',
  surface:     '#181C23',
  surfaceWarm: '#20252D',
  surfaceMid:  '#2A303A',

  // Light gray — primary actions (inverted for dark)
  amber:       '#9CA3AF',
  amberDark:   '#D1D5DB',
  amberLight:  '#2A303A',

  // Mid gray — secondary actions
  teal:        '#9CA3AF',
  tealLight:   '#20252D',

  // Text
  text:        '#F3F4F6',
  textMuted:   '#9CA3AF',
  textFaint:   '#6B7280',

  // Borders
  border:      '#2A303A',
  borderMid:   '#3A414D',

  // Status
  error:       '#F87171',
  errorLight:  '#3F1D1D',
  success:     '#4ADE80',
};

/** Default/light palette — for any call site that hasn't switched to useThemeColors() yet. */
export const Colors = LightColors;

/** Returns the color palette matching the user's theme setting (system/light/dark). */
export function useThemeColors(): typeof LightColors {
  const { effectiveScheme } = useAppSettings();
  return effectiveScheme === 'dark' ? DarkColors : LightColors;
}

export const Radii = {
  sm:   8,
  md:   14,
  lg:   20,
  xl:   28,
  full: 9999,
};

export const Shadows = {
  card: Platform.select({
    ios: {
      shadowColor: '#111827',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.06,
      shadowRadius: 8,
    },
    default: { elevation: 2 },
  }),
  float: Platform.select({
    ios: {
      shadowColor: '#111827',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.10,
      shadowRadius: 16,
    },
    default: { elevation: 6 },
  }),
};

export const Fonts = Platform.select({
  ios: {
    sans: 'system-ui',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    mono: "SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace",
  },
});
