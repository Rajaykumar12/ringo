import { Platform } from 'react-native';

export const Colors = {
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
