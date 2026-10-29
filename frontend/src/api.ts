import axios from 'axios';
import i18n from './i18n';

// Same origin: Vite (dev) or nginx (Docker) forwards /api to the backend; the browser tests set VITE_API_URL
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || undefined });

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Expired or invalid token: drop it and go back to the login page
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const isLogin = error.config?.url?.endsWith('/api/token');
        if (error.response?.status === 401 && !isLogin && localStorage.getItem('token')) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    },
);

// The backend sends a code (errors.<code> in the locales), alone or with the values the text needs
export function errorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        const { code, ...params } = typeof detail === 'string' ? { code: detail } : (detail ?? {});
        if (typeof code === 'string' && i18n.exists(`errors.${code}`)) return i18n.t(`errors.${code}`, params);
        if (!error.response) return i18n.t('errors.network');
    }
    return i18n.t('errors.generic');
}

export default api;
