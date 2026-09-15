import './styles.css';

import { VueQueryPlugin } from '@tanstack/vue-query';
import { createApp } from 'vue';

import { queryClient } from '@/api/queryClient';
import App from '@/App.vue';
import { createAppRouter } from '@/router';

const app = createApp(App);

app.use(VueQueryPlugin, { queryClient });
app.use(createAppRouter());
app.mount('#app');
