import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Radii, Shadows, useThemeColors } from '@/constants/theme';
import { getAdminStats, getAdminLogs, AdminStats, AdminLogEntry } from '@/services/api';

const ADMIN_KEY_STORAGE = 'ringo:admin_key';

export default function AdminScreen() {
  const router = useRouter();
  const Colors = useThemeColors();
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);

  const [adminKey, setAdminKey] = useState('');
  const [keyInput, setKeyInput] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [logs, setLogs] = useState<AdminLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    AsyncStorage.getItem(ADMIN_KEY_STORAGE).then((stored) => {
      if (stored) {
        setAdminKey(stored);
        setKeyInput(stored);
      }
      setLoaded(true);
    });
  }, []);

  const fetchData = useCallback(async (key: string) => {
    if (!key) return;
    setLoading(true);
    setError('');
    try {
      const [statsRes, logsRes] = await Promise.all([
        getAdminStats(key, 7),
        getAdminLogs(key, 1, 50),
      ]);
      setStats(statsRes);
      setLogs(logsRes);
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 401) setError('Invalid admin key.');
      else if (status === 503) setError('Admin dashboard not configured on the server (ADMIN_API_KEY unset).');
      else setError('Failed to load admin data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loaded && adminKey) fetchData(adminKey);
  }, [loaded, adminKey, fetchData]);

  const handleSaveKey = () => {
    const trimmed = keyInput.trim();
    setAdminKey(trimmed);
    AsyncStorage.setItem(ADMIN_KEY_STORAGE, trimmed);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={[styles.header, Shadows.card]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.closeBtn} accessibilityLabel="Close admin dashboard">
          <Ionicons name="close" size={20} color={Colors.textMuted} />
        </TouchableOpacity>
        <Text style={styles.title}>Admin Dashboard</Text>
        <View style={styles.closeBtn} />
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => fetchData(adminKey)} />}
      >
        <Text style={styles.sectionLabel}>Admin key</Text>
        <View style={styles.card}>
          <View style={styles.keyRow}>
            <TextInput
              style={styles.keyInput}
              placeholder="Enter ADMIN_API_KEY"
              placeholderTextColor={Colors.textFaint}
              value={keyInput}
              onChangeText={setKeyInput}
              secureTextEntry
              autoCapitalize="none"
            />
            <TouchableOpacity onPress={handleSaveKey} style={styles.saveBtn} accessibilityLabel="Save admin key">
              <Ionicons name="checkmark" size={18} color="#FFF" />
            </TouchableOpacity>
          </View>
        </View>

        {!!error && <Text style={styles.errorText}>{error}</Text>}
        {loading && !stats && <ActivityIndicator color={Colors.amber} style={{ marginTop: 20 }} />}

        {stats?.configured && (
          <>
            <Text style={styles.sectionLabel}>Last 7 days</Text>
            <View style={styles.statsGrid}>
              <StatTile label="Total calls" value={stats.total_calls ?? 0} Colors={Colors} />
              <StatTile label="Avg latency" value={stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : '—'} Colors={Colors} />
              <StatTile label="Thumbs up" value={stats.thumbs_up ?? 0} Colors={Colors} />
              <StatTile label="Thumbs down" value={stats.thumbs_down ?? 0} Colors={Colors} />
              <StatTile label="Faithfulness" value={stats.avg_faithfulness ?? '—'} Colors={Colors} />
              <StatTile label="Relevance" value={stats.avg_answer_relevance ?? '—'} Colors={Colors} />
            </View>

            {stats.language_breakdown && Object.keys(stats.language_breakdown).length > 0 && (
              <>
                <Text style={styles.sectionLabel}>Languages</Text>
                <View style={styles.card}>
                  {Object.entries(stats.language_breakdown).map(([lang, count]) => (
                    <View key={lang} style={styles.langRow}>
                      <Text style={styles.langName}>{lang}</Text>
                      <Text style={styles.langCount}>{count}</Text>
                    </View>
                  ))}
                </View>
              </>
            )}

            <Text style={styles.sectionLabel}>Recent queries (last 24h)</Text>
            {logs.length === 0 ? (
              <Text style={styles.emptyText}>No log entries yet.</Text>
            ) : (
              logs.map((log) => (
                <View key={log.RowKey} style={styles.logCard}>
                  <Text style={styles.logQuery} numberOfLines={2}>{log.query}</Text>
                  <Text style={styles.logResponse} numberOfLines={3}>{log.response}</Text>
                  <View style={styles.logMeta}>
                    <Text style={styles.logMetaText}>{log.language} · {log.latency_ms}ms</Text>
                    {log.user_rating != null && (
                      <Ionicons
                        name={log.user_rating === 1 ? 'thumbs-up-outline' : 'thumbs-down-outline'}
                        size={12}
                        color={Colors.textFaint}
                      />
                    )}
                  </View>
                </View>
              ))
            )}
          </>
        )}

        {stats && !stats.configured && (
          <Text style={styles.errorText}>
            Server has no AZURE_STORAGE_CONNECTION_STRING configured — no logs to show.
          </Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatTile({ label, value, Colors }: { label: string; value: string | number; Colors: ReturnType<typeof useThemeColors> }) {
  const styles = React.useMemo(() => createStyles(Colors), [Colors]);
  return (
    <View style={styles.statTile}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const createStyles = (Colors: ReturnType<typeof useThemeColors>) => StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: Colors.surface,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: Radii.full,
    backgroundColor: Colors.surfaceWarm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: { fontSize: 17, fontWeight: '700', color: Colors.text },
  content: { padding: 16, gap: 8, paddingBottom: 40 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: 12,
    marginBottom: 6,
    marginLeft: 4,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    overflow: 'hidden',
    ...Shadows.card,
  },
  keyRow: { flexDirection: 'row', alignItems: 'center', padding: 10, gap: 8 },
  keyInput: {
    flex: 1,
    fontSize: 14,
    color: Colors.text,
    paddingHorizontal: 10,
    paddingVertical: 8,
    backgroundColor: Colors.surfaceWarm,
    borderRadius: Radii.sm,
  },
  saveBtn: {
    width: 36,
    height: 36,
    borderRadius: Radii.full,
    backgroundColor: Colors.amber,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: { color: Colors.error, fontSize: 13, marginTop: 10, marginLeft: 4 },
  emptyText: { color: Colors.textMuted, fontSize: 13, marginTop: 8, marginLeft: 4 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  statTile: {
    flexBasis: '31%',
    flexGrow: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    paddingVertical: 14,
    alignItems: 'center',
    ...Shadows.card,
  },
  statValue: { fontSize: 18, fontWeight: '700', color: Colors.text },
  statLabel: { fontSize: 11, color: Colors.textMuted, marginTop: 2, textAlign: 'center' },
  langRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  langName: { fontSize: 14, color: Colors.text, textTransform: 'uppercase' },
  langCount: { fontSize: 14, fontWeight: '600', color: Colors.textMuted },
  logCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: 12,
    marginBottom: 8,
    ...Shadows.card,
  },
  logQuery: { fontSize: 14, fontWeight: '600', color: Colors.text },
  logResponse: { fontSize: 13, color: Colors.textMuted, marginTop: 4 },
  logMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  logMetaText: { fontSize: 11, color: Colors.textFaint },
});
