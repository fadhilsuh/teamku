import assert from 'node:assert/strict';
import {test, afterEach} from 'node:test';
import {api} from '../src/lib/api.ts';

const originalFetch = globalThis.fetch;
globalThis.window = {setTimeout, clearTimeout};
afterEach(() => { globalThis.fetch = originalFetch; });

function respond(body, status = 422) {
  globalThis.fetch = async () => new Response(JSON.stringify(body), {status});
}

test('FastAPI password validation becomes Indonesian text and field errors, never echoes input', async () => {
  respond({detail: [{type: 'string_too_short', loc: ['body', 'password'], input: 'secret', msg: 'String should have at least 8 characters', ctx: {min_length: 8}}]});
  await assert.rejects(api('/auth/signup'), error => {
    assert.equal(error.message, 'Kata sandi minimal 8 karakter.');
    assert.equal(error.fieldErrors.password, error.message);
    assert.equal(error.status, 422);
    assert.ok(!error.message.includes('secret'));
    return true;
  });
});

test('multiple validation errors stay readable', async () => {
  respond({detail: [
    {type: 'missing', loc: ['body', 'email']},
    {type: 'string_too_long', loc: ['body', 'admin_name'], ctx: {max_length: 100}},
  ]});
  await assert.rejects(api('/auth/signup'), error => {
    assert.equal(error.fieldErrors.email, 'Email kerja wajib diisi.');
    assert.equal(error.fieldErrors.admin_name, 'Nama Anda maksimal 100 karakter.');
    return true;
  });
});

test('business errors remain readable', async () => {
  respond({detail: 'Email kerja sudah digunakan'}, 409);
  await assert.rejects(api('/auth/signup'), {message: 'Email kerja sudah digunakan'});
});

test('malformed detail and HTML responses use safe fallback', async () => {
  for (const detail of [{unexpected: 'secret'}, [], null, '[object Object]']) {
    respond({detail});
    await assert.rejects(api('/auth/signup'), {message: 'Data belum dapat diproses. Periksa isian Anda lalu coba lagi.'});
  }
  globalThis.fetch = async () => new Response('<html>proxy failure</html>', {status: 502});
  await assert.rejects(api('/auth/signup'), {message: 'Layanan sedang mengalami gangguan. Silakan coba lagi beberapa saat lagi.'});
});

test('server internals are not displayed', async () => {
  respond({detail: 'SQL connection password=secret'}, 500);
  await assert.rejects(api('/auth/signup'), {message: 'Layanan sedang mengalami gangguan. Silakan coba lagi beberapa saat lagi.'});
});

test('network failures provide recovery guidance', async () => {
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(api('/auth/signup'), {message: 'Tidak dapat terhubung ke server. Periksa koneksi internet Anda lalu coba lagi.'});
});

test('successful responses are unchanged', async () => {
  respond({access_token: 'test-token'}, 200);
  assert.deepEqual(await api('/auth/signup'), {access_token: 'test-token'});
});
