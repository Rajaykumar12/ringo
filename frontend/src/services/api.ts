import axios from 'axios';

// Set VITE_API_URL at build time to point at your backend (see .env.example).
// Local dev defaults to localhost:8000 with zero config; production build falls back
// to the page's own origin, which works when the backend is reverse-proxied behind
// the same host as the frontend.
const DEV_API_URL = 'http://localhost:8000';

if (!import.meta.env.VITE_API_URL && !import.meta.env.DEV) {
  console.warn('VITE_API_URL is not set — falling back to same-origin. Set it at build time to point at your backend.');
}

export const API_BASE_URL =
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? DEV_API_URL : window.location.origin);
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // [High #7] Increased from 30s to 60s for RAG + cold-start
});

// Retry only on network-level failures (no response received) or 5xx — never on 4xx,
// since those are client errors (validation, rate limit, etc.) that retrying won't fix.
const isRetryableError = (error: any) =>
  !error?.response || (error.response.status >= 500 && error.response.status < 600);

api.interceptors.response.use(undefined, async (error) => {
  const config = error?.config;
  if (!config || config.__retryCount >= 2 || !isRetryableError(error)) {
    throw error;
  }
  config.__retryCount = (config.__retryCount ?? 0) + 1;
  await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** (config.__retryCount - 1)));
  return api(config);
});

export class OfflineError extends Error {
  constructor() {
    super('You appear to be offline. Check your connection and try again.');
    this.name = 'OfflineError';
  }
}

export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  isAudio?: boolean;
  audio_data?: string;
  audio_available?: boolean;
  sources?: string[];
  imageUri?: string;
}

export interface ChatResponse {
  success: boolean;
  response: string;
  sources?: string[];
  user_transcription?: string;
}

export interface AudioChatResponse {
  transcription: string;
  responseText: string;
}

export const sendTextMessage = async (
  message: string,
  stream: boolean = false,
  session_id: string = 'default',
  signal?: AbortSignal
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('message', message);
  formData.append('stream', stream.toString());
  formData.append('session_id', session_id);

  const response = await api.post<ChatResponse>('/chat/text', formData, { signal });
  return response.data;
};

export const sendTextMessageStream = async (
  message: string,
  onChunk: (chunk: { type: string; value: string; sources?: string[] }) => void,
  session_id: string = 'default',
  signal?: AbortSignal
): Promise<void> => {
  const formData = new FormData();
  formData.append('message', message);
  formData.append('stream', 'true');
  formData.append('session_id', session_id);

  // A caller-provided signal (e.g. the "stop generating" button) must not disable the
  // timeout — combine them so an unreachable/hung backend can't block forever.
  const timeoutSignal = AbortSignal.timeout(60000);
  const combinedSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;

  const response = await fetch(`${API_BASE_URL}/chat/text`, {
    method: 'POST',
    body: formData,
    signal: combinedSignal,
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
  stream: boolean = false,
  session_id: string = 'default'
): Promise<AudioChatResponse> => {
  const formData = new FormData();

  // Web: audioUri is a blob: URL from MediaRecorder — fetch it first
  const response = await fetch(audioUri);
  const blob = await response.blob();
  formData.append('file', blob, 'audio.webm');

  formData.append('stream', stream.toString());
  formData.append('session_id', session_id);

  const apiResponse = await api.post('/chat/audio', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'json',
  });

  const data = apiResponse.data;
  return {
    transcription: data.transcription || '',
    responseText: data.response || '',
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

  if (imageUri.startsWith('blob:') || imageUri.startsWith('data:')) {
    const res = await fetch(imageUri);
    const blob = await res.blob();
    formData.append('image', blob, 'image.jpg');
  } else {
    formData.append('image', imageUri);
  }

  void mimeType;
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

  if (uri.startsWith('blob:') || uri.startsWith('data:')) {
    // Web: object/data URL from an <input type="file"> selection — fetch it first
    const res = await fetch(uri);
    const blob = await res.blob();
    formData.append('file', blob, filename);
  } else {
    formData.append('file', uri);
  }

  void mimeType;
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

export interface AdminStats {
  total_calls?: number;
  avg_latency_ms?: number | null;
  thumbs_up?: number;
  thumbs_down?: number;
  avg_faithfulness?: number | null;
  avg_answer_relevance?: number | null;
  avg_context_relevance?: number | null;
}

export interface AdminLogEntry {
  PartitionKey: string;
  RowKey: string;
  query: string;
  response: string;
  sources: string;
  latency_ms: number;
  timestamp: string;
  user_rating?: number;
  faithfulness?: number;
  answer_relevance?: number;
  context_relevance?: number;
}

export const getAdminStats = async (adminKey: string, days: number = 7): Promise<AdminStats> => {
  const response = await api.get<AdminStats>('/admin/stats', {
    params: { days },
    headers: { 'x-admin-key': adminKey },
  });
  return response.data;
};

export const getAdminLogs = async (
  adminKey: string,
  days: number = 1,
  limit: number = 100
): Promise<AdminLogEntry[]> => {
  const response = await api.get<{ logs: AdminLogEntry[] }>('/admin/logs', {
    params: { days, limit },
    headers: { 'x-admin-key': adminKey },
  });
  return response.data.logs;
};

// Generate TTS audio on-demand
export const generateTTS = async (
  text: string
): Promise<{ audio_data: string | null; audio_available: boolean }> => {
  const formData = new FormData();
  formData.append('text', text);

  const response = await api.post('/tts/generate', formData);
  return response.data;
};
