import { useNavigate } from 'react-router-dom';
import { IoClose, IoPhonePortraitOutline, IoSunnyOutline, IoMoonOutline, IoStatsChartOutline, IoChevronForward } from 'react-icons/io5';
import type { IconType } from 'react-icons';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useAppSettings, ThemeMode } from '@/hooks/use-app-settings';
import styles from './SettingsPage.module.css';

export default function SettingsPage() {
  const navigate = useNavigate();
  const Colors = useThemeColors();
  const {
    themeMode, setThemeMode,
    streamingEnabled, setStreamingEnabled,
  } = useAppSettings();

  const THEME_OPTIONS: { mode: ThemeMode; label: string; icon: IconType }[] = [
    { mode: 'system', label: 'System', icon: IoPhonePortraitOutline },
    { mode: 'light', label: 'Light', icon: IoSunnyOutline },
    { mode: 'dark', label: 'Dark', icon: IoMoonOutline },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <button type="button" onClick={() => navigate(-1)} className={styles.closeBtn} aria-label="Close settings">
          <IoClose size={20} color={Colors.textMuted} />
        </button>
        <h1 className={styles.title}>Settings</h1>
        <div className={styles.closeBtn} style={{ visibility: 'hidden' }} />
      </div>

      <div className={styles.content}>
        <div className={styles.sectionLabel}>Appearance</div>
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

        <div className={styles.sectionLabel}>Responses</div>
        <div className={styles.card}>
          <div className={styles.switchRow}>
            <div className={styles.switchLabelWrap}>
              <div className={styles.switchLabel}>Stream responses</div>
              <div className={styles.switchSub}>Show the AI's reply as it's generated, token by token.</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={streamingEnabled}
              aria-label="Stream responses"
              className={`${styles.switch} ${streamingEnabled ? styles.switchOn : ''}`}
              onClick={() => setStreamingEnabled(!streamingEnabled)}
            >
              <span className={`${styles.switchThumb} ${streamingEnabled ? styles.switchThumbOn : ''}`} />
            </button>
          </div>
        </div>

        <div className={styles.sectionLabel}>Advanced</div>
        <div className={styles.card}>
          <button
            type="button"
            className={styles.row}
            onClick={() => navigate('/admin')}
            aria-label="Admin dashboard"
          >
            <IoStatsChartOutline size={18} color={Colors.textMuted} />
            <span className={styles.rowText}>
              <span className={styles.rowName}>Admin dashboard</span>
              <span className={styles.rowSub}>RAG call volume, latency, ratings, eval scores</span>
            </span>
            <IoChevronForward size={16} color={Colors.textFaint} />
          </button>
        </div>
      </div>
    </div>
  );
}
