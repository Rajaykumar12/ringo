import { useCallback, useEffect, useState } from 'react';

export const ADMIN_KEY_STORAGE = 'ringo:admin_key';

/**
 * Reads/writes the operator's ADMIN_API_KEY, shared between the Admin
 * dashboard and the Documents panel — both call endpoints gated behind the
 * backend's `x-admin-key` check. Backed by sessionStorage (not localStorage)
 * so the key doesn't persist indefinitely across browser sessions; entering
 * it once in either panel unlocks the other for the rest of the tab session.
 */
export function useAdminKey() {
  const [adminKey, setAdminKeyState] = useState('');
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setAdminKeyState(window.sessionStorage.getItem(ADMIN_KEY_STORAGE) || '');
    setLoaded(true);
  }, []);

  const setAdminKey = useCallback((key: string) => {
    const trimmed = key.trim();
    setAdminKeyState(trimmed);
    if (trimmed) window.sessionStorage.setItem(ADMIN_KEY_STORAGE, trimmed);
    else window.sessionStorage.removeItem(ADMIN_KEY_STORAGE);
  }, []);

  return { adminKey, setAdminKey, loaded };
}
