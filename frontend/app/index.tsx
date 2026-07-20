import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';
import { useAppSettings } from '@/hooks/use-app-settings';
import { useConversations } from '@/hooks/use-conversations';
import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';
import { ChatMessages } from '@/components/chat-messages';
import { ChatInput, AttachedImage } from '@/components/chat-input';
import { LanguageSelector, Language } from '@/components/language-selector';
import { DocumentsPanel } from '@/components/documents-panel';
import { ConversationsPanel } from '@/components/conversations-panel';
import { Message, sendTextMessage, sendTextMessageStream, sendAudioMessage, sendImageMessage, AudioChatResponse, generateTTS } from '@/services/api';

export default function ChatScreen() {
  const router = useRouter();
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  const { defaultLanguage, streamingEnabled, loaded: settingsLoaded } = useAppSettings();
  const {
    activeId, activeConversation, loaded: conversationsLoaded, updateActiveMessages,
  } = useConversations();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<Language | 'auto'>('auto');
  const useStreaming = streamingEnabled;

  // Apply the persisted default language once settings finish loading, without
  // overriding a manual in-session selection made before that (dependency is
  // intentionally just `settingsLoaded`, not `defaultLanguage`).
  useEffect(() => {
    if (settingsLoaded) setSelectedLanguage(defaultLanguage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsLoaded]);

  // Session ID ties requests to the active conversation's backend-side memory.
  const sessionId = activeConversation?.sessionId ?? 'default';

  const [showDocuments, setShowDocuments] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [initStatus, setInitStatus] = useState('System initializing...');
  const [editingText, setEditingText] = useState('');
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load the active conversation's messages whenever the user switches chats.
  useEffect(() => {
    if (activeConversation) setMessages(activeConversation.messages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  // Persist messages back to the active conversation as the chat progresses.
  useEffect(() => {
    if (!conversationsLoaded || !activeId) return;
    updateActiveMessages(messages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  useEffect(() => {
    const checkHealth = async () => {
      const PRODUCTION_API_URL = 'https://adk-backend.yellowocean-31c6616a.centralindia.azurecontainerapps.io';
      const API_URL = process.env.EXPO_PUBLIC_API_URL || PRODUCTION_API_URL;
      try {
        const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(10000) });
        const data = await res.json();
        if (data.vector_store === 'ready') {
          setInitStatus('Ready');
        } else {
          setInitStatus('System ready (no documents indexed)');
        }
      } catch {
        setInitStatus('Backend unavailable — check your connection');
      } finally {
        setIsInitializing(false);
      }
    };
    checkHealth();
  }, []);

  // Audio playback state
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [currentSound, setCurrentSound] = useState<Audio.Sound | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGeneratingTTS, setIsGeneratingTTS] = useState(false);

  // Audio control functions
  const playMessageAudio = async (messageId: string, messageText: string, messageLang: string, cachedAudioData?: string) => {
    try {
      let audioData = cachedAudioData;

      // If no cached audio, generate it on-demand
      if (!audioData) {
        setIsGeneratingTTS(true);
        setPlayingMessageId(messageId); // Show loading state

        try {
          const ttsResponse = await generateTTS(messageText, messageLang);
          audioData = ttsResponse.audio_data || undefined;

          if (!audioData) {
            Alert.alert('Error', 'Failed to generate audio');
            setIsGeneratingTTS(false);
            setPlayingMessageId(null);
            return;
          }

          // Cache the audio in the message
          setMessages(prev => prev.map(msg =>
            msg.id === messageId
              ? { ...msg, audio_data: audioData, audio_available: true }
              : msg
          ));
        } catch (error) {
          console.error('TTS generation failed:', error);
          Alert.alert('Error', 'Failed to generate audio');
          setIsGeneratingTTS(false);
          setPlayingMessageId(null);
          return;
        } finally {
          setIsGeneratingTTS(false);
        }
      }

      // Stop current audio if any
      if (currentSound) {
        await currentSound.stopAsync();
        await currentSound.unloadAsync();
        setCurrentSound(null);
      }

      // Convert base64 to blob
      const binaryString = atob(audioData);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: 'audio/mp3' });
      const audioUrl = URL.createObjectURL(blob);

      // Create and play new audio
      const sound = new Audio.Sound();
      await sound.loadAsync({ uri: audioUrl });
      setCurrentSound(sound);
      setPlayingMessageId(messageId);
      setIsPlaying(true);
      await sound.playAsync();

      // Handle playback completion
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setIsPlaying(false);
          setPlayingMessageId(null);
          sound.unloadAsync();
          URL.revokeObjectURL(audioUrl);
          setCurrentSound(null);
        }
      });
    } catch (error) {
      console.error('Error playing audio:', error);
      Alert.alert('Error', 'Failed to play audio');
      setIsGeneratingTTS(false);
    }
  };

  const pauseMessageAudio = async () => {
    if (currentSound) {
      await currentSound.pauseAsync();
      setIsPlaying(false);
    }
  };

  const resumeMessageAudio = async () => {
    if (currentSound) {
      await currentSound.playAsync();
      setIsPlaying(true);
    }
  };

  // Handle text message send. `skipUserMessage` is used by regenerate, which
  // resends an existing user message's text without appending a new bubble.
  const handleSendText = async (
    text: string,
    options?: { skipUserMessage?: boolean; image?: AttachedImage }
  ) => {
    if (!options?.skipUserMessage) {
      const userMessage: Message = {
        id: Date.now().toString(),
        text,
        sender: 'user',
        timestamp: new Date(),
        imageUri: options?.image?.uri,
      };
      setMessages((prev) => [...prev, userMessage]);
    }
    setIsLoading(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      if (options?.image) {
        const response = await sendImageMessage(
          options.image.uri, text, options.image.mimeType, sessionId, controller.signal
        );
        const aiMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: response.response,
          sender: 'ai',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMessage]);
      } else if (useStreaming) {
        // Streaming mode
        const aiMessageId = (Date.now() + 1).toString();
        let streamedText = '';
        let detectedLang = selectedLanguage;

        // Create placeholder AI message
        const aiMessage: Message = {
          id: aiMessageId,
          text: '',
          sender: 'ai',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMessage]);

        await sendTextMessageStream(
          text,
          (chunk: { type: string; value: string; sources?: string[] }) => {
            if (chunk.type === 'language') {
              detectedLang = chunk.value as Language;
            } else if (chunk.type === 'sources') {
              // Capture sources as they arrive, before the response starts
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId ? { ...msg, sources: chunk.sources ?? [] } : msg
                )
              );
            } else if (chunk.type === 'content') {
              streamedText += chunk.value;
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId ? { ...msg, text: streamedText } : msg
                )
              );
            } else if (chunk.type === 'done') {
              // Merge sources from done chunk in case sources chunk arrived first (no-op if already set)
              if (chunk.sources && chunk.sources.length > 0) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMessageId ? { ...msg, sources: chunk.sources } : msg
                  )
                );
              }
              Speech.speak(streamedText, {
                language: detectedLang === 'en' ? 'en-US' :
                  detectedLang === 'hi' ? 'hi-IN' :
                    detectedLang === 'ta' ? 'ta-IN' : 'te-IN',
              });
            }
          },
          selectedLanguage === 'auto' ? undefined : selectedLanguage,
          sessionId,
          controller.signal
        );
      } else {
        // Non-streaming mode
        const response = await sendTextMessage(
          text,
          selectedLanguage === 'auto' ? undefined : selectedLanguage,
          false,
          sessionId,
          controller.signal
        );

        const aiMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: response.response,
          sender: 'ai',
          timestamp: new Date(),
          language: response.language,
          sources: response.sources,
        };
        setMessages((prev) => [...prev, aiMessage]);
      }
    } catch (error: any) {
      const wasStopped = error?.name === 'AbortError' || error?.code === 'ERR_CANCELED';
      if (!wasStopped) {
        console.error('Error sending text:', error);
        Alert.alert('Error', 'Failed to send message. Check your connection and API URL.');
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopGenerating = () => {
    abortControllerRef.current?.abort();
  };

  const handleEditMessage = (message: Message) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === message.id);
      return idx === -1 ? prev : prev.slice(0, idx);
    });
    setEditingText(message.text);
  };

  const handleRegenerate = (aiMessage: Message) => {
    const idx = messages.findIndex((m) => m.id === aiMessage.id);
    if (idx === -1) return;
    let precedingUserText = '';
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') {
        precedingUserText = messages[i].text;
        break;
      }
    }
    if (!precedingUserText) return;
    setMessages((prev) => prev.filter((m) => m.id !== aiMessage.id));
    handleSendText(precedingUserText, { skipUserMessage: true });
  };

  // Handle audio recording and sending
  const handleSendAudio = async () => {
    if (isRecording) {
      await stopRecordingAndSend();
    } else {
      await startRecording();
    }
  };

  const recordingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const MAX_RECORDING_MS = 120000; // 2 minutes

  const startRecording = async () => {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        Alert.alert('Permission Required', 'Please grant microphone permission');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording: newRecording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      setRecording(newRecording);
      setIsRecording(true);

      recordingTimeoutRef.current = setTimeout(() => {
        Alert.alert('Recording Limit Reached', 'Maximum recording length is 2 minutes.');
        stopRecordingAndSend();
      }, MAX_RECORDING_MS);
    } catch (error) {
      console.error('Failed to start recording:', error);
      Alert.alert('Error', 'Failed to start recording');
    }
  };

  const stopRecordingAndSend = async () => {
    if (!recording) return;

    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }

    try {
      setIsRecording(false);
      setIsLoading(true);

      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();

      if (!uri) {
        Alert.alert('Error', 'No audio recorded');
        return;
      }

      const userMessage: Message = {
        id: Date.now().toString(),
        text: 'Voice message',
        sender: 'user',
        timestamp: new Date(),
        isAudio: true,
      };
      setMessages((prev) => [...prev, userMessage]);

      const response = await sendAudioMessage(
        uri,
        selectedLanguage === 'auto' ? undefined : selectedLanguage,
        false,
        sessionId
      );

      if (response.transcription) {
        const transcriptionMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: response.transcription,
          sender: 'user',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, transcriptionMessage]);
      }

      const aiMessage: Message = {
        id: (Date.now() + 2).toString(),
        text: response.responseText,
        sender: 'ai',
        timestamp: new Date(),
        language: response.language,
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error sending audio:', error);
      Alert.alert('Error', 'Failed to send audio. Check your connection and API URL.');
    } finally {
      setIsLoading(false);
      setRecording(null);
    }
  };

  if (isInitializing || !conversationsLoaded) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.initContainer}>
          <View style={styles.initIconWrap}>
            <Ionicons name="sparkles" size={28} color={Colors.amber} />
          </View>
          <ActivityIndicator size="large" color={Colors.amber} />
          <Text style={styles.initText}>{initStatus}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <DocumentsPanel visible={showDocuments} onClose={() => setShowDocuments(false)} />
      <ConversationsPanel visible={showHistory} onClose={() => setShowHistory(false)} />

      <View style={[styles.header, Shadows.card]}>
        <View style={styles.headerControls}>
          <TouchableOpacity
            onPress={() => setShowHistory(true)}
            style={styles.iconBtn}
            accessibilityLabel="Chat history"
          >
            <Ionicons name="chatbubbles-outline" size={18} color={Colors.amber} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => setShowDocuments(true)}
            style={styles.iconBtn}
            accessibilityLabel="Manage documents"
          >
            <Ionicons name="folder-open-outline" size={18} color={Colors.amber} />
          </TouchableOpacity>
        </View>

        <Text style={styles.title}>AI Chat</Text>

        <View style={styles.headerControls}>
          <LanguageSelector selectedLanguage={selectedLanguage} onSelectLanguage={setSelectedLanguage} />
          <TouchableOpacity
            onPress={() => router.push('/settings')}
            style={styles.iconBtn}
            accessibilityLabel="Settings"
          >
            <Ionicons name="settings-outline" size={18} color={Colors.amber} />
          </TouchableOpacity>
        </View>
      </View>

      <KeyboardAvoidingView
        style={styles.chatContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        <ChatMessages
          messages={messages}
          onPlayAudio={playMessageAudio}
          onPauseAudio={pauseMessageAudio}
          onResumeAudio={resumeMessageAudio}
          playingMessageId={playingMessageId}
          isPlaying={isPlaying}
          isGeneratingTTS={isGeneratingTTS}
          onEditMessage={handleEditMessage}
          onRegenerate={handleRegenerate}
          isLoading={isLoading}
        />
        <ChatInput
          onSendText={(text, image) => handleSendText(text, { image })}
          onSendAudio={handleSendAudio}
          onStop={handleStopGenerating}
          isRecording={isRecording}
          isLoading={isLoading}
          editingText={editingText}
          onEditingTextConsumed={() => setEditingText('')}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 11,
    backgroundColor: Colors.surface,
    zIndex: 10,
  },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: Radii.sm,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    color: Colors.text,
    flex: 1,
    textAlign: 'center',
  },
  headerControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  chatContainer: { flex: 1 },
  initContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 18,
    backgroundColor: Colors.bg,
  },
  initIconWrap: {
    width: 72,
    height: 72,
    borderRadius: Radii.xl,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  initText: {
    fontSize: 15,
    color: Colors.textMuted,
  },
});
