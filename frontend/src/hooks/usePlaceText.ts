import { format, parseISO } from 'date-fns';
import { useTranslation } from 'react-i18next';
import { type Slot, weekdayKey } from '../plan';

// "Sa 7.11. · Abendessen": a place in the plan, as people read it
export function usePlaceText() {
    const { t } = useTranslation();
    return (day: string, slot: Slot) =>
        t('plan.place', {
            day: `${t(`weekdays.${weekdayKey(day)}`)} ${format(parseISO(day), 'd.M.')}`,
            slot: t(`plan.slots.${slot}`),
        });
}
