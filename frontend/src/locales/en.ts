import type de from './de';

// Same keys as de.ts: a missing or extra key is a type error
const en: typeof de = {
    common: {
        appName: 'Meal planner',
        loading: 'Loading…',
        comingSoon: 'Coming soon.',
        save: 'Save',
        cancel: 'Cancel',
        delete: 'Delete',
        edit: 'Edit',
        add: 'Add',
        saved: 'Saved',
    },
    nav: {
        plan: 'Week plan',
        recipes: 'Recipes',
        inbox: 'Inbox',
        history: 'History',
        settings: 'Settings',
        logout: 'Log out',
    },
    roles: { PARENT: 'Parent', CHILD: 'Child' },
    weekdays: {
        0: 'Monday',
        1: 'Tuesday',
        2: 'Wednesday',
        3: 'Thursday',
        4: 'Friday',
        5: 'Saturday',
        6: 'Sunday',
    },
    login: {
        intro: 'Pick your name and enter your PIN',
        pin: 'PIN',
        pinFor: 'PIN for {{name}}',
        showPin: 'Show PIN',
        hidePin: 'Hide PIN',
        submit: 'Log in',
    },
    errors: {
        generic: 'Something went wrong. Please try again.',
        network: 'The server can’t be reached.',
        wrong_name_or_pin: 'Wrong name or PIN.',
        locked: 'Too many wrong tries. Try again in {{minutes}} minutes.',
        not_logged_in: 'You are no longer logged in.',
        parents_only: 'Only parents can do this.',
        user_not_found: 'This person no longer exists.',
        name_taken: 'This name is already taken.',
        last_parent: 'There must be at least one parent.',
        cannot_delete_self: 'You can’t delete yourself.',
        wrong_current_pin: 'The current PIN is wrong.',
    },
};

export default en;
