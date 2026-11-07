import type { Schemas } from './apiTypes';

export type User = Schemas['UserOut'];
export type Role = User['role'];
export type FamilySettings = Schemas['SettingsOut'];

// Python weekday number (0 = Monday) → locale key under weekdays.*
export const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
