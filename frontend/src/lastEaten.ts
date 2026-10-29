import { formatDistanceToNowStrict, parseISO } from 'date-fns';
import { de, enUS } from 'date-fns/locale';
import i18n from './i18n';

// "vor 5 Wochen" / "5 weeks ago", for a date the backend sent as "2026-09-26"
export function sinceText(day: string): string {
    return formatDistanceToNowStrict(parseISO(day), { addSuffix: true, locale: i18n.language === 'de' ? de : enUS });
}
