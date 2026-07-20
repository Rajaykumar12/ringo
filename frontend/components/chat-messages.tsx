import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Platform,
  Image,
} from 'react-native';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import Markdown from 'react-native-markdown-display';
import { Message } from '@/services/api';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';

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
  onEditMessage,
  onRegenerate,
  isLoading,
}: ChatMessagesProps) {
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const markdownStyles = React.useMemo(() => createMarkdownStyles(Colors), [Colors]);
  const scrollViewRef = React.useRef<ScrollView>(null);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

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

  const handleCopy = async (message: Message) => {
    await Clipboard.setStringAsync(message.text);
    setCopiedId(message.id);
    setTimeout(() => setCopiedId((id) => (id === message.id ? null : id)), 1500);
  };

  const lastAIMessageId = [...messages].reverse().find((m) => m.sender === 'ai')?.id;

  const formatTime = (d: Date) =>
    new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <ScrollView
      ref={scrollViewRef}
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      {messages.map((message) => {
        const isUser = message.sender === 'user';
        const isPlayingThis = playingMessageId === message.id;
        const isLastAI = !isUser && message.id === lastAIMessageId;

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
                {message.imageUri && (
                  <Image source={{ uri: message.imageUri }} style={styles.attachedImage} />
                )}

                {isUser || !message.text ? (
                  <Text style={[styles.bubbleText, isUser ? styles.bubbleTextUser : styles.bubbleTextAI]}>
                    {message.text || (isUser ? '' : '…')}
                  </Text>
                ) : (
                  <Markdown style={markdownStyles}>{message.text}</Markdown>
                )}

                {message.isAudio && (
                  <View style={styles.audioLabel}>
                    <Ionicons name="mic" size={10} color={isUser ? 'rgba(255,255,255,0.7)' : Colors.textMuted} />
                    <Text style={[styles.audioLabelText, isUser && styles.audioLabelTextUser]}>Voice</Text>
                  </View>
                )}

                <Text style={[styles.timestamp, isUser && styles.timestampUser]}>
                  {formatTime(message.timestamp)}
                </Text>
              </View>

              {!!message.text && (
                <View style={[styles.actionRow, isUser && styles.actionRowUser]}>
                  <Pressable
                    onPress={() => handleCopy(message)}
                    style={styles.actionIcon}
                    accessibilityLabel="Copy message"
                  >
                    <Ionicons
                      name={copiedId === message.id ? 'checkmark' : 'copy-outline'}
                      size={12}
                      color={Colors.textFaint}
                    />
                  </Pressable>

                  {isUser && !isLoading && (
                    <Pressable
                      onPress={() => onEditMessage(message)}
                      style={styles.actionIcon}
                      accessibilityLabel="Edit and resend message"
                    >
                      <Ionicons name="pencil-outline" size={12} color={Colors.textFaint} />
                    </Pressable>
                  )}

                  {isLastAI && !isLoading && (
                    <Pressable
                      onPress={() => onRegenerate(message)}
                      style={styles.actionIcon}
                      accessibilityLabel="Regenerate response"
                    >
                      <Ionicons name="refresh-outline" size={12} color={Colors.textFaint} />
                    </Pressable>
                  )}
                </View>
              )}
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
  );
}

const createMarkdownStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  body: { fontSize: 15, lineHeight: 22, color: Colors.text },
  paragraph: { marginTop: 0, marginBottom: 6 },
  heading1: { fontSize: 19, fontWeight: '700', color: Colors.text, marginTop: 4, marginBottom: 6 },
  heading2: { fontSize: 17, fontWeight: '700', color: Colors.text, marginTop: 4, marginBottom: 6 },
  heading3: { fontSize: 16, fontWeight: '700', color: Colors.text, marginTop: 4, marginBottom: 4 },
  strong: { fontWeight: '700' },
  em: { fontStyle: 'italic' },
  link: { color: Colors.teal, textDecorationLine: 'underline' },
  bullet_list: { marginBottom: 4 },
  ordered_list: { marginBottom: 4 },
  list_item: { flexDirection: 'row', marginBottom: 2 },
  code_inline: {
    backgroundColor: Colors.surfaceWarm,
    color: Colors.text,
    fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
    fontSize: 13,
    paddingHorizontal: 4,
    borderRadius: 3,
  },
  code_block: {
    backgroundColor: Colors.surfaceWarm,
    color: Colors.text,
    fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
    fontSize: 13,
    borderRadius: Radii.sm,
    padding: 10,
    marginVertical: 4,
  },
  fence: {
    backgroundColor: Colors.surfaceWarm,
    color: Colors.text,
    fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
    fontSize: 13,
    borderRadius: Radii.sm,
    padding: 10,
    marginVertical: 4,
  },
  blockquote: {
    backgroundColor: Colors.surfaceWarm,
    borderLeftWidth: 3,
    borderLeftColor: Colors.amber,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginVertical: 4,
  },
  table: { borderWidth: 1, borderColor: Colors.border, borderRadius: Radii.sm, marginVertical: 4 },
  th: { padding: 6, fontWeight: '700', backgroundColor: Colors.surfaceWarm },
  td: { padding: 6 },
  hr: { backgroundColor: Colors.border, height: 1, marginVertical: 8 },
});

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  content: { padding: 16, paddingBottom: 4, gap: 4 },

  row: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: 12, maxWidth: '88%', gap: 8 },
  rowUser: { alignSelf: 'flex-end', flexDirection: 'row-reverse' },
  rowAI: { alignSelf: 'flex-start' },

  avatar: {
    width: 28,
    height: 28,
    borderRadius: Radii.full,
    backgroundColor: Colors.borderMid,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },

  bubbleCol: { flexShrink: 1 },
  bubble: { borderRadius: Radii.lg, padding: 12 },
  bubbleUser: {
    backgroundColor: Colors.amber,
    borderBottomRightRadius: Radii.sm,
    ...Shadows.card,
  },
  bubbleAI: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderBottomLeftRadius: Radii.sm,
    ...Shadows.card,
  },
  bubblePlaying: {
    borderWidth: 2,
    borderColor: Colors.amberDark,
  },

  bubbleText: { fontSize: 15, lineHeight: 22 },
  attachedImage: { width: 200, height: 200, borderRadius: Radii.md, marginBottom: 8 },
  bubbleTextUser: { color: '#FFFFFF' },
  bubbleTextAI: { color: Colors.text },

  audioLabel: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 4 },
  audioLabelText: { fontSize: 11, color: Colors.textMuted },
  audioLabelTextUser: { color: 'rgba(255,255,255,0.7)' },

  timestamp: { fontSize: 10, color: Colors.textFaint, marginTop: 5, alignSelf: 'flex-end' },
  timestampUser: { color: 'rgba(255,255,255,0.6)' },

  actionRow: { flexDirection: 'row', gap: 2, marginTop: 3, paddingHorizontal: 2 },
  actionRowUser: { justifyContent: 'flex-end' },
  actionIcon: { padding: 3, opacity: 0.55 },

  audioBtn: {
    width: 34,
    height: 34,
    borderRadius: Radii.full,
    backgroundColor: Colors.teal,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },
});
