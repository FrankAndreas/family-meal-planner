import { AxiosError, AxiosHeaders } from 'axios';
import { beforeAll, describe, expect, it } from 'vitest';
import { stubBrowser } from './browserStubs.test-helper';

stubBrowser('en');
let api: typeof import('./api');
beforeAll(async () => {
    api = await import('./api');
});

// An answer of the backend with this status and body
const answer = (status: number, data: unknown) =>
    new AxiosError('failed', String(status), undefined, undefined, {
        status,
        statusText: '',
        headers: {},
        config: { headers: new AxiosHeaders() },
        data,
    });

describe('errorMessage', () => {
    it('shows the text of the code the backend sent', () => {
        expect(api.errorMessage(answer(404, { detail: 'recipe_not_found' }))).toBe('This recipe doesn’t exist.');
    });

    it('fills in the values that come with the code', () => {
        expect(api.errorMessage(answer(429, { detail: { code: 'ai_limit', minutes: 7 } }))).toContain('7');
    });

    it('finds the code of a check of ours in a validation error (422)', () => {
        const detail = [{ msg: 'Value error, not_a_web_link', loc: ['body', 'url'] }];
        expect(api.errorMessage(answer(422, { detail }))).toBe(api.errorMessage(answer(400, { detail: 'not_a_web_link' })));
    });

    it('says the network failed when no answer came, and something generic for anything else', () => {
        const offline = new AxiosError('Network Error', 'ERR_NETWORK');
        expect(api.errorMessage(offline)).not.toBe(api.errorMessage(new Error('x')));
        expect(api.errorMessage(answer(500, { detail: 'no_such_code_here' }))).toBe(api.errorMessage(new Error('x')));
    });
});

describe('errorCode and errorStatus', () => {
    it('give the code and status only of a backend answer', () => {
        expect(api.errorCode(answer(403, { detail: 'no_access' }))).toBe('no_access');
        expect(api.errorCode(answer(429, { detail: { code: 'ai_limit' } }))).toBeUndefined();
        expect(api.errorStatus(answer(401, { detail: 'not_logged_in' }))).toBe(401);
        expect(api.errorStatus(new Error('x'))).toBeUndefined();
    });
});
