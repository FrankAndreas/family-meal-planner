import type { Language } from './i18n';

export type Role = 'PARENT' | 'CHILD';

export interface User {
    id: number;
    name: string;
    role: Role;
    // The language the person sees: their own choice, or the app's default language
    language: Language;
    language_chosen: boolean;
}

export interface PublicUser {
    id: number;
    name: string;
}

export interface FamilySettings {
    family_size: number;
    // Python weekday: 0 = Monday ... 6 = Sunday
    week_start: number;
}

// Python weekday number (0 = Monday) → locale key under weekdays.*
export const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
