(function () {
  'use strict';

  // Keep the storage key consistent with existing backend/frontend expectations.
  const storageKey = 'autojoin_active';

  /**
   * Best-effort keepalive POST helper for leaving AutoJoin queue during tab close / navigation.
   * Returns true if the request was dispatched (not necessarily accepted by server).
   */
  const sendBeacon = (url, payload) => {
    const body = JSON.stringify(payload || {});
    // Prefer navigator.sendBeacon (works during unload in most browsers)
    if (navigator.sendBeacon) {
      try {
        const blob = new Blob([body], { type: 'application/json' });
        return navigator.sendBeacon(url, blob);
      } catch (e) {
        // fallthrough
      }
    }

    // Fallback: keepalive fetch (best effort; may be ignored by browser)
    try {
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
        credentials: 'same-origin'
      });
      return true;
    } catch (e) {
      return false;
    }
  };

  window.AutojoinUI = {
    storageKey,
    sendBeacon
  };
})();
