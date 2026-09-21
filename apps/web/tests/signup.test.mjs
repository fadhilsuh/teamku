import assert from 'node:assert/strict';
import {test} from 'node:test';
import {validateSignup} from '../src/lib/signup.ts';

const valid = {company_name: 'TeamKu', admin_name: 'Admin', email: 'admin@example.com', password: '12345678'};

test('short password reproduces screenshot before any API request', () => {
  assert.deepEqual(validateSignup({...valid, password: 'test'}), {password: 'Kata sandi minimal 8 karakter.'});
});

test('required fields and whitespace-only names are rejected', () => {
  const errors = validateSignup({company_name: '  ', admin_name: '', email: '', password: ''});
  assert.equal(Object.keys(errors).length, 4);
  assert.equal(errors.company_name, 'Nama perusahaan wajib diisi.');
});

test('backend maximum lengths and malformed email are rejected', () => {
  const errors = validateSignup({company_name: 'x'.repeat(121), admin_name: 'x'.repeat(101), email: 'invalid', password: 'x'.repeat(129)});
  assert.equal(Object.keys(errors).length, 4);
  assert.equal(errors.email, 'Masukkan alamat email yang valid, misalnya nama@perusahaan.com.');
});

test('valid data and password spaces are preserved', () => {
  assert.deepEqual(validateSignup(valid), {});
  assert.deepEqual(validateSignup({...valid, password: ' 123456 '}), {});
});

test('Unicode length matches Python code-point counting', () => {
  assert.equal(validateSignup({...valid, password: '😀'.repeat(4)}).password, 'Kata sandi minimal 8 karakter.');
});
