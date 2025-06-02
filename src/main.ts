import { createApp } from 'vue'
import App from './App.vue'

// Create and mount the Vue app
const app = createApp(App)

app.mount('#app')

// Hide loading screen once Vue app is mounted
setTimeout(() => {
    const loadingElement = document.getElementById('loading')
    if (loadingElement) {
        loadingElement.style.display = 'none'
    }
}, 500)