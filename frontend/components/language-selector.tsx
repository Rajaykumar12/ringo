import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  Platform,
} from 'react-native';

export type Language = 'en' | 'hi' | 'ta' | 'te' | 'auto';

interface LanguageSelectorProps {
  selectedLanguage: Language;
  onSelectLanguage: (language: Language) => void;
}

const LANGUAGES: { code: Language; name: string; nativeName: string }[] = [
  { code: 'auto', name: 'Auto-Detect', nativeName: '🌐 Auto' },
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिंदी' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు' },
];

export function LanguageSelector({
  selectedLanguage,
  onSelectLanguage,
}: LanguageSelectorProps) {
  const [visible, setVisible] = React.useState(false);

  const currentLanguage = LANGUAGES.find((l) => l.code === selectedLanguage);

  return (
    <>
      <TouchableOpacity
        style={styles.button}
        onPress={() => setVisible(true)}
      >
        <Text style={styles.buttonText}>
          {currentLanguage?.nativeName}
        </Text>
      </TouchableOpacity>

      <Modal
        visible={visible}
        transparent
        animationType="fade"
        onRequestClose={() => setVisible(false)}
      >
        <TouchableOpacity
          style={styles.overlay}
          activeOpacity={1}
          onPress={() => setVisible(false)}
        >
          <View style={styles.modal}>
            <Text style={styles.title}>Select Language</Text>
            {LANGUAGES.map((lang) => (
              <TouchableOpacity
                key={lang.code}
                style={[
                  styles.languageItem,
                  selectedLanguage === lang.code && styles.selected,
                ]}
                onPress={() => {
                  onSelectLanguage(lang.code);
                  setVisible(false);
                }}
              >
                <Text style={styles.languageName}>{lang.nativeName}</Text>
                <Text style={styles.languageSubname}>{lang.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: '#F0F0F0',
    borderRadius: 16,
  },
  buttonText: {
    fontSize: 14,
    fontWeight: '600',
  },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modal: {
    width: '80%',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.25,
        shadowRadius: 8,
      },
      android: {
        elevation: 5,
      },
    }),
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 16,
    textAlign: 'center',
  },
  languageItem: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
    backgroundColor: '#F8F8F8',
  },
  selected: {
    backgroundColor: '#007AFF',
  },
  languageName: {
    fontSize: 18,
    fontWeight: '600',
  },
  languageSubname: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
});
