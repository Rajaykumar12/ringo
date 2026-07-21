import React, { Component, type ReactNode } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import { IoAlertCircleOutline } from 'react-icons/io5';

import { useThemeColors } from '@/hooks/use-theme-colors';
import { SettingsProvider } from '@/hooks/use-app-settings';
import { ConversationsProvider } from '@/hooks/use-conversations';
import { NetworkStatusProvider } from '@/hooks/use-network-status';
import { useTranslation } from '@/hooks/use-translation';
import ChatPage from '@/pages/ChatPage';
import SettingsPage from '@/pages/SettingsPage';
import AdminPage from '@/pages/AdminPage';
import styles from './App.module.css';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

type ErrorBoundaryProps = {
  children: ReactNode;
  colors: ReturnType<typeof useThemeColors>;
  t: (key: string) => string;
};

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Uncaught rendering error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      const { t, colors } = this.props;
      return (
        <div className={styles.container}>
          <div className={styles.iconWrap}>
            <IoAlertCircleOutline size={32} color={colors.amber} />
          </div>
          <h1 className={styles.title}>{t('errorBoundary.title')}</h1>
          <p className={styles.message}>{t('errorBoundary.message')}</p>
          <button
            type="button"
            className={styles.button}
            onClick={() => this.setState({ hasError: false, error: null })}
            aria-label={t('errorBoundary.tryAgain')}
          >
            {t('errorBoundary.tryAgain')}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <SettingsProvider>
      <NetworkStatusProvider>
        <ConversationsProvider>
          <AppInner />
        </ConversationsProvider>
      </NetworkStatusProvider>
    </SettingsProvider>
  );
}

function AppInner() {
  const colors = useThemeColors();
  const { t } = useTranslation();

  return (
    <ErrorBoundary colors={colors} t={t}>
      <HashRouter>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  );
}
