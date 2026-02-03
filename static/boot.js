(() => {
  const BOOT_TIMEOUT_MS = 8000;
  const BOOT_MOUNT_TIMEOUT_MS = 10000;
  const bootRoot = document.getElementById('boot-root');
  const fragmentsRoot = document.getElementById('fragments-root');
  const debugState = {
    fragments: [],
    viteEntrySrc: null,
    viteCss: [],
    injectedHtmlLength: 0,
  };

  const showError = (message) => {
    if (!bootRoot) {
      return;
    }
    const details = `
      <div style="margin-top:12px;text-align:left;font-size:12px;color:var(--text-secondary)">
        <div><strong>Fragments:</strong> ${debugState.fragments.join(', ') || 'none'}</div>
        <div><strong>Injected HTML length:</strong> ${debugState.injectedHtmlLength}</div>
        <div><strong>Vite entry:</strong> ${debugState.viteEntrySrc || 'missing'}</div>
      </div>
    `;
    bootRoot.innerHTML = `
      <div class="boot-card">
        <div class="boot-title">We hit a loading issue</div>
        <div class="boot-desc">${message}</div>
        ${details}
        <div class="boot-actions">
          <button class="boot-btn" type="button" data-retry>Reload</button>
        </div>
      </div>
    `;
    const retryButton = bootRoot.querySelector('[data-retry]');
    if (retryButton) {
      retryButton.addEventListener('click', () => window.location.reload());
    }
  };

  const fetchWithTimeout = async (url) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), BOOT_TIMEOUT_MS);
    try {
      const response = await fetch(url, {
        cache: 'force-cache',
        credentials: 'same-origin',
        headers: { 'Accept': 'text/html' },
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.text();
    } finally {
      window.clearTimeout(timeoutId);
    }
  };

  const ensureStyles = (cssList) => {
    if (!Array.isArray(cssList)) {
      return;
    }
    debugState.viteCss = cssList;
    const head = document.head || document.getElementsByTagName('head')[0];
    cssList.forEach((href) => {
      if (!href || document.querySelector(`link[data-vite-css="${href}"]`)) {
        return;
      }
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.dataset.viteCss = href;
      head.appendChild(link);
    });
  };

  const loadEntryScript = (src) => new Promise((resolve, reject) => {
    debugState.viteEntrySrc = src;
    console.info('[boot] loading entry script', src);
    const script = document.createElement('script');
    script.type = 'module';
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load entry script'));
    document.head.appendChild(script);
  });

  let appMounted = false;
  const appHasContent = () => {
    const appRoot = document.querySelector('#app');
    return !!(appRoot && appRoot.children && appRoot.children.length > 0);
  };

  const checkReadyToHide = () => {
    if (appMounted && appHasContent()) {
      if (bootRoot) {
        bootRoot.style.display = 'none';
        console.info('[boot] boot-root hidden');
      }
    }
  };

  window.addEventListener('app:mounted', () => {
    appMounted = true;
    console.info('[boot] app:mounted received');
    checkReadyToHide();
  });

  const waitForAppRender = () => new Promise((resolve, reject) => {
    const start = window.performance.now();
    const tick = () => {
      checkReadyToHide();
      if (appMounted && appHasContent()) {
        resolve();
        return;
      }
      if (window.performance.now() - start > BOOT_MOUNT_TIMEOUT_MS) {
        reject(new Error('App mounted but did not render in time'));
        return;
      }
      window.requestAnimationFrame(tick);
    };
    tick();
  });

  const requireAppContainer = () => {
    const appRoot = document.querySelector('#app');
    if (!appRoot) {
      throw new Error('Missing #app root after fragment injection');
    }
  };

  const ensureBootRootVisible = () => {
    if (bootRoot) {
      bootRoot.style.display = '';
    }
  };

  const startBoot = async () => {
    try {
      if (!fragmentsRoot) {
        throw new Error('Missing fragments container');
      }
      const fragmentSources = window.__FRAGMENTS__ ? Object.values(window.__FRAGMENTS__) : [];
      if (!fragmentSources.length) {
        throw new Error('No fragments configured');
      }
      debugState.fragments = fragmentSources;
      const fragmentHtmlList = [];
      for (const source of fragmentSources) {
        try {
          const html = await fetchWithTimeout(source);
          console.info('[boot] fragment fetched', source, html.length);
          fragmentHtmlList.push(html);
        } catch (error) {
          console.info('[boot] fragment fetch failed', source, error);
          throw error;
        }
      }
      fragmentsRoot.innerHTML = fragmentHtmlList.join('\n');
      debugState.injectedHtmlLength = fragmentsRoot.innerHTML.length;
      console.info('[boot] injected html length', debugState.injectedHtmlLength);
      fragmentsRoot.style.display = 'block';
      if (bootRoot) {
        bootRoot.style.background = 'transparent';
      }
      ensureBootRootVisible();
      requireAppContainer();

      const viteEntry = window.__VITE_ENTRY__ || {};
      ensureStyles(viteEntry.css || []);
      if (!viteEntry.js) {
        throw new Error('Missing Vite entry script');
      }
      await loadEntryScript(viteEntry.js);
      await waitForAppRender();
    } catch (error) {
      const message = error && error.message ? error.message : 'Unexpected error while loading the app.';
      showError(`${message}. Please check your connection and try again.`);
    }
  };

  startBoot();
})();
