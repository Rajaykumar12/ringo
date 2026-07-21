import { useNavigate } from 'react-router-dom';
import { IoClose, IoPhonePortraitOutline, IoSunnyOutline, IoMoonOutline, IoCheckmark, IoStatsChartOutline, IoChevronForward } from 'react-icons/io5';
import type { IconType } from 'react-icons';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useAppSettings, ThemeMode } from '@/hooks/use-app-settings';
import { LANGUAGES, Language } from '@/components/language-selector';
import { useTranslation } from '@/hooks/use-translation';
import styles from './SettingsPage.module.css';

const UI_LANGUAGES = LANGUAGES.filter((l): l is typeof LANGUAGES[number] & { code: Exclude<Language, 'auto'> } => l.code !== 'auto');

export default function SettingsPage() {
  const navigate = useNavigate();
  const Colors = useThemeColors();
  const { t } = useTranslation();
  const {
    themeMode, setThemeMode,
    defaultLanguage, setDefaultLanguage,
    uiLanguage, setUiLanguage,
    streamingEnabled, setStreamingEnabled,
  } = useAppSettings();

  const THEME_OPTIONS: { mode: ThemeMode; label: string; icon: IconType }[] = [
    { mode: 'system', label: t('settings.themeSystem'), icon: IoPhonePortraitOutline },
    { mode: 'light', label: t('settings.themeLight'), icon: IoSunnyOutline },
    { mode: 'dark', label: t('settings.themeDark'), icon: IoMoonOutline },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <button type="button" onClick={() => navigate(-1)} className={styles.closeBtn} aria-label={t('settings.close')}>
          <IoClose size={20} color={Colors.textMuted} />
        </button>
        <h1 className={styles.title}>{t('settings.title')}</h1>
        <div className={styles.closeBtn} style={{ visibility: 'hidden' }} />
      </div>

      <div className={styles.content}>
        <div className={styles.sectionLabel}>{t('settings.appearance')}</div>
        <div className={styles.card}>
          <div className={styles.segmented}>
            {THEME_OPTIONS.map((opt) => {
              const selected = themeMode === opt.mode;
              const Icon = opt.icon;
              return (
                <button
                  type="button"
                  key={opt.mode}
                  className={`${styles.segment} ${selected ? styles.segmentSelected : ''}`}
                  onClick={() => setThemeMode(opt.mode)}
                  aria-label={`Theme: ${opt.label}${selected ? ', selected' : ''}`}
                  role="radio"
                  aria-checked={selected}
                >
                  <Icon size={16} color={selected ? '#FFF' : Colors.textMuted} />
                  <span className={`${styles.segmentText} ${selected ? styles.segmentTextSelected : ''}`}>{opt.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className={styles.sectionLabel}>{t('settings.defaultLanguage')}</div>
        <div className={styles.card}>
          {LANGUAGES.map((lang) => {
            const selected = defaultLanguage === lang.code;
            return (
              <button
                type="button"
                key={lang.code}
                className={`${styles.row} ${selected ? styles.rowSelected : ''}`}
                onClick={() => setDefaultLanguage(lang.code)}
                aria-label={`${lang.name}${selected ? ', selected' : ''}`}
                role="radio"
                aria-checked={selected}
              >
                <span className={styles.rowCode}>{lang.shortCode}</span>
                <span className={styles.rowText}>
                  <span className={`${styles.rowName} ${selected ? styles.rowNameSelected : ''}`}>{lang.nativeName}</span>
                  <span className={styles.rowSub}>{lang.name}</span>
                </span>
                {selected && <IoCheckmark size={16} color={Colors.amber} />}
              </button>
            );
          })}
        </div>

        <div className={styles.sectionLabel}>{t('settings.uiLanguage')}</div>
        <div className={styles.card}>
          {UI_LANGUAGES.map((lang) => {
            const selected = uiLanguage === lang.code;
            return (
              <button
                type="button"
                key={lang.code}
                className={`${styles.row} ${selected ? styles.rowSelected : ''}`}
                onClick={() => setUiLanguage(lang.code)}
                aria-label={`${lang.name}${selected ? ', selected' : ''}`}
                role="radio"
                aria-checked={selected}
              >
                <span className={styles.rowCode}>{lang.shortCode}</span>
                <span className={styles.rowText}>
                  <span className={`${styles.rowName} ${selected ? styles.rowNameSelected : ''}`}>{lang.nativeName}</span>
                  <span className={styles.rowSub}>{lang.name}</span>
                </span>
                {selected && <IoCheckmark size={16} color={Colors.amber} />}
              </button>
            );
          })}
        </div>

        <div className={styles.sectionLabel}>{t('settings.responses')}</div>
        <div className={styles.card}>
          <div className={styles.switchRow}>
            <div className={styles.switchLabelWrap}>
              <div className={styles.switchLabel}>{t('settings.streamResponses')}</div>
              <div className={styles.switchSub}>{t('settings.streamResponsesSub')}</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={streamingEnabled}
              aria-label={t('settings.streamResponses')}
              className={`${styles.switch} ${streamingEnabled ? styles.switchOn : ''}`}
              onClick={() => setStreamingEnabled(!streamingEnabled)}
            >
              <span className={`${styles.switchThumb} ${streamingEnabled ? styles.switchThumbOn : ''}`} />
            </button>
          </div>
        </div>

        <div className={styles.sectionLabel}>{t('settings.advanced')}</div>
        <div className={styles.card}>
          <button
            type="button"
            className={styles.row}
            onClick={() => navigate('/admin')}
            aria-label={t('settings.adminDashboard')}
          >
            <IoStatsChartOutline size={18} color={Colors.textMuted} />
            <span className={styles.rowText}>
              <span className={styles.rowName}>{t('settings.adminDashboard')}</span>
              <span className={styles.rowSub}>{t('settings.adminDashboardSub')}</span>
            </span>
            <IoChevronForward size={16} color={Colors.textFaint} />
          </button>
        </div>
      </div>
    </div>
  );
}
