import { Platform } from 'react-native';

export const Colors = {
  // Backgrounds
  bg:          '#FAFAF8',
  surface:     '#FFFFFF',
  surfaceWarm: '#F5F0E8',
  surfaceMid:  '#EDE8DF',

  // Amber — primary actions
  amber:       '#D97706',
  amberDark:   '#B45309',
  amberLight:  '#FEF3C7',

  // Teal — secondary actions
  teal:        '#0D9488',
  tealLight:   '#CCFBF1',

  // Text
  text:        '#1C1917',
  textMuted:   '#78716C',
  textFaint:   '#A8A29E',

  // Borders
  border:      '#E7E5E4',
  borderMid:   '#D6D3D1',

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
      shadowColor: '#1C1917',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.06,
      shadowRadius: 8,
    },
    default: { elevation: 2 },
  }),
  float: Platform.select({
    ios: {
      shadowColor: '#1C1917',
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
