'use client';

/**
 * MobileOptimizations.tsx
 *
 * Production Task 24: Mobile & PWA
 *
 * This module provides mobile-specific behaviors:
 * - Task 24.1: Responsive detection hook (useIsMobile)
 *   NOTE: Tailwind CSS handles responsive breakpoints via utility classes
 *   (sm:, md:, lg:, xl:). This hook provides a JavaScript-level check for
 *   conditional rendering when CSS alone isn't sufficient.
 *
 * - Task 24.3: Push notifications hook (usePushNotifications)
 *   Requests permission, registers service worker, handles push subscription.
 *
 * - Task 24.4: Touch upload hook (useTouchUpload)
 *   On mobile, converts drag-drop zones to tap-to-upload with large tap targets.
 *
 * - Task 24.6: Offline indicator component (OfflineIndicator)
 *   Shows a banner when network connection is lost.
 *
 * ============================================================================
 * MOBILE TESTING REQUIREMENTS (Task 24.5)
 * ============================================================================
 *
 * Before release, all flows MUST be tested on:
 *
 * 1. iOS Safari (iPhone 13+, iOS 16+):
 *    - Test file upload via camera roll picker
 *    - Test PWA install from Safari share menu → "Add to Home Screen"
 *    - Test push notifications (requires HTTPS + user gesture for permission)
 *    - Test offline indicator (toggle airplane mode)
 *    - Verify safe area insets (notch, home indicator)
 *    - Test video playback (inline, no fullscreen hijack)
 *    - Verify 100vh fix (iOS address bar causes layout shift)
 *
 * 2. Chrome Android (Pixel 6+, Android 12+):
 *    - Test file upload via file picker and camera
 *    - Test PWA install from "Add to Home Screen" prompt
 *    - Test push notifications with Firebase Cloud Messaging integration
 *    - Test offline mode transitions (airplane mode toggle)
 *    - Test back button behavior in PWA standalone mode
 *    - Verify no content hidden behind system navigation bar
 *
 * 3. iPad / Android Tablet:
 *    - Test responsive layout at tablet breakpoint (768px - 1024px)
 *    - Verify drag-drop still works on tablet (larger touch targets)
 *    - Test split-screen / multitasking mode
 *
 * 4. Known Mobile Issues to Verify:
 *    - iOS: 300ms tap delay (ensure touch-action: manipulation is set)
 *    - iOS: Rubber-band scrolling doesn't break fixed headers
 *    - iOS: Input zoom on focus (font-size must be ≥ 16px)
 *    - Android: Keyboard pushing content up (verify layout stability)
 *    - Both: Touch target minimum 44x44px (WCAG 2.1)
 *    - Both: Orientation change doesn't break layout
 *
 * Testing Tools:
 *    - BrowserStack or Sauce Labs for real device testing
 *    - Chrome DevTools mobile emulation for quick checks
 *    - Xcode Simulator for iOS Safari debugging
 *    - Android Studio Emulator for Chrome Android debugging
 * ============================================================================
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// =============================================================================
// Task 24.1: useIsMobile — Responsive Detection Hook
// =============================================================================

/**
 * Detects if the current viewport is mobile-sized.
 *
 * NOTE: Tailwind CSS handles all responsive styling via breakpoint prefixes
 * (sm:, md:, lg:, xl:, 2xl:). Use this hook ONLY when you need to:
 * - Conditionally render entirely different component trees
 * - Change behavior (not just styling) based on device type
 * - Optimize performance by not loading heavy components on mobile
 *
 * @param breakpoint - The max-width in px to consider "mobile" (default: 768)
 * @returns boolean indicating if viewport is at or below the breakpoint
 */
export function useIsMobile(breakpoint: number = 768): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(false);

  useEffect(() => {
    // Check on mount (SSR-safe: defaults to false, updates on client)
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= breakpoint);
    };

    checkMobile();

    const mediaQuery = window.matchMedia(`(max-width: ${breakpoint}px)`);

    const handler = (event: MediaQueryListEvent) => {
      setIsMobile(event.matches);
    };

    // Modern browsers support addEventListener on MediaQueryList
    mediaQuery.addEventListener('change', handler);

    return () => {
      mediaQuery.removeEventListener('change', handler);
    };
  }, [breakpoint]);

  return isMobile;
}

