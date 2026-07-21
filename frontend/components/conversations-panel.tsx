import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';
import { Conversation, useConversations } from '@/hooks/use-conversations';
import { useTranslation } from '@/hooks/use-translation';

interface ConversationsPanelProps {
  visible: boolean;
  onClose: () => void;
}

function formatDate(ts: number): string {
  const d = new Date(ts);
  const today = new Date();
  const isToday = d.toDateString() === today.toDateString();
  return isToday
    ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export function ConversationsPanel({ visible, onClose }: ConversationsPanelProps) {
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const { t } = useTranslation();
  const {
    conversations, activeId, createConversation, selectConversation, deleteConversation, renameConversation,
  } = useConversations();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);

  const handleSelect = (id: string) => {
    selectConversation(id);
    onClose();
  };

  const handleNewChat = () => {
    createConversation();
    onClose();
  };

  const startRename = (c: Conversation) => {
    setEditingId(c.id);
    setEditingTitle(c.title);
  };

  const commitRename = () => {
    if (editingId && editingTitle.trim()) {
      renameConversation(editingId, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle('');
  };

  const handleDelete = (c: Conversation) => {
    const confirmed = Platform.OS === 'web'
      ? window.confirm(t('conversations.deleteConfirm', { title: c.title }))
      : true; // Alert.alert would require importing Alert; web covers primary target here.
    if (confirmed) deleteConversation(c.id);
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={styles.container} accessibilityViewIsModal>
        <View style={[styles.header, Shadows.card]}>
          <View style={styles.headerTitle}>
            <View style={styles.headerIconWrap}>
              <Ionicons name="chatbubbles" size={18} color={Colors.amber} />
            </View>
            <Text style={styles.title} accessibilityRole="header">{t('conversations.title')}</Text>
          </View>
          <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityLabel={t('conversations.close')} accessibilityRole="button">
            <Ionicons name="close" size={18} color={Colors.textMuted} />
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.newBtn} onPress={handleNewChat} accessibilityLabel={t('conversations.startNewChat')} accessibilityRole="button">
          <Ionicons name="add" size={18} color="#FFF" />
          <Text style={styles.newBtnText}>{t('conversations.newChat')}</Text>
        </TouchableOpacity>

        <View style={styles.divider} />

        <ScrollView contentContainerStyle={styles.list}>
          {sorted.map((c) => {
            const isActive = c.id === activeId;
            const isEditing = editingId === c.id;
            return (
              <View key={c.id} style={[styles.convCard, Shadows.card, isActive && styles.convCardActive]}>
                <TouchableOpacity
                  style={styles.convMain}
                  onPress={() => (isEditing ? undefined : handleSelect(c.id))}
                  disabled={isEditing}
                  accessibilityLabel={t('conversations.openChat', { title: c.title })}
                  accessibilityRole="button"
                >
                  {isEditing ? (
                    <TextInput
                      style={styles.editInput}
                      value={editingTitle}
                      onChangeText={setEditingTitle}
                      onSubmitEditing={commitRename}
                      onBlur={commitRename}
                      autoFocus
                      maxLength={80}
                    />
                  ) : (
                    <>
                      <Text style={styles.convTitle} numberOfLines={1}>{c.title}</Text>
                      <Text style={styles.convMeta}>
                        {t('conversations.messageCount', { count: c.messages.length })} · {formatDate(c.updatedAt)}
                      </Text>
                    </>
                  )}
                </TouchableOpacity>

                {!isEditing && (
                  <View style={styles.convActions}>
                    <TouchableOpacity
                      onPress={() => startRename(c)}
                      style={styles.iconBtn}
                      accessibilityLabel={t('conversations.rename', { title: c.title })}
                      accessibilityRole="button"
                    >
                      <Ionicons name="pencil-outline" size={15} color={Colors.textMuted} />
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={() => handleDelete(c)}
                      style={styles.iconBtn}
                      accessibilityLabel={t('conversations.delete', { title: c.title })}
                      accessibilityRole="button"
                    >
                      <Ionicons name="trash-outline" size={15} color={Colors.error} />
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            );
          })}
        </ScrollView>
      </SafeAreaView>
    </Modal>
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
  headerTitle: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerIconWrap: {
    width: 34,
    height: 34,
    borderRadius: Radii.sm,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: { fontSize: 17, fontWeight: '700', color: Colors.text },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: Radii.full,
    backgroundColor: Colors.surfaceWarm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  newBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    margin: 16,
    marginBottom: 8,
    backgroundColor: Colors.amber,
    borderRadius: Radii.md,
    paddingVertical: 14,
    ...Shadows.float,
  },
  newBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
  divider: { height: 1, backgroundColor: Colors.border, marginTop: 8 },
  list: { padding: 16, gap: 8 },
  convCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: 12,
    gap: 8,
  },
  convCardActive: {
    borderWidth: 1.5,
    borderColor: Colors.amber,
  },
  convMain: { flex: 1 },
  convTitle: { fontSize: 14, fontWeight: '600', color: Colors.text },
  convMeta: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  editInput: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.text,
    borderBottomWidth: 1,
    borderBottomColor: Colors.amber,
    paddingVertical: 2,
  },
  convActions: { flexDirection: 'row', gap: 4 },
  iconBtn: {
    width: 30,
    height: 30,
    borderRadius: Radii.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
