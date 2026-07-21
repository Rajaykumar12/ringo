import { IoChatbubblesOutline, IoFolderOpenOutline, IoSettingsOutline } from 'react-icons/io5';
import type { IconType } from 'react-icons';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useTranslation } from '@/hooks/use-translation';
import styles from './header-menu.module.css';

interface HeaderMenuProps {
  visible: boolean;
  onClose: () => void;
  onSelectHistory: () => void;
  onSelectDocuments: () => void;
  onSelectSettings: () => void;
}

export function HeaderMenu({
  visible,
  onClose,
  onSelectHistory,
  onSelectDocuments,
  onSelectSettings,
}: HeaderMenuProps) {
  const Colors = useThemeColors();
  const { t } = useTranslation();

  if (!visible) return null;

  const items: { label: string; icon: IconType; onPress: () => void }[] = [
    { label: t('menu.chatHistory'), icon: IoChatbubblesOutline, onPress: onSelectHistory },
    { label: t('menu.documents'), icon: IoFolderOpenOutline, onPress: onSelectDocuments },
    { label: t('menu.settings'), icon: IoSettingsOutline, onPress: onSelectSettings },
  ];

  return (
    <div className={styles.overlay} onClick={onClose} role="presentation">
      <div className={styles.menu} role="menu" onClick={(e) => e.stopPropagation()}>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              type="button"
              key={item.label}
              className={styles.row}
              onClick={() => { item.onPress(); onClose(); }}
              aria-label={item.label}
              role="menuitem"
            >
              <Icon size={17} color={Colors.textMuted} />
              <span className={styles.rowText}>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
