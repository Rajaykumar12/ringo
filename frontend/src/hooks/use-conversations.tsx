import React, { createContext, useContext, useEffect, useState } from 'react';
import type { Message } from '@/services/api';

export interface Conversation {
  id: string;
  sessionId: string;
  title: string;
  messages: Message[];
  updatedAt: number;
}

interface ConversationsContextValue {
  conversations: Conversation[];
  activeId: string | null;
  activeConversation: Conversation | null;
  loaded: boolean;
  createConversation: () => string;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  updateActiveMessages: (messages: Message[]) => void;
}

const STORAGE_KEY = 'ringo:conversations';
const MAX_TITLE_LENGTH = 42;

// crypto.randomUUID(), not Date.now()+Math.random(): sessionId doubles as a
// bearer capability token for GET /conversations/{session_id}, so it needs to
// be unguessable, not just unique.
const makeId = () => `conv_${crypto.randomUUID()}`;
const makeSessionId = () => `session_${crypto.randomUUID()}`;

function freshConversation(): Conversation {
  return { id: makeId(), sessionId: makeSessionId(), title: 'New chat', messages: [], updatedAt: Date.now() };
}

function deriveTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.sender === 'user' && m.text.trim());
  if (!firstUser) return 'New chat';
  const text = firstUser.text.trim();
  return text.length > MAX_TITLE_LENGTH ? text.slice(0, MAX_TITLE_LENGTH - 1) + '…' : text;
}

const ConversationsContext = createContext<ConversationsContextValue | null>(null);

export function ConversationsProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const restored: Conversation[] = (parsed.conversations ?? []).map((c: any) => ({
          ...c,
          messages: (c.messages ?? []).map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) })),
        }));
        if (restored.length > 0) {
          setConversations(restored);
          setActiveId(
            parsed.activeId && restored.some((c) => c.id === parsed.activeId)
              ? parsed.activeId
              : restored[0].id
          );
          setLoaded(true);
          return;
        }
      }
    } catch {
      // Corrupt/missing conversation history — fall through to a fresh conversation.
    }
    const fresh = freshConversation();
    setConversations([fresh]);
    setActiveId(fresh.id);
    setLoaded(true);
  }, []);

  // Gated on `loaded` (state, not a ref) so this only ever fires on a render where
  // `conversations`/`activeId` already reflect the hydrated values — a ref flipped
  // inside the hydration effect above flips before this effect's closure captures
  // the new state, so it would otherwise fire once with the stale pre-hydration
  // ([], null) and overwrite the persisted history with an empty conversation list.
  useEffect(() => {
    if (!loaded) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ conversations, activeId }));
    } catch {
      // Storage unavailable/full — history just won't persist this time.
    }
  }, [conversations, activeId, loaded]);

  const createConversation = () => {
    const fresh = freshConversation();
    setConversations((prev) => [fresh, ...prev]);
    setActiveId(fresh.id);
    return fresh.id;
  };

  const selectConversation = (id: string) => setActiveId(id);

  const deleteConversation = (id: string) => {
    const next = conversations.filter((c) => c.id !== id);
    if (next.length === 0) {
      const fresh = freshConversation();
      setConversations([fresh]);
      setActiveId(fresh.id);
      return;
    }
    setConversations(next);
    if (activeId === id) setActiveId(next[0].id);
  };

  const renameConversation = (id: string, title: string) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
  };

  const updateActiveMessages = (messages: Message[]) => {
    if (!activeId) return;
    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeId
          ? { ...c, messages, updatedAt: Date.now(), title: c.title === 'New chat' ? deriveTitle(messages) : c.title }
          : c
      )
    );
  };

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;

  return (
    <ConversationsContext.Provider
      value={{
        conversations, activeId, activeConversation, loaded,
        createConversation, selectConversation, deleteConversation, renameConversation, updateActiveMessages,
      }}
    >
      {children}
    </ConversationsContext.Provider>
  );
}

export function useConversations(): ConversationsContextValue {
  const ctx = useContext(ConversationsContext);
  if (!ctx) throw new Error('useConversations must be used within a ConversationsProvider');
  return ctx;
}
