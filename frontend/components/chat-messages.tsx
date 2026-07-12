import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Platform,
} from 'react-native';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import { Message } from '@/services/api';
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
    ...Platform.select({
      ios: { shadowColor: Colors.amberDark, shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.25, shadowRadius: 6 },
      default: { elevation: 3 },
    }),
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
  bubbleTextUser: { color: '#FFFFFF' },
  bubbleTextAI: { color: Colors.text },

  audioLabel: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 4 },
  audioLabelText: { fontSize: 11, color: Colors.textMuted },
  audioLabelTextUser: { color: 'rgba(255,255,255,0.7)' },

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
});
