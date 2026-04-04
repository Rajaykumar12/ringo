import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Modal,
  Platform,
} from 'react-native';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Message, getDocumentChunks, DocumentChunk } from '@/services/api';
import { Colors, Radii, Shadows } from '@/constants/theme';

interface ChatMessagesProps {
  messages: Message[];
  onPlayAudio: (messageId: string, messageText: string, messageLang: string, cachedAudioData?: string) => void;
  onPauseAudio: () => void;
  onResumeAudio: () => void;
  playingMessageId: string | null;
  isPlaying: boolean;
  isGeneratingTTS: boolean;
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

function SpringPressable({ onPress, style, children, accessibilityLabel }: {
  onPress: () => void;
  style?: any;
  children: React.ReactNode;
  accessibilityLabel?: string;
}) {
  const scale = useSharedValue(1);
  const animStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return (
    <AnimatedPressable
      onPressIn={() => { scale.value = withSpring(0.93, { damping: 15 }); }}
      onPressOut={() => { scale.value = withSpring(1, { damping: 15 }); }}
      onPress={onPress}
      style={[style, animStyle]}
      accessibilityLabel={accessibilityLabel}
    >
      {children}
    </AnimatedPressable>
  );
}

export function ChatMessages({
  messages,
  onPlayAudio,
  onPauseAudio,
  onResumeAudio,
  playingMessageId,
  isPlaying,
  isGeneratingTTS,
}: ChatMessagesProps) {
  const scrollViewRef = React.useRef<ScrollView>(null);

  const [previewSource, setPreviewSource] = useState<string | null>(null);
  const [previewQuery, setPreviewQuery] = useState('');
  const [previewChunks, setPreviewChunks] = useState<DocumentChunk[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  React.useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  const handleAudioButtonPress = (message: Message) => {
    const lang = message.language || 'en';
    if (playingMessageId === message.id) {
      isPlaying ? onPauseAudio() : onResumeAudio();
    } else {
      onPlayAudio(message.id, message.text, lang, message.audio_data);
    }
  };

  const handleSourcePress = async (source: string, messageText: string) => {
    setPreviewSource(source);
    setPreviewQuery(messageText);
    setPreviewChunks([]);
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const result = await getDocumentChunks(source, messageText);
      setPreviewChunks(result.chunks);
    } catch {
      setPreviewError('Failed to load source content.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => { setPreviewSource(null); setPreviewChunks([]); setPreviewError(null); };

  const formatTime = (d: Date) =>
    new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <>
      <ScrollView
        ref={scrollViewRef}
        style={styles.container}
        contentContainerStyle={styles.content}
      >
        {messages.map((message) => {
          const isUser = message.sender === 'user';
          const isPlayingThis = playingMessageId === message.id;

          return (
            <View key={message.id} style={[styles.row, isUser ? styles.rowUser : styles.rowAI]}>
              {/* AI avatar */}
              {!isUser && (
                <View style={styles.avatar}>
                  <Ionicons name="sparkles" size={14} color={Colors.teal} />
                </View>
              )}

              <View style={styles.bubbleCol}>
                <View
                  style={[
                    styles.bubble,
                    isUser ? styles.bubbleUser : styles.bubbleAI,
                    isPlayingThis && styles.bubblePlaying,
                  ]}
                >
                  <Text style={[styles.bubbleText, isUser ? styles.bubbleTextUser : styles.bubbleTextAI]}>
                    {message.text || (isUser ? '' : '…')}
                  </Text>

                  {message.isAudio && (
                    <View style={styles.audioLabel}>
                      <Ionicons name="mic" size={10} color={isUser ? 'rgba(255,255,255,0.7)' : Colors.textMuted} />
                      <Text style={[styles.audioLabelText, isUser && styles.audioLabelTextUser]}>Voice</Text>
                    </View>
                  )}

                  {/* Source tags */}
                  {!isUser && message.sources && message.sources.length > 0 && (
                    <View style={styles.sourcesRow}>
                      {message.sources.map((src, i) => (
                        <SpringPressable
                          key={i}
                          onPress={() => handleSourcePress(src, message.text)}
                          style={styles.sourceTag}
                          accessibilityLabel={`View source: ${src}`}
                        >
                          <Ionicons name="document-text-outline" size={9} color={Colors.amberDark} />
                          <Text style={styles.sourceTagText} numberOfLines={1}>{src}</Text>
                        </SpringPressable>
                      ))}
                    </View>
                  )}

                  <Text style={[styles.timestamp, isUser && styles.timestampUser]}>
                    {formatTime(message.timestamp)}
                  </Text>
                </View>
              </View>

              {/* Audio button */}
              {!isUser && (
                <SpringPressable
                  onPress={() => handleAudioButtonPress(message)}
                  style={[styles.audioBtn, Shadows.card]}
                  accessibilityLabel={isPlayingThis && isPlaying ? 'Pause audio' : 'Play audio'}
                >
                  {isGeneratingTTS && isPlayingThis ? (
                    <ActivityIndicator size="small" color="#FFF" />
                  ) : isPlayingThis && isPlaying ? (
                    <Ionicons name="pause" size={16} color="#FFF" />
                  ) : (
                    <Ionicons name="play" size={16} color="#FFF" />
                  )}
                </SpringPressable>
              )}
            </View>
          );
        })}
      </ScrollView>

      {/* Source preview modal */}
      <Modal
        visible={previewSource !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={closePreview}
      >
        <SafeAreaView style={styles.modal}>
          <View style={styles.modalHeader}>
            <View style={styles.modalTitleRow}>
              <View style={styles.modalIconWrap}>
                <Ionicons name="document-text" size={16} color={Colors.amber} />
              </View>
              <Text style={styles.modalTitle} numberOfLines={1}>{previewSource}</Text>
            </View>
            <Pressable onPress={closePreview} style={styles.closeBtn} accessibilityLabel="Close">
              <Ionicons name="close" size={20} color={Colors.textMuted} />
            </Pressable>
          </View>

          <Text style={styles.modalSubtitle}>
            {previewQuery ? 'Relevant passages from this document' : 'Document excerpts'}
          </Text>

          <ScrollView contentContainerStyle={styles.modalScroll}>
            {previewLoading && (
              <View style={styles.centered}>
                <ActivityIndicator size="large" color={Colors.amber} />
                <Text style={styles.centeredText}>Loading excerpts…</Text>
              </View>
            )}
            {previewError && (
              <View style={styles.centered}>
                <Ionicons name="alert-circle-outline" size={32} color={Colors.error} />
                <Text style={[styles.centeredText, { color: Colors.error }]}>{previewError}</Text>
              </View>
            )}
            {!previewLoading && !previewError && previewChunks.length === 0 && (
              <View style={styles.centered}>
                <Text style={styles.centeredText}>No excerpts found.</Text>
              </View>
            )}
            {previewChunks.map((chunk, i) => (
              <View key={i} style={[styles.chunkCard, Shadows.card]}>
                <Text style={styles.chunkLabel}>
                  Excerpt {i + 1}
                  {chunk.metadata.slide ? ` · Slide ${chunk.metadata.slide}` : ''}
                  {chunk.metadata.page ? ` · Page ${chunk.metadata.page}` : ''}
                  {chunk.metadata.type ? ` · ${chunk.metadata.type.toUpperCase()}` : ''}
                </Text>
                <Text style={styles.chunkText}>{chunk.text}</Text>
              </View>
            ))}
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  content: { padding: 16, paddingBottom: 4, gap: 4 },

  row: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: 14, maxWidth: '88%', gap: 8 },
  rowUser: { alignSelf: 'flex-end', flexDirection: 'row-reverse' },
  rowAI: { alignSelf: 'flex-start' },

  avatar: {
    width: 28,
    height: 28,
    borderRadius: Radii.full,
    backgroundColor: Colors.tealLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },

  bubbleCol: { flex: 1 },
  bubble: { borderRadius: Radii.lg, padding: 12 },
  bubbleUser: {
    backgroundColor: Colors.amber,
    borderBottomRightRadius: Radii.sm,
    ...Platform.select({
      ios: { shadowColor: Colors.amberDark, shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.25, shadowRadius: 6 },
      default: { elevation: 3 },
    }),
  },
  bubbleAI: {
    backgroundColor: Colors.surfaceWarm,
    borderBottomLeftRadius: Radii.sm,
    ...Shadows.card,
  },
  bubblePlaying: {
    borderWidth: 2,
    borderColor: Colors.teal,
  },

  bubbleText: { fontSize: 15, lineHeight: 22 },
  bubbleTextUser: { color: '#FFFFFF' },
  bubbleTextAI: { color: Colors.text },

  audioLabel: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 4 },
  audioLabelText: { fontSize: 11, color: Colors.textMuted },
  audioLabelTextUser: { color: 'rgba(255,255,255,0.7)' },

  sourcesRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 8 },
  sourceTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.amberLight,
    borderRadius: Radii.sm,
    paddingHorizontal: 8,
    paddingVertical: 4,
    maxWidth: 160,
  },
  sourceTagText: { fontSize: 11, color: Colors.amberDark, fontWeight: '500', flex: 1 },

  timestamp: { fontSize: 10, color: Colors.textFaint, marginTop: 5, alignSelf: 'flex-end' },
  timestampUser: { color: 'rgba(255,255,255,0.6)' },

  audioBtn: {
    width: 34,
    height: 34,
    borderRadius: Radii.full,
    backgroundColor: Colors.teal,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },

  // Modal
  modal: { flex: 1, backgroundColor: Colors.bg },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: Colors.surface,
    ...Shadows.card,
  },
  modalTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1, marginRight: 12 },
  modalIconWrap: {
    width: 30,
    height: 30,
    borderRadius: Radii.sm,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalTitle: { fontSize: 15, fontWeight: '700', color: Colors.text, flex: 1 },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: Radii.full,
    backgroundColor: Colors.surfaceWarm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalSubtitle: { fontSize: 12, color: Colors.textMuted, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 2 },
  modalScroll: { padding: 16, gap: 10 },
  centered: { alignItems: 'center', paddingTop: 60, gap: 12 },
  centeredText: { fontSize: 14, color: Colors.textMuted },
  chunkCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: 14,
    gap: 8,
  },
  chunkLabel: { fontSize: 11, fontWeight: '700', color: Colors.amber, letterSpacing: 0.5, textTransform: 'uppercase' },
  chunkText: { fontSize: 14, lineHeight: 21, color: Colors.text },
});
