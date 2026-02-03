import { createApp } from 'vue';
import App from './App.vue';

declare global {
  interface Window {
    __INITIAL_CONFIG__?: unknown;
    __PAGE_CONTEXT__?: unknown;
  }
}

const initialConfig = window.__INITIAL_CONFIG__ ?? [];
const pageContext = window.__PAGE_CONTEXT__ ?? {};

const app = createApp(App, { initialConfig, pageContext });
app.config.compilerOptions.delimiters = ['[[', ']]'];
app.mount('#app');
