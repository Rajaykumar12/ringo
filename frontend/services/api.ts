import axios from 'axios';

// Update this to your backend URL
// For local development: use your machine's IP address (not localhost)
// e.g., "http://192.168.1.100:8000" or use ngrok for public URL
export const API_BASE_URL = 'http://localhost:8000'; // Change this!

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
}

export interface ChatResponse {
  success: boolean;
  response: string;
  language: string;
  user_transcription?: string;
  audio_available?: boolean;
}

export interface AudioChatResponse {
  audioBlob: Blob;
  transcription: string;
  responseText: string;
  language: string;
}

export const sendTextMessage = async (
  message: string,
  language: string = 'en'
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('message', message);
  formData.append('language', language);

  const response = await api.post<ChatResponse>('/chat/text', formData);
  return response.data;
};

export const sendAudioMessage = async (
  audioUri: string,
  language: string = 'en'
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
  
  formData.append('language', language);

  const response = await api.post('/chat/audio', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    responseType: 'blob', // Expect binary audio response
  });
  
  // Extract metadata from headers
  const transcription = response.headers['x-transcription'] || '';
  const responseText = response.headers['x-response-text'] || '';
  const responseLang = response.headers['x-language'] || language;
  
  return {
    audioBlob: response.data,
    transcription,
    responseText,
    language: responseLang,
  };
};
