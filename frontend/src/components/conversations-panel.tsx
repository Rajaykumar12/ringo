import { useState } from 'react';
import { IoChatbubbles, IoClose, IoAdd, IoPencilOutline, IoTrashOutline } from 'react-icons/io5';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { Conversation, useConversations } from '@/hooks/use-conversations';
import styles from './conversations-panel.module.css';

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
  const {
    conversations, activeId, createConversation, selectConversation, deleteConversation, renameConversation,
  } = useConversations();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  if (!visible) return null;

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
    if (window.confirm(`Delete "${c.title}"?`)) {
      deleteConversation(c.id);
    }
  };

  return (
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.container}
        role="dialog"
        aria-modal="true"
        aria-label="Chats"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <div className={styles.headerIconWrap}>
              <IoChatbubbles size={18} color={Colors.amber} />
            </div>
            <h2 className={styles.title}>Chats</h2>
          </div>
          <button type="button" onClick={onClose} className={styles.closeBtn} aria-label="Close chat history">
            <IoClose size={18} color={Colors.textMuted} />
          </button>
        </div>

        <button type="button" className={styles.newBtn} onClick={handleNewChat} aria-label="Start a new chat">
          <IoAdd size={18} color="#FFF" />
          <span className={styles.newBtnText}>New Chat</span>
        </button>

        <div className={styles.divider} />

        <div className={styles.list}>
          {sorted.map((c) => {
            const isActive = c.id === activeId;
            const isEditing = editingId === c.id;
            return (
              <div key={c.id} className={`${styles.convCard} ${isActive ? styles.convCardActive : ''}`}>
                {isEditing ? (
                  <div className={styles.convMain}>
                    <input
                      className={styles.editInput}
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') commitRename(); }}
                      onBlur={commitRename}
                      autoFocus
                      maxLength={80}
                    />
                  </div>
                ) : (
                  <button
                    type="button"
                    className={styles.convMain}
                    onClick={() => handleSelect(c.id)}
                    aria-label={`Open chat: ${c.title}`}
                  >
                    <span className={styles.convTitle}>{c.title}</span>
                    <span className={styles.convMeta}>
                      {c.messages.length} messages · {formatDate(c.updatedAt)}
                    </span>
                  </button>
                )}

                {!isEditing && (
                  <div className={styles.convActions}>
                    <button
                      type="button"
                      onClick={() => startRename(c)}
                      className={styles.iconBtn}
                      aria-label={`Rename ${c.title}`}
                    >
                      <IoPencilOutline size={15} color={Colors.textMuted} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(c)}
                      className={styles.iconBtn}
                      aria-label={`Delete ${c.title}`}
                    >
                      <IoTrashOutline size={15} color={Colors.error} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
