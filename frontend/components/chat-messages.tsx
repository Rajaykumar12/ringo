import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Message } from '@/services/api';

interface ChatMessagesProps {
  messages: Message[];
  onPlayAudio: (messageId: string, messageText: string, messageLang: string, cachedAudioData?: string) => void;
  onPauseAudio: () => void;
  onResumeAudio: () => void;
  playingMessageId: string | null;
  isPlaying: boolean;
  isGeneratingTTS: boolean;
}

export function ChatMessages({
  messages,
  onPlayAudio,
  onPauseAudio,
  onResumeAudio,
  playingMessageId,
  isPlaying,
  isGeneratingTTS
}: ChatMessagesProps) {
  const scrollViewRef = React.useRef<ScrollView>(null);

  React.useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  const handleAudioButtonPress = (message: Message) => {
    const messageLang = message.language || 'en';

    if (playingMessageId === message.id) {
      // Same message - toggle play/pause
      if (isPlaying) {
        onPauseAudio();
      } else {
        onResumeAudio();
      }
    } else {
      // Different message - play new audio (will generate if needed)
      onPlayAudio(message.id, message.text, messageLang, message.audio_data);
    }
  };

  return (
    <ScrollView
      ref={scrollViewRef}
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
    >
      {messages.map((message) => (
        <View
          key={message.id}
          style={[
            styles.messageRow,
            message.sender === 'user' ? styles.userMessageRow : styles.aiMessageRow,
          ]}
        >
          <View
            style={[
              styles.messageContainer,
              message.sender === 'user' ? styles.userMessage : styles.aiMessage,
              playingMessageId === message.id && styles.playingMessage,
            ]}
          >
            <Text
              style={[
                styles.messageText,
                message.sender === 'user' ? styles.userText : styles.aiText,
              ]}
            >
              {message.text}
            </Text>
            {message.isAudio && (
              <Text style={styles.audioLabel}>Voice Message</Text>
            )}

            <Text style={styles.timestamp}>
              {message.timestamp.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </Text>
          </View>

          {/* Audio control button outside message bubble for AI messages */}
          {message.sender === 'ai' && (
            <TouchableOpacity
              onPress={() => handleAudioButtonPress(message)}
              style={styles.audioButton}
              disabled={isGeneratingTTS && playingMessageId === message.id}
            >
              {isGeneratingTTS && playingMessageId === message.id ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : playingMessageId === message.id && isPlaying ? (
                <Ionicons name="pause" size={20} color="#FFFFFF" />
              ) : (
                <Ionicons name="play" size={20} color="#FFFFFF" />
              )}
            </TouchableOpacity>
          )}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 8,
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginBottom: 12,
    maxWidth: '85%',
  },
  userMessageRow: {
    alignSelf: 'flex-end',
    flexDirection: 'row-reverse',
  },
  aiMessageRow: {
    alignSelf: 'flex-start',
  },
  messageContainer: {
    flex: 1,
    padding: 12,
    borderRadius: 16,
  },
  userMessage: {
    backgroundColor: '#007AFF',
  },
  aiMessage: {
    backgroundColor: '#E9ECEF',
  },
  playingMessage: {
    borderWidth: 2,
    borderColor: '#4CAF50',
  },
  messageText: {
    fontSize: 16,
    lineHeight: 22,
  },
  userText: {
    color: '#FFFFFF',
  },
  aiText: {
    color: '#000000',
  },
  audioLabel: {
    fontSize: 12,
    marginTop: 4,
    opacity: 0.7,
  },
  timestamp: {
    fontSize: 11,
    marginTop: 4,
    opacity: 0.6,
  },
  audioButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#9E9E9E',
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
});
