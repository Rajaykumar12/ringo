import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  IoFolderOpen, IoClose, IoCloudUploadOutline, IoAlertCircleOutline,
  IoFolderOpenOutline, IoTrashOutline, IoDocumentText, IoEasel, IoCodeSlash,
  IoGrid, IoGlobeOutline,
} from 'react-icons/io5';
import type { IconType } from 'react-icons';
import { listDocuments, uploadDocument, deleteDocument, DocumentInfo } from '@/services/api';
import { useThemeColors } from '@/hooks/use-theme-colors';
import styles from './documents-panel.module.css';

interface DocumentsPanelProps {
  visible: boolean;
  onClose: () => void;
}

const SUPPORTED_EXTENSIONS = '.pdf,.pptx,.md,.markdown,.txt,.docx,.html,.csv,.xlsx';

const createTypeIcon = (Colors: ReturnType<typeof useThemeColors>): Record<string, { Icon: IconType; color: string; bg: string }> => ({
  pdf: { Icon: IoDocumentText, color: Colors.amber, bg: Colors.amberLight },
  pptx: { Icon: IoEasel, color: Colors.teal, bg: Colors.tealLight },
  markdown: { Icon: IoCodeSlash, color: Colors.textMuted, bg: Colors.surfaceWarm },
  docx: { Icon: IoDocumentText, color: Colors.amber, bg: Colors.amberLight },
  html: { Icon: IoGlobeOutline, color: Colors.teal, bg: Colors.tealLight },
  tabular: { Icon: IoGrid, color: Colors.textMuted, bg: Colors.surfaceWarm },
});

const MAX_DOCUMENT_SIZE_MB = 20;

// Only surface the backend's `detail` for 4xx responses — those are deliberate,
// user-facing validation messages (bad file type/size). Anything else (5xx, network
// errors) could contain internal details, so fall back to a generic message.
function getErrorMessage(e: any, fallback: string): string {
  const status = e?.response?.status;
  const detail = e?.response?.data?.detail;
  if (status >= 400 && status < 500 && typeof detail === 'string') return detail;
  return fallback;
}

export function DocumentsPanel({ visible, onClose }: DocumentsPanelProps) {
  const Colors = useThemeColors();
  const TYPE_ICON = React.useMemo(() => createTypeIcon(Colors), [Colors]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocuments(await listDocuments());
    } catch {
      setError('Failed to load documents.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (visible) fetchDocuments(); }, [visible, fetchDocuments]);

  const handlePick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (file.size > MAX_DOCUMENT_SIZE_MB * 1024 * 1024) {
      window.alert(`"${file.name}" exceeds the ${MAX_DOCUMENT_SIZE_MB}MB limit.`);
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      const uri = URL.createObjectURL(file);
      await uploadDocument(uri, file.name, file.type || 'application/octet-stream', setUploadProgress);
      URL.revokeObjectURL(uri);
      await fetchDocuments();
    } catch (err: any) {
      window.alert(getErrorMessage(err, 'Something went wrong. Please try again.'));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`Remove "${filename}" from the index?`)) return;
    try {
      await deleteDocument(filename);
      await fetchDocuments();
    } catch (e: any) {
      window.alert(getErrorMessage(e, 'Delete failed. Please try again.'));
    }
  };

  const getTypeIcon = (type: string) => TYPE_ICON[type] ?? TYPE_ICON.markdown;

  if (!visible) return null;

  return (
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.container}
        role="dialog"
        aria-modal="true"
        aria-label="Documents"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <div className={styles.headerIconWrap}>
              <IoFolderOpen size={18} color={Colors.amber} />
            </div>
            <h2 className={styles.title}>Documents</h2>
          </div>
          <button type="button" onClick={onClose} className={styles.closeBtn} aria-label="Close documents panel">
            <IoClose size={18} color={Colors.textMuted} />
          </button>
        </div>

        <p className={styles.subtitle}>Upload documents, presentations, or spreadsheets to expand the knowledge base.</p>

        <input
          ref={fileInputRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS}
          className={styles.hiddenInput}
          onChange={handleFileSelected}
        />
        <button
          type="button"
          className={`${styles.uploadBtn} ${uploading ? styles.uploadBtnDisabled : ''}`}
          onClick={handlePick}
          disabled={uploading}
          aria-label="Upload Document"
        >
          {uploading ? (
            <div className={styles.uploadBtnInner}>
              <div className={styles.spinner} style={{ width: 16, height: 16, borderWidth: 2, borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.4)' }} />
              <span className={styles.uploadBtnText}>
                Uploading{uploadProgress > 0 ? ` ${uploadProgress}%` : '…'}
              </span>
            </div>
          ) : (
            <div className={styles.uploadBtnInner}>
              <IoCloudUploadOutline size={18} color="#FFF" />
              <span className={styles.uploadBtnText}>Upload Document</span>
            </div>
          )}
        </button>

        <p className={styles.hint}>PDF · PPTX · Markdown · DOCX · HTML · CSV · XLSX — max 20 MB</p>

        <div className={styles.divider} />

        {loading ? (
          <div className={styles.centered}>
            <div className={styles.spinner} />
          </div>
        ) : error ? (
          <div className={styles.centered}>
            <div className={styles.errorIconWrap}>
              <IoAlertCircleOutline size={28} color={Colors.error} />
            </div>
            <p className={styles.errorText}>{error}</p>
            <button type="button" onClick={fetchDocuments} className={styles.retryBtn} aria-label="Try Again">
              <span className={styles.retryBtnText}>Try Again</span>
            </button>
          </div>
        ) : documents.length === 0 ? (
          <div className={styles.centered}>
            <div className={styles.emptyIconWrap}>
              <IoFolderOpenOutline size={36} color={Colors.amber} />
            </div>
            <p className={styles.emptyTitle}>No documents yet</p>
            <p className={styles.emptySub}>Upload a file to get started.</p>
          </div>
        ) : (
          <div className={styles.list}>
            <p className={styles.listHeader}>
              <span className={styles.listHeaderDot}>● </span>
              {documents.length} documents indexed
            </p>
            {documents.map((doc) => {
              const { Icon, color, bg } = getTypeIcon(doc.type);
              return (
                <div key={doc.filename} className={styles.docCard}>
                  <div className={styles.docTypeIcon} style={{ backgroundColor: bg }}>
                    <Icon size={18} color={color} />
                  </div>
                  <div className={styles.docInfo}>
                    <div className={styles.docName}>{doc.filename}</div>
                    <div className={styles.docMeta}>{doc.type.toUpperCase()}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(doc.filename)}
                    className={styles.deleteBtn}
                    aria-label={`Remove ${doc.filename}`}
                  >
                    <IoTrashOutline size={16} color={Colors.error} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