// =============================================================================
// Task 24.3: usePushNotifications — Push Notification Hook
// =============================================================================

export interface PushNotificationState {
  /** Whether push is supported in the current browser */
  isSupported: boolean;
  /** Current permission status: 'default' | 'granted' | 'denied' */
  permission: NotificationPermission | 'unsupported';
  /** The push subscription object (null if not subscribed) */
  subscription: PushSubscription | null;
  /** Whether a request is in progress */
  isLoading: boolean;
  /** Error message if something went wrong */
  error: string | null;
}

export interface PushNotificationActions {
  /** Request notification permission and subscribe to push */
  requestPermission: () => Promise<void>;
  /** Unsubscribe from push notifications */
  unsubscribe: () => Promise<void>;
}

/**
 * Hook for managing push notifications.
 *
 * Handles:
 * - Checking browser support for Push API
 * - Requesting notification permission (must be triggered by user gesture)
 * - Registering the service worker
 * - Creating a push subscription
 * - Sending subscription to backend (placeholder)
 *
 * Usage:
 * ```tsx
 * const { state, actions } = usePushNotifications();
 *
 * if (state.permission === 'default') {
 *   return <button onClick={actions.requestPermission}>Enable Notifications</button>;
 * }
 * ```
 */
export function usePushNotifications(): {
  state: PushNotificationState;
  actions: PushNotificationActions;
} {
  const [state, setState] = useState<PushNotificationState>({
    isSupported: false,
    permission: 'unsupported',
    subscription: null,
    isLoading: false,
    error: null,
  });

  // Check support on mount
  useEffect(() => {
    const isSupported =
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window;

    setState((prev) => ({
      ...prev,
      isSupported,
      permission: isSupported ? Notification.permission : 'unsupported',
    }));

    // Check for existing subscription
    if (isSupported) {
      navigator.serviceWorker.ready
        .then((registration) => {
          return registration.pushManager.getSubscription();
        })
        .then((subscription) => {
          setState((prev) => ({ ...prev, subscription }));
        })
        .catch(() => {
          // Silently fail — might not have SW registered yet
        });
    }
  }, []);

  const requestPermission = useCallback(async () => {
    if (!state.isSupported) {
      setState((prev) => ({
        ...prev,
        error: 'Push notifications are not supported in this browser.',
      }));
      return;
    }

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Step 1: Request notification permission
      const permission = await Notification.requestPermission();
      setState((prev) => ({ ...prev, permission }));

      if (permission !== 'granted') {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error:
            permission === 'denied'
              ? 'Notification permission was denied. Please enable in browser settings.'
              : 'Notification permission was dismissed.',
        }));
        return;
      }

      // Step 2: Register service worker (if not already)
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
      });

      // Wait for the service worker to be ready
      await navigator.serviceWorker.ready;

      // Step 3: Subscribe to push
      // NOTE: In production, replace this with your actual VAPID public key
      // generated via: npx web-push generate-vapid-keys
      const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || '';

      let subscription: PushSubscription | null = null;

      if (VAPID_PUBLIC_KEY) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });

        // Step 4: Send subscription to backend
        // Placeholder: replace with actual API call
        await sendSubscriptionToBackend(subscription);
      }

      setState((prev) => ({
        ...prev,
        subscription,
        isLoading: false,
      }));
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to enable push notifications.',
      }));
    }
  }, [state.isSupported]);

  const unsubscribe = useCallback(async () => {
    if (!state.subscription) return;

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      await state.subscription.unsubscribe();

      // Notify backend to remove subscription
      // Placeholder: replace with actual API call
      await removeSubscriptionFromBackend(state.subscription);

      setState((prev) => ({
        ...prev,
        subscription: null,
        isLoading: false,
      }));
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to unsubscribe from push notifications.',
      }));
    }
  }, [state.subscription]);

  return {
    state,
    actions: { requestPermission, unsubscribe },
  };
}

