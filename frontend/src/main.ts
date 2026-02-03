import { createApp } from 'vue';
import App from './App.vue';

declare global {
  interface Window {
    __INITIAL_CONFIG__?: unknown;
    __PAGE_CONTEXT__?: unknown;
  }
}

const rawInitialConfig = window.__INITIAL_CONFIG__;
const initialConfig = Array.isArray(rawInitialConfig)
  ? { server: rawInitialConfig }
  : {
      ...(rawInitialConfig && typeof rawInitialConfig === 'object' ? rawInitialConfig : {}),
      server:
        rawInitialConfig && typeof rawInitialConfig === 'object' && 'server' in rawInitialConfig
          ? (rawInitialConfig as { server?: unknown }).server ?? []
          : [],
    };
const pageContext = window.__PAGE_CONTEXT__ ?? {};

const app = createApp(App, { initialConfig, pageContext });
app.config.compilerOptions.delimiters = ['[[', ']]'];
app.mount('#app');
