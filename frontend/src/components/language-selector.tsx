import React from 'react';
import { IoChevronDown, IoCheckmark } from 'react-icons/io5';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useTranslation } from '@/hooks/use-translation';
import styles from './language-selector.module.css';

export type Language = 'en' | 'hi' | 'ta' | 'te' | 'auto';

interface LanguageSelectorProps {
  selectedLanguage: Language;
  onSelectLanguage: (language: Language) => void;
}

export const LANGUAGES: { code: Language; name: string; nativeName: string; shortCode: string }[] = [
  { code: 'auto', name: 'Auto-Detect', nativeName: 'Auto', shortCode: 'AUTO' },
  { code: 'en', name: 'English', nativeName: 'English', shortCode: 'EN' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिंदी', shortCode: 'HI' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', shortCode: 'TA' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు', shortCode: 'TE' },
];

export function LanguageSelector({ selectedLanguage, onSelectLanguage }: LanguageSelectorProps) {
  const Colors = useThemeColors();
  const { t } = useTranslation();
  const [visible, setVisible] = React.useState(false);
  const current = LANGUAGES.find((l) => l.code === selectedLanguage);

  return (
    <>
      <button
        type="button"
        className={styles.button}
        onClick={() => setVisible(true)}
        aria-label={t('language.current', { name: current?.name ?? '' })}
      >
        <span className={styles.buttonCode}>{current?.shortCode}</span>
        <span className={styles.buttonText}>{current?.nativeName}</span>
        <IoChevronDown size={12} color={Colors.textMuted} />
      </button>

      {visible && (
        <div
          className={styles.overlay}
          onClick={() => setVisible(false)}
          role="presentation"
        >
          <div
            className={styles.modal}
            role="dialog"
            aria-modal="true"
            aria-label={t('language.title')}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className={styles.title}>{t('language.title')}</h2>
            {LANGUAGES.map((lang) => {
              const isSelected = selectedLanguage === lang.code;
              return (
                <button
                  type="button"
                  key={lang.code}
                  className={`${styles.row} ${isSelected ? styles.rowSelected : ''}`}
                  onClick={() => { onSelectLanguage(lang.code); setVisible(false); }}
                  aria-label={`${lang.name}${isSelected ? ', selected' : ''}`}
                  role="radio"
                  aria-checked={isSelected}
                >
                  <span className={styles.rowCode}>{lang.shortCode}</span>
                  <span className={styles.rowText}>
                    <span className={`${styles.rowName} ${isSelected ? styles.rowNameSelected : ''}`}>
                      {lang.nativeName}
                    </span>
                    <span className={styles.rowSub}>{lang.name}</span>
                  </span>
                  {isSelected && <IoCheckmark size={16} color={Colors.amber} />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
