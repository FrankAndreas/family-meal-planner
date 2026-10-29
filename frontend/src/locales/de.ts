// German texts (Swiss spelling: ss, never ß; informal du). en.ts must have the same keys (tsc checks it).
const de = {
    common: {
        appName: 'Menüplaner',
        loading: 'Laden…',
        comingSoon: 'Kommt bald.',
        save: 'Speichern',
        cancel: 'Abbrechen',
        delete: 'Löschen',
        edit: 'Bearbeiten',
        add: 'Hinzufügen',
        saved: 'Gespeichert',
    },
    nav: {
        plan: 'Wochenplan',
        recipes: 'Rezepte',
        inbox: 'Posteingang',
        history: 'Verlauf',
        settings: 'Einstellungen',
        logout: 'Abmelden',
    },
    roles: { PARENT: 'Elternteil', CHILD: 'Kind' },
    // Python weekday numbers: 0 = Montag
    weekdays: {
        0: 'Montag',
        1: 'Dienstag',
        2: 'Mittwoch',
        3: 'Donnerstag',
        4: 'Freitag',
        5: 'Samstag',
        6: 'Sonntag',
    },
    login: {
        intro: 'Wähle deinen Namen und gib deine PIN ein',
        pin: 'PIN',
        pinFor: 'PIN für {{name}}',
        showPin: 'PIN anzeigen',
        hidePin: 'PIN verbergen',
        submit: 'Anmelden',
    },
    errors: {
        generic: 'Etwas ist schiefgelaufen. Bitte versuche es nochmals.',
        network: 'Der Server ist nicht erreichbar.',
        wrong_name_or_pin: 'Name oder PIN ist falsch.',
        locked: 'Zu viele Fehlversuche. Versuche es in {{minutes}} Minuten nochmals.',
        not_logged_in: 'Du bist nicht mehr angemeldet.',
        parents_only: 'Das dürfen nur Eltern.',
        user_not_found: 'Diese Person gibt es nicht mehr.',
        name_taken: 'Diesen Namen gibt es schon.',
        last_parent: 'Es braucht mindestens einen Elternteil.',
        cannot_delete_self: 'Du kannst dich nicht selbst löschen.',
        wrong_current_pin: 'Die aktuelle PIN ist falsch.',
    },
};

export default de;