// Helper: Convert VAPID key from base64 URL to Uint8Array
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// Placeholder: Send push subscription to backend for storage
async function sendSubscriptionToBackend(
  subscription: PushSubscription
): Promise<void> {
  // TODO: Replace with actual API endpoint when push service is configured
  // Example:
  // await fetch('/api/push/subscribe', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify(subscription.toJSON()),
  // });
  console.log('[Push] Subscription created:', subscription.endpoint);
}

// Placeholder: Remove push subscription from backend
async function removeSubscriptionFromBackend(
  subscription: PushSubscription
): Promise<void> {
  // TODO: Replace with actual API endpoint
  // await fetch('/api/push/unsubscribe', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ endpoint: subscription.endpoint }),
  // });
  console.log('[Push] Subscription removed:', subscription.endpoint);
}

// =============================================================================
// Task 24.4: useTouchUpload — Touch-Optimized File Upload Hook
// =============================================================================

export interface TouchUploadOptions {
  /** Accepted MIME types (default: 'video/*') */
  accept?: string;
  /** Max file size in bytes (default: 2GB) */
  maxSize?: number;
  /** Callback when a file is selected */
  onFileSelected: (file: File) => void;
  /** Callback for validation errors */
  onError?: (error: string) => void;
}

export interface TouchUploadReturn {
  /** Whether the device is touch-enabled */
  isTouchDevice: boolean;
  /** Open the native file picker (for tap-to-upload) */
  openFilePicker: () => void;
  /** Props to spread on the upload target element */
  touchTargetProps: {
    onClick: () => void;
    onKeyDown: (e: React.KeyboardEvent) => void;
    role: string;
    tabIndex: number;
    'aria-label': string;
    style: React.CSSProperties;
  };
}

/**
 * Hook that converts drag-drop upload zones to tap-to-upload on mobile.
 *
 * On touch devices, drag-and-drop is impractical. This hook provides:
 * - A large tap target (minimum 44x44px per WCAG 2.1)
 * - Opens native file picker on tap
 * - File type and size validation
 * - Keyboard accessible (Enter/Space to activate)
 *
 * Usage:
 * ```tsx
 * const { isTouchDevice, touchTargetProps } = useTouchUpload({
 *   accept: 'video/*',
 *   onFileSelected: (file) => handleUpload(file),
 * });
 *
 * return isTouchDevice ? (
 *   <div {...touchTargetProps} className="tap-upload-zone">
 *     Tap to upload video
 *   </div>
 * ) : (
 *   <DropZone onDrop={handleUpload} />
 * );
 * ```
 */
export function useTouchUpload(options: TouchUploadOptions): TouchUploadReturn {
  const { accept = 'video/*', maxSize = 2 * 1024 * 1024 * 1024, onFileSelected, onError } = options;
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isTouchDevice, setIsTouchDevice] = useState(false);

  useEffect(() => {
    // Detect touch capability
    const hasTouch =
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      // @ts-ignore — msMaxTouchPoints is IE/Edge legacy
      navigator.msMaxTouchPoints > 0;

    setIsTouchDevice(hasTouch);

    // Create hidden file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.style.display = 'none';
    input.setAttribute('aria-hidden', 'true');

    input.addEventListener('change', (e) => {
      const target = e.target as HTMLInputElement;
      const file = target.files?.[0];

      if (!file) return;

      // Validate file size
      if (file.size > maxSize) {
        const maxMB = Math.round(maxSize / (1024 * 1024));
        onError?.(`File is too large. Maximum size is ${maxMB}MB.`);
        target.value = '';
        return;
      }

      // Validate file type
      if (accept !== '*' && !file.type.match(accept.replace('*', '.*'))) {
        onError?.(`Invalid file type. Please upload a ${accept} file.`);
        target.value = '';
        return;
      }

      onFileSelected(file);
      target.value = ''; // Reset for re-selection
    });

    document.body.appendChild(input);
    inputRef.current = input;

    return () => {
      document.body.removeChild(input);
      inputRef.current = null;
    };
  }, [accept, maxSize, onFileSelected, onError]);

  const openFilePicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openFilePicker();
      }
    },
    [openFilePicker]
  );

  const touchTargetProps = {
    onClick: openFilePicker,
    onKeyDown: handleKeyDown,
    role: 'button' as const,
    tabIndex: 0,
    'aria-label': 'Tap to upload a video file',
    style: {
      // Ensure minimum 44x44px touch target (WCAG 2.1 AAA)
      minHeight: '120px',
      minWidth: '100%',
      cursor: 'pointer',
      touchAction: 'manipulation' as const, // Eliminates 300ms tap delay
    } as React.CSSProperties,
  };

  return {
    isTouchDevice,
    openFilePicker,
    touchTargetProps,
  };
}

