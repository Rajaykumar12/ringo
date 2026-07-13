import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';

export type Language = 'en' | 'hi' | 'ta' | 'te' | 'auto';

interface LanguageSelectorProps {
  selectedLanguage: Language;
  onSelectLanguage: (language: Language) => void;
}

export const LANGUAGES: { code: Language; name: string; nativeName: string; flag: string }[] = [
  { code: 'auto', name: 'Auto-Detect', nativeName: 'Auto',   flag: '🌐' },
  { code: 'en',   name: 'English',     nativeName: 'English', flag: '🇬🇧' },
  { code: 'hi',   name: 'Hindi',       nativeName: 'हिंदी',   flag: '🇮🇳' },
  { code: 'ta',   name: 'Tamil',       nativeName: 'தமிழ்',   flag: '🇮🇳' },
  { code: 'te',   name: 'Telugu',      nativeName: 'తెలుగు',  flag: '🇮🇳' },
];

export function LanguageSelector({ selectedLanguage, onSelectLanguage }: LanguageSelectorProps) {
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const [visible, setVisible] = React.useState(false);
  const current = LANGUAGES.find((l) => l.code === selectedLanguage);

  return (
    <>
      <TouchableOpacity
        style={styles.button}
        onPress={() => setVisible(true)}
        accessibilityLabel={`Language: ${current?.name}. Tap to change`}
      >
        <Text style={styles.buttonFlag}>{current?.flag}</Text>
        <Text style={styles.buttonText}>{current?.nativeName}</Text>
        <Ionicons name="chevron-down" size={12} color={Colors.textMuted} />
      </TouchableOpacity>

      <Modal visible={visible} transparent animationType="fade" onRequestClose={() => setVisible(false)}>
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setVisible(false)}>
          <View style={[styles.modal, Shadows.float]}>
            <Text style={styles.title}>Language</Text>
            {LANGUAGES.map((lang) => {
              const isSelected = selectedLanguage === lang.code;
              return (
                <TouchableOpacity
                  key={lang.code}
                  style={[styles.row, isSelected && styles.rowSelected]}
                  onPress={() => { onSelectLanguage(lang.code); setVisible(false); }}
                  accessibilityLabel={`${lang.name}${isSelected ? ', selected' : ''}`}
                >
                  <Text style={styles.rowFlag}>{lang.flag}</Text>
                  <View style={styles.rowText}>
                    <Text style={[styles.rowName, isSelected && styles.rowNameSelected]}>
                      {lang.nativeName}
                    </Text>
                    <Text style={styles.rowSub}>{lang.name}</Text>
                  </View>
                  {isSelected && (
                    <Ionicons name="checkmark" size={16} color={Colors.amber} />
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: Colors.surfaceWarm,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radii.full,
    paddingHorizontal: 11,
    paddingVertical: 6,
  },
  buttonFlag: { fontSize: 14 },
  buttonText: { fontSize: 13, fontWeight: '600', color: Colors.text },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(17,24,39,0.45)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modal: {
    width: '82%',
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    padding: 18,
    gap: 6,
    ...Platform.select({ android: { elevation: 6 } }),
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.text,
    textAlign: 'center',
    marginBottom: 6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: Colors.bg,
    borderRadius: Radii.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderLeftWidth: 3,
    borderLeftColor: 'transparent',
  },
  rowSelected: {
    backgroundColor: Colors.amberLight,
    borderLeftColor: Colors.amber,
  },
  rowFlag: { fontSize: 20 },
  rowText: { flex: 1 },
  rowName: { fontSize: 16, fontWeight: '600', color: Colors.text },
  rowNameSelected: { color: Colors.amberDark },
  rowSub: { fontSize: 12, color: Colors.textMuted, marginTop: 1 },
});
