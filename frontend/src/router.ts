import { createRouter, createWebHistory } from 'vue-router';
import MapCooldownView from './views/MapCooldownView.vue';

const EmptyView = { template: '<div></div>' };

const routes = [
  { path: '/', name: 'Servers', component: EmptyView },
  { path: '/map-sub', name: 'MapSub', component: EmptyView },
  { path: '/map-cooldown', name: 'MapCooldown', component: MapCooldownView },
  { path: '/stats', name: 'Stats', component: EmptyView },
  { path: '/feedback', name: 'Feedback', component: EmptyView }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
