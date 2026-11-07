import api from './api';

// Mirrors backend/app/ai_api.py
export interface AiUsage {
    month: { user_name: string; calls: number }[];
    total: number;
}

// Whether the AI can be used at all (a token is set); a parent's AI buttons stay hidden without it
export const fetchAiEnabled = async () => (await api.get<{ enabled: boolean }>('/api/ai/status')).data.enabled;
// Who started how many AI calls this month (parents)
export const fetchAiUsage = async () => (await api.get<AiUsage>('/api/ai/usage')).data;