// =============================================================================
// Task 24.6: OfflineIndicator — Connection Status Component
// =============================================================================

export interface OfflineIndicatorProps {
  /** Custom message to show when offline (default provided) */
  message?: string;
  /** Additional CSS classes */
  className?: string;
  /** Whether to show a "retry" button */
  showRetry?: boolean;
}

/**
 * OfflineIndicator Component
 *
 * Displays a banner at the top of the viewport when the user loses
 * their internet connection. Automatically hides when connection is restored.
 *
 * Uses:
 * - navigator.onLine for initial state
 * - 'online' / 'offline' window events for real-time updates
 *
 * The banner animates in/out smoothly and is positioned fixed at the top
 * so it doesn't disrupt page layout.
 */
export function OfflineIndicator({
  message = "You're offline. Some features may be unavailable.",
  className = '',
  showRetry = true,
}: OfflineIndicatorProps) {
  const [isOffline, setIsOffline] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Set initial state
    setIsOffline(!navigator.onLine);

    const handleOffline = () => {
      setIsOffline(true);
      // Small delay for animation
      requestAnimationFrame(() => setIsVisible(true));
    };

    const handleOnline = () => {
      setIsVisible(false);
      // Wait for exit animation before removing from DOM
      setTimeout(() => setIsOffline(false), 300);
    };

    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    // If already offline on mount, show immediately
    if (!navigator.onLine) {
      requestAnimationFrame(() => setIsVisible(true));
    }

    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={className}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        transform: isVisible ? 'translateY(0)' : 'translateY(-100%)',
        transition: 'transform 0.3s ease-in-out',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.75rem',
          padding: '0.75rem 1rem',
          backgroundColor: '#dc2626',
          color: '#ffffff',
          fontSize: '0.875rem',
          fontWeight: 500,
          textAlign: 'center',
        }}
      >
        {/* Offline Icon */}
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="1" y1="1" x2="23" y2="23" />
          <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
          <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
          <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
          <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
          <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
          <line x1="12" y1="20" x2="12.01" y2="20" />
        </svg>

        <span>{message}</span>

        {showRetry && (
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '0.25rem 0.75rem',
              backgroundColor: 'rgba(255, 255, 255, 0.2)',
              color: '#ffffff',
              border: '1px solid rgba(255, 255, 255, 0.4)',
              borderRadius: '0.25rem',
              fontSize: '0.75rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Default Export — Convenience wrapper component
// =============================================================================

/**
 * MobileOptimizations wrapper component.
 *
 * Drop this into your layout to automatically enable:
 * - Offline indicator banner
 * - Service worker registration (for PWA + push)
 *
 * Usage in layout.tsx:
 * ```tsx
 * import MobileOptimizations from '@/app/components/MobileOptimizations';
 *
 * export default function RootLayout({ children }) {
 *   return (
 *     <html>
 *       <body>
 *         <MobileOptimizations />
 *         {children}
 *       </body>
 *     </html>
 *   );
 * }
 * ```
 */
export default function MobileOptimizations() {
  // Register service worker on mount
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then((registration) => {
          console.log('[PWA] Service Worker registered:', registration.scope);

          // Check for updates periodically
          setInterval(() => {
            registration.update();
          }, 60 * 60 * 1000); // Check every hour
        })
        .catch((error) => {
          console.error('[PWA] Service Worker registration failed:', error);
        });
    }
  }, []);

  return <OfflineIndicator />;
}
