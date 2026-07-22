import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { IoMenuOutline, IoCloudOfflineOutline, IoSparkles } from 'react-icons/io5';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useAppSettings } from '@/hooks/use-app-settings';
import { useConversations } from '@/hooks/use-conversations';
import { useNetworkStatus } from '@/hooks/use-network-status';
import { ChatMessages } from '@/components/chat-messages';
import { ChatInput, AttachedImage } from '@/components/chat-input';
import { DocumentsPanel } from '@/components/documents-panel';
import { ConversationsPanel } from '@/components/conversations-panel';
import { HeaderMenu } from '@/components/header-menu';
import {
  API_BASE_URL, Message, sendTextMessage, sendTextMessageStream, sendAudioMessage,
  sendImageMessage, generateTTS, OfflineError, toImageUrl,
} from '@/services/api';
import styles from './ChatPage.module.css';

export default function ChatPage() {
  const navigate = useNavigate();
  const Colors = useThemeColors();
  const { streamingEnabled } = useAppSettings();
  const { isOnline } = useNetworkStatus();
  const {
    activeId, activeConversation, loaded: conversationsLoaded, updateActiveMessages,
  } = useConversations();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const useStreaming = streamingEnabled;

  // Session ID ties requests to the active conversation's backend-side memory.
  const sessionId = activeConversation?.sessionId ?? 'default';

  const [showDocuments, setShowDocuments] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
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
      try {
        const res = await fetch(`${API_BASE_URL}/health`, { signal: AbortSignal.timeout(10000) });
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
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGeneratingTTS, setIsGeneratingTTS] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  const cleanupAudio = () => {
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    audioRef.current = null;
  };

  // Audio control functions
  const playMessageAudio = async (messageId: string, messageText: string, cachedAudioData?: string) => {
    try {
      let audioData = cachedAudioData;

      if (!audioData) {
        setIsGeneratingTTS(true);
        setPlayingMessageId(messageId);

        try {
          const ttsResponse = await generateTTS(messageText);
          audioData = ttsResponse.audio_data || undefined;

          if (!audioData) {
            window.alert('Failed to generate audio');
            setIsGeneratingTTS(false);
            setPlayingMessageId(null);
            return;
          }

          setMessages((prev) => prev.map((msg) =>
            msg.id === messageId
              ? { ...msg, audio_data: audioData, audio_available: true }
              : msg
          ));
        } catch (error) {
          console.error('TTS generation failed:', error);
          window.alert('Failed to generate audio');
          setIsGeneratingTTS(false);
          setPlayingMessageId(null);
          return;
        } finally {
          setIsGeneratingTTS(false);
        }
      }

      if (audioRef.current) {
        audioRef.current.pause();
        cleanupAudio();
      }

      const binaryString = atob(audioData);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: 'audio/mp3' });
      const audioUrl = URL.createObjectURL(blob);
      audioUrlRef.current = audioUrl;

      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      setPlayingMessageId(messageId);
      setIsPlaying(true);

      audio.addEventListener('ended', () => {
        setIsPlaying(false);
        setPlayingMessageId(null);
        cleanupAudio();
      });

      await audio.play();
    } catch (error) {
      console.error('Error playing audio:', error);
      window.alert('Failed to play audio');
      setIsGeneratingTTS(false);
    }
  };

  const pauseMessageAudio = async () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const resumeMessageAudio = async () => {
    if (audioRef.current) {
      await audioRef.current.play();
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
      if (!isOnline) {
        throw new OfflineError();
      }
      if (options?.image) {
        const response = await sendImageMessage(
          options.image.uri, text, options.image.mimeType, sessionId, controller.signal
        );
        const aiMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: response.response,
          sender: 'ai',
          timestamp: new Date(),
          imageUris: response.images?.map(toImageUrl),
        };
        setMessages((prev) => [...prev, aiMessage]);
      } else if (useStreaming) {
        const aiMessageId = (Date.now() + 1).toString();
        let streamedText = '';

        const aiMessage: Message = {
          id: aiMessageId,
          text: '',
          sender: 'ai',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMessage]);

        await sendTextMessageStream(
          text,
          (chunk: { type: string; value: string; sources?: string[]; images?: string[] }) => {
            if (chunk.type === 'sources') {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId ? { ...msg, sources: chunk.sources ?? [] } : msg
                )
              );
            } else if (chunk.type === 'images') {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId
                    ? { ...msg, imageUris: (chunk.images ?? []).map(toImageUrl) }
                    : msg
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
              if (chunk.sources && chunk.sources.length > 0) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMessageId ? { ...msg, sources: chunk.sources } : msg
                  )
                );
              }
              if (chunk.images && chunk.images.length > 0) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMessageId
                      ? { ...msg, imageUris: chunk.images!.map(toImageUrl) }
                      : msg
                  )
                );
              }
              if ('speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(streamedText);
                utterance.lang = 'en-US';
                window.speechSynthesis.speak(utterance);
              }
            }
          },
          sessionId,
          controller.signal
        );
      } else {
        const response = await sendTextMessage(
          text,
          false,
          sessionId,
          controller.signal
        );

        const aiMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: response.response,
          sender: 'ai',
          timestamp: new Date(),
          sources: response.sources,
          imageUris: response.images?.map(toImageUrl),
        };
        setMessages((prev) => [...prev, aiMessage]);
      }
    } catch (error: any) {
      const wasStopped = error?.name === 'AbortError' || error?.code === 'ERR_CANCELED';
      if (!wasStopped) {
        console.error('Error sending text:', error);
        if (error instanceof OfflineError || !isOnline) {
          window.alert('Reconnect and try again.');
        } else {
          window.alert('Failed to send message. Check your connection and API URL.');
        }
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

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const MAX_RECORDING_MS = 120000; // 2 minutes

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      recordedChunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);

      recordingTimeoutRef.current = setTimeout(() => {
        window.alert('Maximum recording length is 2 minutes.');
        stopRecordingAndSend();
      }, MAX_RECORDING_MS);
    } catch (error) {
      console.error('Failed to start recording:', error);
      window.alert('Failed to start recording');
    }
  };

  const stopRecordingAndSend = async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;

    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }

    try {
      setIsRecording(false);
      setIsLoading(true);

      const blob: Blob = await new Promise((resolve) => {
        recorder.addEventListener('stop', () => {
          resolve(new Blob(recordedChunksRef.current, { type: recorder.mimeType || 'audio/webm' }));
        }, { once: true });
        recorder.stop();
      });
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;

      if (!blob.size) {
        window.alert('No audio recorded');
        return;
      }
      const uri = URL.createObjectURL(blob);

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
        false,
        sessionId
      );
      URL.revokeObjectURL(uri);

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
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error sending audio:', error);
      if (error instanceof OfflineError || !isOnline) {
        window.alert('Reconnect and try again.');
      } else {
        window.alert('Failed to send audio. Check your connection and API URL.');
      }
    } finally {
      setIsLoading(false);
      mediaRecorderRef.current = null;
    }
  };

  if (isInitializing || !conversationsLoaded) {
    return (
      <div className={styles.container}>
        <div className={styles.initContainer}>
          <div className={styles.initIconWrap}>
            <IoSparkles size={28} color={Colors.amber} />
          </div>
          <div className={styles.spinner} />
          <p className={styles.initText}>{initStatus}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <DocumentsPanel visible={showDocuments} onClose={() => setShowDocuments(false)} />
      <ConversationsPanel visible={showHistory} onClose={() => setShowHistory(false)} />
      <HeaderMenu
        visible={showMenu}
        onClose={() => setShowMenu(false)}
        onSelectHistory={() => setShowHistory(true)}
        onSelectDocuments={() => setShowDocuments(true)}
        onSelectSettings={() => navigate('/settings')}
      />

      <div className={styles.header}>
        <div className={styles.headerControls}>
          <button
            type="button"
            onClick={() => setShowMenu(true)}
            className={styles.iconBtn}
            aria-label="Menu"
          >
            <IoMenuOutline size={18} color={Colors.amber} />
          </button>
        </div>

        <h1 className={styles.title}>AI Chat</h1>

        <div className={styles.headerControls}>
          <div className={styles.iconBtn} style={{ visibility: 'hidden' }} />
        </div>
      </div>

      {!isOnline && (
        <div className={styles.offlineBanner} aria-live="polite">
          <IoCloudOfflineOutline size={14} color={Colors.textMuted} />
          <span className={styles.offlineBannerText}>You're offline</span>
        </div>
      )}

      <div className={styles.chatContainer}>
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
      </div>
    </div>
  );
}
