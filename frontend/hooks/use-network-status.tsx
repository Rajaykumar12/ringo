import React, { createContext, useContext, useEffect, useState } from 'react';
import NetInfo from '@react-native-community/netinfo';

interface NetworkStatus {
  isOnline: boolean;
}

const NetworkStatusContext = createContext<NetworkStatus | null>(null);

export function NetworkStatusProvider({ children }: { children: React.ReactNode }) {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setIsOnline(state.isConnected !== false && state.isInternetReachable !== false);
    });
    return unsubscribe;
  }, []);

  return (
    <NetworkStatusContext.Provider value={{ isOnline }}>
      {children}
    </NetworkStatusContext.Provider>
  );
}

export function useNetworkStatus(): NetworkStatus {
  const ctx = useContext(NetworkStatusContext);
  if (!ctx) throw new Error('useNetworkStatus must be used within a NetworkStatusProvider');
  return ctx;
}
