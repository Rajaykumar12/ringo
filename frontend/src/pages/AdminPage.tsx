import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { IoClose, IoCheckmark, IoThumbsUpOutline, IoThumbsDownOutline } from 'react-icons/io5';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { useAdminKey } from '@/hooks/use-admin-key';
import { getAdminStats, getAdminLogs, AdminStats, AdminLogEntry } from '@/services/api';
import styles from './AdminPage.module.css';

export default function AdminPage() {
  const navigate = useNavigate();
  const Colors = useThemeColors();

  const { adminKey, setAdminKey, loaded } = useAdminKey();
  const [keyInput, setKeyInput] = useState('');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [logs, setLogs] = useState<AdminLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (loaded) setKeyInput(adminKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

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
    setAdminKey(keyInput);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <button type="button" onClick={() => navigate(-1)} className={styles.closeBtn} aria-label="Close admin dashboard">
          <IoClose size={20} color={Colors.textMuted} />
        </button>
        <h1 className={styles.title}>Admin Dashboard</h1>
        <div className={styles.closeBtn} style={{ visibility: 'hidden' }} />
      </div>

      <div className={styles.content}>
        <div className={styles.sectionLabel}>Admin key</div>
        <div className={styles.card}>
          <div className={styles.keyRow}>
            <input
              className={styles.keyInput}
              placeholder="Enter ADMIN_API_KEY"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              type="password"
              autoCapitalize="none"
            />
            <button type="button" onClick={handleSaveKey} className={styles.saveBtn} aria-label="Save admin key">
              <IoCheckmark size={18} color="#FFF" />
            </button>
          </div>
        </div>

        {!!error && <p className={styles.errorText}>{error}</p>}
        {loading && !stats && <div className={styles.spinner} />}

        {stats && (
          <>
            <div className={styles.sectionLabel}>Last 7 days</div>
            <div className={styles.statsGrid}>
              <StatTile label="Total calls" value={stats.total_calls ?? 0} />
              <StatTile label="Avg latency" value={stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : '—'} />
              <StatTile label="Thumbs up" value={stats.thumbs_up ?? 0} />
              <StatTile label="Thumbs down" value={stats.thumbs_down ?? 0} />
              <StatTile label="Faithfulness" value={stats.avg_faithfulness ?? '—'} />
              <StatTile label="Relevance" value={stats.avg_answer_relevance ?? '—'} />
            </div>

            <div className={styles.sectionLabel}>Recent queries (last 24h)</div>
            {logs.length === 0 ? (
              <p className={styles.emptyText}>No log entries yet.</p>
            ) : (
              logs.map((log) => (
                <div key={log.RowKey} className={styles.logCard}>
                  <p className={styles.logQuery}>{log.query}</p>
                  <p className={styles.logResponse}>{log.response}</p>
                  <div className={styles.logMeta}>
                    <span className={styles.logMetaText}>{log.latency_ms}ms</span>
                    {log.user_rating != null && (
                      log.user_rating === 1
                        ? <IoThumbsUpOutline size={12} color={Colors.textFaint} />
                        : <IoThumbsDownOutline size={12} color={Colors.textFaint} />
                    )}
                  </div>
                </div>
              ))
            )}
          </>
        )}

      </div>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.statTile}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}
