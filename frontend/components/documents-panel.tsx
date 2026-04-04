import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import { listDocuments, uploadDocument, deleteDocument, DocumentInfo } from '@/services/api';
import { Colors, Radii, Shadows } from '@/constants/theme';

interface DocumentsPanelProps {
  visible: boolean;
  onClose: () => void;
}

const SUPPORTED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'text/markdown',
  'text/plain',
];

const TYPE_ICON: Record<string, { name: string; color: string; bg: string }> = {
  pdf:      { name: 'document-text', color: Colors.amber,     bg: Colors.amberLight },
  pptx:     { name: 'easel',         color: Colors.teal,      bg: Colors.tealLight },
  markdown: { name: 'code-slash',    color: Colors.textMuted, bg: Colors.surfaceWarm },
};

export function DocumentsPanel({ visible, onClose }: DocumentsPanelProps) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

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

  const handlePick = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: SUPPORTED_MIME_TYPES,
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (result.canceled || !result.assets?.length) return;

      const asset = result.assets[0];
      setUploading(true);
      setUploadProgress(0);
      await uploadDocument(asset.uri, asset.name, asset.mimeType ?? 'application/octet-stream', setUploadProgress);
      await fetchDocuments();
    } catch (e: any) {
      Alert.alert('Upload Failed', e?.response?.data?.detail ?? e?.message ?? 'Unknown error');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = (filename: string) => {
    Alert.alert('Remove Document', `Remove "${filename}" from the index?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteDocument(filename);
            await fetchDocuments();
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Delete failed');
          }
        },
      },
    ]);
  };

  const getTypeIcon = (type: string) => TYPE_ICON[type] ?? TYPE_ICON.markdown;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={styles.container}>
        {/* Header */}
        <View style={[styles.header, Shadows.card]}>
          <View style={styles.headerTitle}>
            <View style={styles.headerIconWrap}>
              <Ionicons name="folder-open" size={18} color={Colors.amber} />
            </View>
            <Text style={styles.title}>Documents</Text>
          </View>
          <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityLabel="Close documents panel">
            <Ionicons name="close" size={18} color={Colors.textMuted} />
          </TouchableOpacity>
        </View>

        <Text style={styles.subtitle}>Upload PDFs, PowerPoints, or Markdown to expand the knowledge base.</Text>

        {/* Upload button */}
        <TouchableOpacity
          style={[styles.uploadBtn, uploading && styles.uploadBtnDisabled]}
          onPress={handlePick}
          disabled={uploading}
          accessibilityLabel="Upload document"
        >
          {uploading ? (
            <View style={styles.uploadBtnInner}>
              <ActivityIndicator size="small" color="#FFF" />
              <Text style={styles.uploadBtnText}>
                Uploading{uploadProgress > 0 ? ` ${uploadProgress}%` : '…'}
              </Text>
            </View>
          ) : (
            <View style={styles.uploadBtnInner}>
              <Ionicons name="cloud-upload-outline" size={18} color="#FFF" />
              <Text style={styles.uploadBtnText}>Upload Document</Text>
            </View>
          )}
        </TouchableOpacity>

        <Text style={styles.hint}>PDF · PPTX · Markdown — max 20 MB</Text>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Content */}
        {loading ? (
          <View style={styles.centered}>
            <ActivityIndicator size="large" color={Colors.amber} />
          </View>
        ) : error ? (
          <View style={styles.centered}>
            <View style={styles.errorIconWrap}>
              <Ionicons name="alert-circle-outline" size={28} color={Colors.error} />
            </View>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity onPress={fetchDocuments} style={styles.retryBtn}>
              <Text style={styles.retryBtnText}>Try Again</Text>
            </TouchableOpacity>
          </View>
        ) : documents.length === 0 ? (
          <View style={styles.centered}>
            <View style={styles.emptyIconWrap}>
              <Ionicons name="folder-open-outline" size={36} color={Colors.amber} />
            </View>
            <Text style={styles.emptyTitle}>No documents yet</Text>
            <Text style={styles.emptySub}>Upload a file to get started.</Text>
          </View>
        ) : (
          <ScrollView contentContainerStyle={styles.list}>
            <Text style={styles.listHeader}>
              <Text style={styles.listHeaderDot}>● </Text>
              {documents.length} document{documents.length !== 1 ? 's' : ''} indexed
            </Text>
            {documents.map((doc) => {
              const icon = getTypeIcon(doc.type);
              return (
                <View key={doc.filename} style={[styles.docCard, Shadows.card]}>
                  <View style={[styles.docTypeIcon, { backgroundColor: icon.bg }]}>
                    <Ionicons name={icon.name as any} size={18} color={icon.color} />
                  </View>
                  <View style={styles.docInfo}>
                    <Text style={styles.docName} numberOfLines={1}>{doc.filename}</Text>
                    <Text style={styles.docMeta}>
                      {doc.type.toUpperCase()} · {doc.chunks} chunk{doc.chunks !== 1 ? 's' : ''}
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => handleDelete(doc.filename)}
                    style={styles.deleteBtn}
                    accessibilityLabel={`Remove ${doc.filename}`}
                  >
                    <Ionicons name="trash-outline" size={16} color={Colors.error} />
                  </TouchableOpacity>
                </View>
              );
            })}
          </ScrollView>
        )}
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: Colors.surface,
  },
  headerTitle: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerIconWrap: {
    width: 34,
    height: 34,
    borderRadius: Radii.sm,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: { fontSize: 17, fontWeight: '700', color: Colors.text },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: Radii.full,
    backgroundColor: Colors.surfaceWarm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  subtitle: { fontSize: 13, color: Colors.textMuted, paddingHorizontal: 16, paddingTop: 14, paddingBottom: 4 },
  uploadBtn: {
    margin: 16,
    marginBottom: 8,
    backgroundColor: Colors.amber,
    borderRadius: Radii.md,
    paddingVertical: 14,
    alignItems: 'center',
    ...Platform.select({
      ios: { shadowColor: Colors.amberDark, shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.3, shadowRadius: 8 },
      default: { elevation: 4 },
    }),
  },
  uploadBtnDisabled: { backgroundColor: '#E6A84A' },
  uploadBtnInner: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  uploadBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
  hint: { textAlign: 'center', fontSize: 12, color: Colors.textFaint },
  divider: { height: 1, backgroundColor: Colors.border, marginTop: 16 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12, paddingBottom: 40 },
  errorIconWrap: {
    width: 56,
    height: 56,
    borderRadius: Radii.full,
    backgroundColor: Colors.errorLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: { color: Colors.error, fontSize: 14, textAlign: 'center', maxWidth: 240 },
  retryBtn: { paddingHorizontal: 22, paddingVertical: 9, backgroundColor: Colors.amber, borderRadius: Radii.sm },
  retryBtnText: { color: '#FFF', fontWeight: '600', fontSize: 14 },
  emptyIconWrap: {
    width: 72,
    height: 72,
    borderRadius: Radii.xl,
    backgroundColor: Colors.amberLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: Colors.textMuted },
  emptySub: { fontSize: 13, color: Colors.textFaint },
  list: { padding: 16, gap: 10 },
  listHeader: { fontSize: 13, color: Colors.textMuted, marginBottom: 4 },
  listHeaderDot: { color: Colors.amber },
  docCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: 12,
    gap: 12,
  },
  docTypeIcon: {
    width: 40,
    height: 40,
    borderRadius: Radii.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  docInfo: { flex: 1 },
  docName: { fontSize: 14, fontWeight: '600', color: Colors.text },
  docMeta: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  deleteBtn: {
    width: 32,
    height: 32,
    borderRadius: Radii.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
