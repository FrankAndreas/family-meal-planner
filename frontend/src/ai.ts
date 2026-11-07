import api from './api';
import type { Schemas } from './apiTypes';

export type AiUsage = Schemas['AiUsageOut'];

// Whether the AI can be used at all (a token is set); a parent's AI buttons stay hidden without it
export const fetchAiEnabled = async () => (await api.get<Schemas['AiStatusOut']>('/api/ai/status')).data.enabled;
// Who started how many AI calls this month (parents)
export const fetchAiUsage = async () => (await api.get<AiUsage>('/api/ai/usage')).data;
