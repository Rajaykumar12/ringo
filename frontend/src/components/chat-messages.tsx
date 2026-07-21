import React from 'react';
import ReactMarkdown from 'react-markdown';
import { IoSparkles, IoCopyOutline, IoCheckmark, IoPencilOutline, IoRefreshOutline, IoPlay, IoPause, IoMic } from 'react-icons/io5';
import { Message } from '@/services/api';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { StreamingLiveRegion } from '@/components/streaming-live-region';
import { useTranslation } from '@/hooks/use-translation';
import styles from './chat-messages.module.css';

interface ChatMessagesProps {
  messages: Message[];
  onPlayAudio: (messageId: string, messageText: string, messageLang: string, cachedAudioData?: string) => void;
  onPauseAudio: () => void;
  onResumeAudio: () => void;
  playingMessageId: string | null;
  isPlaying: boolean;
  isGeneratingTTS: boolean;
  onEditMessage: (message: Message) => void;
  onRegenerate: (message: Message) => void;
  isLoading: boolean;
}

export function ChatMessages({
  messages,
  onPlayAudio,
  onPauseAudio,
  onResumeAudio,
  playingMessageId,
  isPlaying,
  isGeneratingTTS,
  onEditMessage,
  onRegenerate,
  isLoading,
}: ChatMessagesProps) {
  const Colors = useThemeColors();
  const { t } = useTranslation();
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  React.useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleAudioButtonPress = (message: Message) => {
    const lang = message.language || 'en';
    if (playingMessageId === message.id) {
      if (isPlaying) onPauseAudio(); else onResumeAudio();
    } else {
      onPlayAudio(message.id, message.text, lang, message.audio_data);
    }
  };

  const handleCopy = async (message: Message) => {
    try {
      await navigator.clipboard.writeText(message.text);
    } catch {
      // Clipboard API unavailable/denied — silently no-op.
    }
    setCopiedId(message.id);
    setTimeout(() => setCopiedId((id) => (id === message.id ? null : id)), 1500);
  };

  const lastAIMessageId = [...messages].reverse().find((m) => m.sender === 'ai')?.id;

  const formatTime = (d: Date) =>
    new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.content}>
        {messages.map((message) => {
          const isUser = message.sender === 'user';
          const isPlayingThis = playingMessageId === message.id;
          const isLastAI = !isUser && message.id === lastAIMessageId;

          return (
            <div key={message.id} className={`${styles.row} ${isUser ? styles.rowUser : styles.rowAI}`}>
              {!isUser && (
                <div className={styles.avatar}>
                  <IoSparkles size={14} color={Colors.teal} />
                </div>
              )}

              <div className={styles.bubbleCol}>
                <div
                  className={[
                    styles.bubble,
                    isUser ? styles.bubbleUser : styles.bubbleAI,
                    isPlayingThis ? styles.bubblePlaying : '',
                  ].join(' ')}
                >
                  {message.imageUri && (
                    <img src={message.imageUri} className={styles.attachedImage} alt="" />
                  )}

                  {isUser || !message.text ? (
                    <p className={`${styles.bubbleText} ${isUser ? styles.bubbleTextUser : styles.bubbleTextAI}`}>
                      {message.text || (isUser ? '' : '…')}
                    </p>
                  ) : (
                    <>
                      <div className={`${styles.markdown} ${styles.bubbleTextAI}`}>
                        <ReactMarkdown>{message.text}</ReactMarkdown>
                      </div>
                      <StreamingLiveRegion text={message.text} active={isLastAI && isLoading} />
                    </>
                  )}

                  {message.isAudio && (
                    <div className={styles.audioLabel}>
                      <span style={{ display: 'flex' }}>
                        <IoMic size={10} color={isUser ? 'rgba(255,255,255,0.7)' : Colors.textMuted} />
                      </span>
                      <span className={`${styles.audioLabelText} ${isUser ? styles.audioLabelTextUser : ''}`}>
                        {t('chat.voiceLabel')}
                      </span>
                    </div>
                  )}

                  <div className={`${styles.timestamp} ${isUser ? styles.timestampUser : ''}`}>
                    {formatTime(message.timestamp)}
                  </div>
                </div>

                {!!message.text && (
                  <div className={`${styles.actionRow} ${isUser ? styles.actionRowUser : ''}`}>
                    <button
                      type="button"
                      onClick={() => handleCopy(message)}
                      className={styles.actionIcon}
                      aria-label={t('chat.copyMessage')}
                    >
                      {copiedId === message.id
                        ? <IoCheckmark size={12} color={Colors.textFaint} />
                        : <IoCopyOutline size={12} color={Colors.textFaint} />}
                    </button>

                    {isUser && !isLoading && (
                      <button
                        type="button"
                        onClick={() => onEditMessage(message)}
                        className={styles.actionIcon}
                        aria-label={t('chat.editMessage')}
                      >
                        <IoPencilOutline size={12} color={Colors.textFaint} />
                      </button>
                    )}

                    {isLastAI && !isLoading && (
                      <button
                        type="button"
                        onClick={() => onRegenerate(message)}
                        className={styles.actionIcon}
                        aria-label={t('chat.regenerate')}
                      >
                        <IoRefreshOutline size={12} color={Colors.textFaint} />
                      </button>
                    )}
                  </div>
                )}
              </div>

              {!isUser && (
                <button
                  type="button"
                  onClick={() => handleAudioButtonPress(message)}
                  className={styles.audioBtn}
                  aria-label={isPlayingThis && isPlaying ? t('chat.pauseAudio') : t('chat.playAudio')}
                >
                  {isGeneratingTTS && isPlayingThis ? (
                    <span className={styles.spinner} />
                  ) : isPlayingThis && isPlaying ? (
                    <IoPause size={16} color="#FFF" />
                  ) : (
                    <IoPlay size={16} color="#FFF" />
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

