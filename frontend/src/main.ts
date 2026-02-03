import { createApp } from 'vue';
import App from './App.vue';

declare global {
  interface Window {
    __INITIAL_CONFIG__?: unknown;
    __SERVER_SOURCES__?: unknown;
    __PAGE_CONTEXT__?: unknown;
  }
}

const initialConfig = window.__SERVER_SOURCES__ ?? window.__INITIAL_CONFIG__ ?? [];
const pageContext = window.__PAGE_CONTEXT__ ?? {};

const app = createApp(App, { initialConfig, pageContext });
// Vite runtime-only build does not support custom template delimiters.
app.mount('#app');
window.dispatchEvent(new Event('app:mounted'));
