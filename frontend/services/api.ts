import axios from 'axios';

// Update this to your backend URL
// For Azure: set EXPO_PUBLIC_API_URL env var during docker build
// For local dev: defaults to localhost:8000
const PRODUCTION_API_URL = 'https://adk-backend.yellowocean-31c6616a.centralindia.azurecontainerapps.io';

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || PRODUCTION_API_URL;
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // [High #7] Increased from 30s to 60s for RAG + cold-start
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
  sources?: string[];
  imageUri?: string;
}

export interface ChatResponse {
  success: boolean;
  response: string;
  language: string;
  sources?: string[];
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
  stream: boolean = false,
  session_id: string = 'default',
  signal?: AbortSignal
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('message', message);
  if (language) {
    formData.append('language', language);
  }
  formData.append('stream', stream.toString());
  formData.append('session_id', session_id);

  const response = await api.post<ChatResponse>('/chat/text', formData, { signal });
  return response.data;
};

export const sendTextMessageStream = async (
  message: string,
  onChunk: (chunk: { type: string; value: string; sources?: string[] }) => void,
  language?: string,
  session_id: string = 'default',
  signal?: AbortSignal
): Promise<void> => {
  const formData = new FormData();
  formData.append('message', message);
  if (language) {
    formData.append('language', language);
  }
  formData.append('stream', 'true');
  formData.append('session_id', session_id);

  const response = await fetch(`${API_BASE_URL}/chat/text`, {
    method: 'POST',
    body: formData,
    signal: signal ?? AbortSignal.timeout(60000),
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
  stream: boolean = false,
  session_id: string = 'default'
): Promise<AudioChatResponse> => {
  const formData = new FormData();

  // For web, we need to fetch the blob first
  if (typeof window !== 'undefined' && audioUri.startsWith('blob:')) {
    const response = await fetch(audioUri);
    const blob = await response.blob();
    formData.append('file', blob, 'audio.wav');
  } else {
    // React Native mobile — detect actual format from URI extension
    const ext = audioUri.split('.').pop()?.toLowerCase() ?? 'wav';
    const mimeType = ext === 'm4a' ? 'audio/mp4' : ext === 'mp3' ? 'audio/mpeg' : 'audio/wav';
    // @ts-ignore - React Native FormData supports file objects
    formData.append('file', {
      uri: audioUri,
      type: mimeType,
      name: `audio.${ext}`,
    } as any);
  }

  if (language) {
    formData.append('language', language);
  }
  formData.append('stream', stream.toString());
  formData.append('session_id', session_id);

  const response = await api.post('/chat/audio', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'json',
  });

  const data = response.data;
  return {
    transcription: data.transcription || '',
    responseText: data.response || '',
    language: data.language || language || 'en',
  };
};

export interface ImageChatResponse {
  response: string;
  sources?: string[];
}

export const sendImageMessage = async (
  imageUri: string,
  message: string,
  mimeType: string = 'image/jpeg',
  session_id: string = 'default',
  signal?: AbortSignal
): Promise<ImageChatResponse> => {
  const formData = new FormData();

  if (typeof window !== 'undefined' && (imageUri.startsWith('blob:') || imageUri.startsWith('data:'))) {
    const res = await fetch(imageUri);
    const blob = await res.blob();
    formData.append('image', blob, 'image.jpg');
  } else {
    // @ts-ignore - React Native FormData supports file objects
    formData.append('image', { uri: imageUri, type: mimeType, name: 'image.jpg' } as any);
  }

  formData.append('message', message);
  formData.append('session_id', session_id);

  const response = await api.post<ImageChatResponse>('/chat/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    signal,
  });
  return response.data;
};

export interface DocumentInfo {
  filename: string;
  chunks: number;
  type: string;
}

export const listDocuments = async (): Promise<DocumentInfo[]> => {
  const response = await api.get('/documents/list');
  return response.data.documents;
};

export const uploadDocument = async (
  uri: string,
  filename: string,
  mimeType: string,
  onProgress?: (pct: number) => void
): Promise<{ success: boolean; filename: string; message: string }> => {
  const formData = new FormData();

  if (typeof window !== 'undefined' && (uri.startsWith('blob:') || uri.startsWith('data:'))) {
    // Web: expo-document-picker returns a blob/data URL — fetch it first
    const res = await fetch(uri);
    const blob = await res.blob();
    formData.append('file', blob, filename);
  } else {
    // React Native mobile: pass the file object directly
    // @ts-ignore — React Native FormData supports file objects
    formData.append('file', { uri, name: filename, type: mimeType } as any);
  }

  const response = await api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  });
  return response.data;
};

export const deleteDocument = async (filename: string): Promise<void> => {
  await api.delete(`/documents/${encodeURIComponent(filename)}`);
};

export interface DocumentChunk {
  text: string;
  metadata: { source: string; type?: string; slide?: number; page?: number };
}

export const getDocumentChunks = async (
  source: string,
  query: string = ''
): Promise<{ source: string; chunks: DocumentChunk[] }> => {
  const params = new URLSearchParams({ source });
  if (query) params.append('query', query);
  const response = await api.get(`/documents/chunks?${params.toString()}`);
  return response.data;
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
