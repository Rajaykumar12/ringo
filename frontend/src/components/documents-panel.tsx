import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  IoFolderOpen, IoClose, IoCloudUploadOutline, IoAlertCircleOutline,
  IoFolderOpenOutline, IoTrashOutline, IoDocumentText, IoEasel, IoCodeSlash,
} from 'react-icons/io5';
import type { IconType } from 'react-icons';
import { listDocuments, uploadDocument, deleteDocument, DocumentInfo } from '@/services/api';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useTranslation } from '@/hooks/use-translation';
import styles from './documents-panel.module.css';

interface DocumentsPanelProps {
  visible: boolean;
  onClose: () => void;
}

const SUPPORTED_EXTENSIONS = '.pdf,.pptx,.md,.markdown,.txt';

const createTypeIcon = (Colors: ReturnType<typeof useThemeColors>): Record<string, { Icon: IconType; color: string; bg: string }> => ({
  pdf: { Icon: IoDocumentText, color: Colors.amber, bg: Colors.amberLight },
  pptx: { Icon: IoEasel, color: Colors.teal, bg: Colors.tealLight },
  markdown: { Icon: IoCodeSlash, color: Colors.textMuted, bg: Colors.surfaceWarm },
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
  const { t } = useTranslation();
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
      setError(t('documents.loadFailed'));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      window.alert(t('documents.fileTooLargeMessage', { filename: file.name, limit: MAX_DOCUMENT_SIZE_MB }));
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
      window.alert(getErrorMessage(err, t('documents.uploadFailedGeneric')));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async (filename: string) => {
    if (!window.confirm(t('documents.removeConfirm', { filename }))) return;
    try {
      await deleteDocument(filename);
      await fetchDocuments();
    } catch (e: any) {
      window.alert(getErrorMessage(e, t('documents.deleteFailed')));
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
        aria-label={t('documents.title')}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <div className={styles.headerIconWrap}>
              <IoFolderOpen size={18} color={Colors.amber} />
            </div>
            <h2 className={styles.title}>{t('documents.title')}</h2>
          </div>
          <button type="button" onClick={onClose} className={styles.closeBtn} aria-label={t('documents.close')}>
            <IoClose size={18} color={Colors.textMuted} />
          </button>
        </div>

        <p className={styles.subtitle}>{t('documents.subtitle')}</p>

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
          aria-label={t('documents.upload')}
        >
          {uploading ? (
            <div className={styles.uploadBtnInner}>
              <div className={styles.spinner} style={{ width: 16, height: 16, borderWidth: 2, borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.4)' }} />
              <span className={styles.uploadBtnText}>
                {t('documents.uploading')}{uploadProgress > 0 ? ` ${uploadProgress}%` : '…'}
              </span>
            </div>
          ) : (
            <div className={styles.uploadBtnInner}>
              <IoCloudUploadOutline size={18} color="#FFF" />
              <span className={styles.uploadBtnText}>{t('documents.upload')}</span>
            </div>
          )}
        </button>

        <p className={styles.hint}>{t('documents.hint')}</p>

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
            <button type="button" onClick={fetchDocuments} className={styles.retryBtn} aria-label={t('common.tryAgain')}>
              <span className={styles.retryBtnText}>{t('common.tryAgain')}</span>
            </button>
          </div>
        ) : documents.length === 0 ? (
          <div className={styles.centered}>
            <div className={styles.emptyIconWrap}>
              <IoFolderOpenOutline size={36} color={Colors.amber} />
            </div>
            <p className={styles.emptyTitle}>{t('documents.emptyTitle')}</p>
            <p className={styles.emptySub}>{t('documents.emptySub')}</p>
          </div>
        ) : (
          <div className={styles.list}>
            <p className={styles.listHeader}>
              <span className={styles.listHeaderDot}>● </span>
              {t('documents.indexedCount', { count: documents.length })}
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
                    aria-label={t('documents.remove', { filename: doc.filename })}
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
