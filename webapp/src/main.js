import { createApp } from 'vue'
import App from './App.vue'

import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'telegram',
    themes: {
      telegram: {
        dark: false,
        colors: {
          background: '#ffffff',
          surface: '#f5f5f5',
          primary: '#3390ec',
          secondary: '#6c757d',
          success: '#4caf50',
          error: '#f44336',
          warning: '#ff9800',
        },
      },
    },
  },
})

const app = createApp(App)
app.config.globalProperties.TMA = window.Telegram.WebApp
app.use(vuetify)
app.mount('#app')
