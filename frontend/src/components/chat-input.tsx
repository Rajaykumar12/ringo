import React, { useState, useRef } from 'react';
import { IoImageOutline, IoCloseCircle, IoStopCircle, IoSend, IoMic, IoStop } from 'react-icons/io5';
import { useThemeColors } from '@/hooks/use-theme-colors';
import styles from './chat-input.module.css';

export interface AttachedImage {
  uri: string;
  mimeType: string;
}

interface ChatInputProps {
  onSendText: (message: string, image?: AttachedImage) => void;
  onSendAudio: () => void;
  onStop: () => void;
  isRecording: boolean;
  isLoading: boolean;
  editingText: string;
  onEditingTextConsumed: () => void;
}

export function ChatInput({
  onSendText,
  onSendAudio,
  onStop,
  isRecording,
  isLoading,
  editingText,
  onEditingTextConsumed,
}: ChatInputProps) {
  const Colors = useThemeColors();
  const [message, setMessage] = useState('');
  const [focused, setFocused] = useState(false);
  const [attachedImage, setAttachedImage] = useState<AttachedImage | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (editingText) {
      setMessage(editingText);
      onEditingTextConsumed();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingText]);

  const handleSend = () => {
    if ((message.trim() || attachedImage) && !isLoading) {
      onSendText(message.trim(), attachedImage ?? undefined);
      setMessage('');
      setAttachedImage(null);
    }
  };

  const handleAttachImage = () => {
    fileInputRef.current?.click();
  };

  const handleImageSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const uri = URL.createObjectURL(file);
    setAttachedImage({ uri, mimeType: file.type || 'image/jpeg' });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasContent = Boolean(message.trim() || attachedImage);
  const buttonColor = isRecording ? Colors.error : hasContent ? Colors.amber : Colors.teal;
  const buttonSize = isRecording || !hasContent ? 24 : 20;

  return (
    <div className={styles.container}>
      {!isLoading && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className={styles.hiddenInput}
            onChange={handleImageSelected}
          />
          <button
            type="button"
            onClick={handleAttachImage}
            className={styles.attachButton}
            aria-label="Attach image"
          >
            <IoImageOutline size={22} color={Colors.textFaint} />
          </button>
        </>
      )}
      <div className={`${styles.inputWrapper} ${focused ? styles.inputWrapperFocused : ''}`}>
        {attachedImage && (
          <div className={styles.imagePreviewRow}>
            <img src={attachedImage.uri} className={styles.imagePreview} alt="" />
            <button
              type="button"
              onClick={() => setAttachedImage(null)}
              aria-label="Remove attached image"
              className={styles.removeImageButton}
            >
              <IoCloseCircle size={18} color={Colors.textFaint} />
            </button>
          </div>
        )}
        <textarea
          ref={textareaRef}
          className={styles.input}
          placeholder="Ask anything…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={1000}
          disabled={isLoading}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
      </div>

      {isLoading ? (
        <button
          type="button"
          onClick={onStop}
          className={`${styles.actionButton} ${styles.loadingButton}`}
          aria-label="Stop generating"
        >
          <IoStop size={18} color={Colors.error} />
        </button>
      ) : (
        <button
          type="button"
          onClick={hasContent ? handleSend : onSendAudio}
          className={styles.actionButton}
          style={{ backgroundColor: buttonColor }}
        >
          {isRecording ? (
            <IoStopCircle size={buttonSize} color="#FFFFFF" />
          ) : hasContent ? (
            <IoSend size={buttonSize} color="#FFFFFF" />
          ) : (
            <IoMic size={buttonSize} color="#FFFFFF" />
          )}
        </button>
      )}
    </div>
  );
}
