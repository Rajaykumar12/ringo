import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';
import { useTranslation } from '@/hooks/use-translation';

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
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const { t } = useTranslation();

  const items: { label: string; icon: keyof typeof Ionicons.glyphMap; onPress: () => void }[] = [
    { label: t('menu.chatHistory'), icon: 'chatbubbles-outline', onPress: onSelectHistory },
    { label: t('menu.documents'), icon: 'folder-open-outline', onPress: onSelectDocuments },
    { label: t('menu.settings'), icon: 'settings-outline', onPress: onSelectSettings },
  ];

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose}>
        <View style={[styles.menu, Shadows.float]} accessibilityViewIsModal accessibilityRole="menu">
          {items.map((item) => (
            <TouchableOpacity
              key={item.label}
              style={styles.row}
              onPress={() => { item.onPress(); onClose(); }}
              accessibilityLabel={item.label}
              accessibilityRole="menuitem"
            >
              <Ionicons name={item.icon} size={17} color={Colors.textMuted} />
              <Text style={styles.rowText}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </Pressable>
    </Modal>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(17,24,39,0.25)',
  },
  menu: {
    position: 'absolute',
    top: 58,
    left: 14,
    minWidth: 190,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    paddingVertical: 6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 14,
    minHeight: 44,
  },
  rowText: { fontSize: 14, fontWeight: '600', color: Colors.text },
});
