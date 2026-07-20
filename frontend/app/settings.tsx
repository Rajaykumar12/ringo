import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';
import { useAppSettings, ThemeMode } from '@/hooks/use-app-settings';
import { LANGUAGES } from '@/components/language-selector';

const THEME_OPTIONS: { mode: ThemeMode; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { mode: 'system', label: 'System', icon: 'phone-portrait-outline' },
  { mode: 'light', label: 'Light', icon: 'sunny-outline' },
  { mode: 'dark', label: 'Dark', icon: 'moon-outline' },
];

export default function SettingsScreen() {
  const router = useRouter();
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const {
    themeMode, setThemeMode,
    defaultLanguage, setDefaultLanguage,
    streamingEnabled, setStreamingEnabled,
  } = useAppSettings();

  return (
    <SafeAreaView style={styles.container}>
      <View style={[styles.header, Shadows.card]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.closeBtn} accessibilityLabel="Close settings">
          <Ionicons name="close" size={20} color={Colors.textMuted} />
        </TouchableOpacity>
        <Text style={styles.title}>Settings</Text>
        <View style={styles.closeBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.sectionLabel}>Appearance</Text>
        <View style={styles.card}>
          <View style={styles.segmented}>
            {THEME_OPTIONS.map((opt) => {
              const selected = themeMode === opt.mode;
              return (
                <TouchableOpacity
                  key={opt.mode}
                  style={[styles.segment, selected && styles.segmentSelected]}
                  onPress={() => setThemeMode(opt.mode)}
                  accessibilityLabel={`Theme: ${opt.label}${selected ? ', selected' : ''}`}
                >
                  <Ionicons name={opt.icon} size={16} color={selected ? '#FFF' : Colors.textMuted} />
                  <Text style={[styles.segmentText, selected && styles.segmentTextSelected]}>{opt.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        <Text style={styles.sectionLabel}>Default response language</Text>
        <View style={styles.card}>
          {LANGUAGES.map((lang) => {
            const selected = defaultLanguage === lang.code;
            return (
              <TouchableOpacity
                key={lang.code}
                style={[styles.row, selected && styles.rowSelected]}
                onPress={() => setDefaultLanguage(lang.code)}
                accessibilityLabel={`${lang.name}${selected ? ', selected' : ''}`}
              >
                <Text style={styles.rowFlag}>{lang.flag}</Text>
                <View style={styles.rowText}>
                  <Text style={[styles.rowName, selected && styles.rowNameSelected]}>{lang.nativeName}</Text>
                  <Text style={styles.rowSub}>{lang.name}</Text>
                </View>
                {selected && <Ionicons name="checkmark" size={16} color={Colors.amber} />}
              </TouchableOpacity>
            );
          })}
        </View>

        <Text style={styles.sectionLabel}>Responses</Text>
        <View style={styles.card}>
          <View style={styles.switchRow}>
            <View style={styles.switchLabelWrap}>
              <Text style={styles.switchLabel}>Stream responses</Text>
              <Text style={styles.switchSub}>Show the AI&apos;s reply as it&apos;s generated, token by token.</Text>
            </View>
            <Switch
              value={streamingEnabled}
              onValueChange={setStreamingEnabled}
              trackColor={{ false: Colors.borderMid, true: Colors.amber }}
              thumbColor="#FFF"
            />
          </View>
        </View>
        <Text style={styles.sectionLabel}>Advanced</Text>
        <View style={styles.card}>
          <TouchableOpacity
            style={styles.row}
            onPress={() => router.push('/admin')}
            accessibilityLabel="Admin dashboard"
          >
            <Ionicons name="stats-chart-outline" size={18} color={Colors.textMuted} />
            <View style={styles.rowText}>
              <Text style={styles.rowName}>Admin dashboard</Text>
              <Text style={styles.rowSub}>RAG call volume, latency, ratings, eval scores</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={Colors.textFaint} />
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: Colors.surface,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: Radii.full,
    backgroundColor: Colors.surfaceWarm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: { fontSize: 17, fontWeight: '700', color: Colors.text },
  content: { padding: 16, gap: 8 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: 12,
    marginBottom: 6,
    marginLeft: 4,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    overflow: 'hidden',
    ...Shadows.card,
  },
  segmented: { flexDirection: 'row', padding: 6, gap: 6 },
  segment: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: Radii.sm,
  },
  segmentSelected: { backgroundColor: Colors.amber },
  segmentText: { fontSize: 13, fontWeight: '600', color: Colors.textMuted },
  segmentTextSelected: { color: '#FFF' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  rowSelected: { backgroundColor: Colors.amberLight },
  rowFlag: { fontSize: 20 },
  rowText: { flex: 1 },
  rowName: { fontSize: 15, fontWeight: '600', color: Colors.text },
  rowNameSelected: { color: Colors.amberDark },
  rowSub: { fontSize: 12, color: Colors.textMuted, marginTop: 1 },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
    gap: 12,
  },
  switchLabelWrap: { flex: 1 },
  switchLabel: { fontSize: 15, fontWeight: '600', color: Colors.text },
  switchSub: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
});
