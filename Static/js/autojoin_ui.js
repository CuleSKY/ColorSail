(function() {
    const storageKey = 'autojoin_active';
    const joinWindows = {};

    const sendBeacon = (url, payload) => {
        const body = JSON.stringify(payload || {});
        if (navigator.sendBeacon) {
            try {
                return navigator.sendBeacon(url, body);
            } catch (e) {
                return false;
            }
        }
        try {
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body,
                keepalive: true,
                credentials: 'same-origin'
            });
            return true;
        } catch (e) {
            return false;
        }
    };

    const preopenJoinWindow = (serverKey) => {
        let win = null;
        let blocked = false;
        try {
            win = window.open('about:blank', '_blank');
            if (!win) blocked = true;
        } catch (e) {
            blocked = true;
        }
        joinWindows[serverKey] = { win, blocked };
        return joinWindows[serverKey];
    };

    const navigateJoinWindow = (serverKey, url) => {
        const entry = joinWindows[serverKey];
        if (!entry || entry.blocked) return false;
        try {
            const w = entry.win;
            if (!w || w.closed) return false;
            w.location.href = url;
            return true;
        } catch (e) {
            return false;
        }
    };

    window.AutojoinUI = {
        storageKey,
        joinWindows,
        sendBeacon,
        preopenJoinWindow,
        navigateJoinWindow
    };
})();
