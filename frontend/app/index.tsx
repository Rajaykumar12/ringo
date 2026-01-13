import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';
import { ChatMessages } from '@/components/chat-messages';
import { ChatInput } from '@/components/chat-input';
import { LanguageSelector, Language } from '@/components/language-selector';
import { Message, sendTextMessage, sendAudioMessage, AudioChatResponse } from '@/services/api';

export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<Language>('en');

  // Handle text message send
  const handleSendText = async (text: string) => {
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      text,
      sender: 'user',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await sendTextMessage(text, selectedLanguage);

      // Add AI response
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response,
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);

      // Speak the response
      Speech.speak(response.response, {
        language: selectedLanguage === 'en' ? 'en-US' : 
                  selectedLanguage === 'hi' ? 'hi-IN' :
                  selectedLanguage === 'ta' ? 'ta-IN' : 'te-IN',
      });
    } catch (error) {
      console.error('Error sending text:', error);
      Alert.alert('Error', 'Failed to send message. Check your connection and API URL.');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle audio recording and sending
  const handleSendAudio = async () => {
    if (isRecording) {
      await stopRecordingAndSend();
    } else {
      await startRecording();
    }
  };

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
    } catch (error) {
      console.error('Failed to start recording:', error);
      Alert.alert('Error', 'Failed to start recording');
    }
  };

  const stopRecordingAndSend = async () => {
    if (!recording) return;

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

      const response = await sendAudioMessage(uri, selectedLanguage);

      if (response.transcription) {
        const transcriptionMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: `You said: "${response.transcription}"`,
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

      // Play the audio response
      const sound = new Audio.Sound();
      const audioUrl = URL.createObjectURL(response.audioBlob);
      await sound.loadAsync({ uri: audioUrl });
      await sound.playAsync();
      
      // Clean up
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          sound.unloadAsync();
          URL.revokeObjectURL(audioUrl);
        }
      });
    } catch (error) {
      console.error('Error sending audio:', error);
      Alert.alert('Error', 'Failed to send audio. Check your connection and API URL.');
    } finally {
      setIsLoading(false);
      setRecording(null);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>AI Chat Assistant</Text>
        <LanguageSelector
          selectedLanguage={selectedLanguage}
          onSelectLanguage={setSelectedLanguage}
        />
      </View>

      <KeyboardAvoidingView
        style={styles.chatContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        <ChatMessages messages={messages} />
        <ChatInput
          onSendText={handleSendText}
          onSendAudio={handleSendAudio}
          isRecording={isRecording}
          isLoading={isLoading}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000000',
  },
  chatContainer: {
    flex: 1,
  },
});
