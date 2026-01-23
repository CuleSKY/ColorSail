(function() {
    const storageKey = 'autojoin_active';

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

    window.AutojoinUI = {
        storageKey,
        sendBeacon
    };
})();
