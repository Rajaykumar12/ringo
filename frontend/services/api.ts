import axios from 'axios';

// Update this to your backend URL
// For Azure: set EXPO_PUBLIC_API_URL env var during docker build
// For local dev: defaults to localhost:8000
const PRODUCTION_API_URL = 'https://adk-backend.yellowocean-31c6616a.centralindia.azurecontainerapps.io';

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || PRODUCTION_API_URL;

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  isAudio?: boolean;
  audio_data?: string;
  audio_available?: boolean;
  language?: string;
}

export interface ChatResponse {
  success: boolean;
  response: string;
  language: string;
  user_transcription?: string;
}

export interface AudioChatResponse {
  transcription: string;
  responseText: string;
  language: string;
}

export const sendTextMessage = async (
  message: string,
  language?: string,
  stream: boolean = false
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('message', message);
  if (language) {
    formData.append('language', language);
  }
  formData.append('stream', stream.toString());

  const response = await api.post<ChatResponse>('/chat/text', formData);
  return response.data;
};

export const sendTextMessageStream = async (
  message: string,
  onChunk: (chunk: { type: string; value: string }) => void,
  language?: string
): Promise<void> => {
  const formData = new FormData();
  formData.append('message', message);
  if (language) {
    formData.append('language', language);
  }
  formData.append('stream', 'true');

  const response = await fetch(`${API_BASE_URL}/chat/text`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) throw new Error('No reader available');

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          onChunk(data);
        } catch (e) {
          console.error('Failed to parse SSE data:', e);
        }
      }
    }
  }
};

export const sendAudioMessage = async (
  audioUri: string,
  language?: string,
  stream: boolean = false
): Promise<AudioChatResponse> => {
  const formData = new FormData();

  // For web, we need to fetch the blob first
  if (typeof window !== 'undefined' && audioUri.startsWith('blob:')) {
    const response = await fetch(audioUri);
    const blob = await response.blob();
    formData.append('file', blob, 'audio.wav');
  } else {
    // React Native mobile
    // @ts-ignore - React Native FormData supports file objects
    formData.append('file', {
      uri: audioUri,
      type: 'audio/wav',
      name: 'audio.wav',
    } as any);
  }

  if (language) {
    formData.append('language', language);
  }
  formData.append('stream', stream.toString());

  const response = await api.post('/chat/audio', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    responseType: 'json',
  });

  // Backend returns JSON with text response and transcription (no audio)
  const data = response.data;

  return {
    transcription: data.transcription || '',
    responseText: data.response || '',
    language: data.language || language || 'en',
  };
};

// Generate TTS audio on-demand
export const generateTTS = async (
  text: string,
  language: string
): Promise<{ audio_data: string | null; audio_available: boolean }> => {
  const formData = new FormData();
  formData.append('text', text);
  formData.append('language', language);

  const response = await api.post('/tts/generate', formData);
  return response.data;
};
