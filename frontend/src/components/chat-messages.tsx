import React from 'react';
import ReactMarkdown from 'react-markdown';
import { IoSparkles, IoCopyOutline, IoCheckmark, IoPencilOutline, IoRefreshOutline, IoPlay, IoPause, IoMic, IoClose } from 'react-icons/io5';
import { Message, SourceCitation, toImageUrl } from '@/services/api';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { StreamingLiveRegion } from '@/components/streaming-live-region';
import styles from './chat-messages.module.css';

const MarkdownImage = (
  { src, alt, onOpen }: { src?: string; alt?: string; onOpen: (src: string) => void }
) => {
  if (!src) return null;
  const resolved = toImageUrl(src);
  return (
    <img
      src={resolved}
      alt={alt || ''}
      className={styles.attachedImage}
      onClick={() => onOpen(resolved)}
    />
  );
};

// The backend embeds bare "[n]" citation markers in response text (see rag.py's
// _sanitize_citations, which already strips any marker not backed by a real source).
// Rewrite the ones that match a known source into markdown link syntax so ReactMarkdown
// renders them through the `a` component override below as clickable badges instead of
// literal text.
const CITATION_MARKER_RE = /\[(\d+)\]/g;

function linkifyCitations(text: string, validIndices: Set<number>): string {
  if (validIndices.size === 0) return text;
  return text.replace(CITATION_MARKER_RE, (match, digits) => {
    const idx = Number(digits);
    return validIndices.has(idx) ? `[${idx}](citation:${idx})` : match;
  });
}

function sourceLabel(source: SourceCitation): string {
  if (source.page) return `${source.filename} · p.${source.page}`;
  if (source.slide) return `${source.filename} · slide ${source.slide}`;
  return source.filename;
}

interface ChatMessagesProps {
  messages: Message[];
  onPlayAudio: (messageId: string, messageText: string, cachedAudioData?: string) => void;
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
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [lightboxSrc, setLightboxSrc] = React.useState<string | null>(null);
  const [activeSource, setActiveSource] = React.useState<{ messageId: string; index: number } | null>(null);

  React.useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleCitationClick = (messageId: string, index: number) => {
    setActiveSource((prev) =>
      prev?.messageId === messageId && prev.index === index ? null : { messageId, index }
    );
    document
      .getElementById(`source-chip-${messageId}-${index}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const handleAudioButtonPress = (message: Message) => {
    if (playingMessageId === message.id) {
      if (isPlaying) onPauseAudio(); else onResumeAudio();
    } else {
      onPlayAudio(message.id, message.text, message.audio_data);
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
                    <img
                      src={message.imageUri}
                      className={styles.attachedImage}
                      alt=""
                      onClick={() => setLightboxSrc(message.imageUri!)}
                    />
                  )}

                  {message.imageUris && message.imageUris.length > 0 && (
                    <div className={styles.attachedImageGrid}>
                      {message.imageUris.map((uri) => (
                        <img
                          key={uri}
                          src={uri}
                          className={styles.attachedImage}
                          alt=""
                          onClick={() => setLightboxSrc(uri)}
                        />
                      ))}
                    </div>
                  )}

                  {isUser || !message.text ? (
                    <p className={`${styles.bubbleText} ${isUser ? styles.bubbleTextUser : styles.bubbleTextAI}`}>
                      {message.text || (isUser ? '' : '…')}
                    </p>
                  ) : (
                    <>
                      <div className={`${styles.markdown} ${styles.bubbleTextAI}`}>
                        <ReactMarkdown
                          components={{
                            img: ({ src, alt }) => (
                              <MarkdownImage src={src} alt={alt} onOpen={setLightboxSrc} />
                            ),
                            a: ({ href, children }) => {
                              if (href?.startsWith('citation:')) {
                                const idx = Number(href.slice('citation:'.length));
                                return (
                                  <button
                                    type="button"
                                    className={styles.citationBadge}
                                    onClick={() => handleCitationClick(message.id, idx)}
                                    aria-label={`Jump to source ${idx}`}
                                  >
                                    {idx}
                                  </button>
                                );
                              }
                              // Defense-in-depth: only render as a live link if it's
                              // http(s). react-markdown's default (non-raw-HTML) mode
                              // already blocks script injection, but an LLM-emitted
                              // `javascript:`-scheme link would otherwise still render.
                              if (!href || !/^https?:\/\//i.test(href)) {
                                return <>{children}</>;
                              }
                              return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
                            },
                          }}
                        >
                          {linkifyCitations(
                            message.text,
                            new Set((message.sources ?? []).map((s) => s.index))
                          )}
                        </ReactMarkdown>
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
                        Voice
                      </span>
                    </div>
                  )}

                  <div className={`${styles.timestamp} ${isUser ? styles.timestampUser : ''}`}>
                    {formatTime(message.timestamp)}
                  </div>
                </div>

                {!isUser && message.sources && message.sources.length > 0 && (
                  <div className={styles.sourcesStrip}>
                    {message.sources.map((source) => (
                      <button
                        key={source.index}
                        id={`source-chip-${message.id}-${source.index}`}
                        type="button"
                        className={[
                          styles.sourceChip,
                          activeSource?.messageId === message.id && activeSource.index === source.index
                            ? styles.sourceChipActive
                            : '',
                        ].join(' ')}
                        onClick={() => handleCitationClick(message.id, source.index)}
                      >
                        <span className={styles.sourceChipIndex}>[{source.index}]</span>
                        <span className={styles.sourceChipLabel}>{sourceLabel(source)}</span>
                      </button>
                    ))}
                  </div>
                )}

                {!isUser && activeSource?.messageId === message.id && (
                  <div className={styles.sourcePreview}>
                    {message.sources?.find((s) => s.index === activeSource.index)?.preview}
                  </div>
                )}

                {!!message.text && (
                  <div className={`${styles.actionRow} ${isUser ? styles.actionRowUser : ''}`}>
                    <button
                      type="button"
                      onClick={() => handleCopy(message)}
                      className={styles.actionIcon}
                      aria-label="Copy message"
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
                        aria-label="Edit and resend message"
                      >
                        <IoPencilOutline size={12} color={Colors.textFaint} />
                      </button>
                    )}

                    {isLastAI && !isLoading && (
                      <button
                        type="button"
                        onClick={() => onRegenerate(message)}
                        className={styles.actionIcon}
                        aria-label="Regenerate response"
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
                  aria-label={isPlayingThis && isPlaying ? 'Pause audio' : 'Play audio'}
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

      {lightboxSrc && (
        <div
          className={styles.lightboxBackdrop}
          role="presentation"
          onClick={() => setLightboxSrc(null)}
        >
          <button
            type="button"
            className={styles.lightboxClose}
            aria-label="Close image"
            onClick={() => setLightboxSrc(null)}
          >
            <IoClose size={22} color="#FFF" />
          </button>
          <img src={lightboxSrc} className={styles.lightboxImage} alt="" onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  );
}

