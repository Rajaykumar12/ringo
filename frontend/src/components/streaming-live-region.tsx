import React from 'react';

interface StreamingLiveRegionProps {
  text: string;
  active: boolean;
}

const THROTTLE_MS = 1500;

/**
 * Screen-reader announcement for a streaming AI response. Renders no visible UI —
 * the visible text is handled by the caller's own Markdown render, which updates
 * on every chunk. Announcing every chunk would spam/garble a screen reader, so this
 * throttles what's exposed to the aria-live region to roughly once every THROTTLE_MS
 * while streaming, and announces the final text once streaming ends.
 */
export function StreamingLiveRegion({ text, active }: StreamingLiveRegionProps) {
  const [announced, setAnnounced] = React.useState('');
  const lastUpdateRef = React.useRef(0);
  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!active) {
      setAnnounced(text);
      return;
    }
    const elapsed = Date.now() - lastUpdateRef.current;
    if (elapsed >= THROTTLE_MS) {
      lastUpdateRef.current = Date.now();
      setAnnounced(text);
      return;
    }
    timeoutRef.current = setTimeout(() => {
      lastUpdateRef.current = Date.now();
      setAnnounced(text);
    }, THROTTLE_MS - elapsed);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [text, active]);

  return (
    <span
      aria-live="polite"
      style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}
    >
      {announced}
    </span>
  );
}
