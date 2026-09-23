import {test, expect} from "@playwright/test";

async function fillForm(page: import('@playwright/test').Page, password = '12345678') {
  await page.goto('/signup');
  await page.getByLabel('Nama perusahaan').fill('TeamKu');
  await page.getByLabel('Nama Anda').fill('Admin');
  await page.getByLabel('Email kerja').fill('admin@example.com');
  await page.getByLabel('Kata sandi', {exact: true}).fill(password);
}

test('short password stays inline, focuses field and never calls API', async ({page}) => {
  let requests = 0;
  await page.route('**/api/auth/signup', route => { requests++; return route.fulfill({status: 422, json: {detail: []}}); });
  await fillForm(page, 'test');
  await page.getByRole('button', {name: 'Buat workspace'}).click();
  await expect(page.getByText('Kata sandi minimal 8 karakter.', {exact: true})).toBeVisible();
  await expect(page.getByLabel('Kata sandi', {exact: true})).toBeFocused();
  await expect(page.getByLabel('Kata sandi', {exact: true})).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(requests).toBe(0);
});

test('server validation is readable and form is preserved', async ({page}) => {
  await page.route('**/api/auth/signup', route => route.fulfill({status: 422, json: {detail: [{type: 'string_too_short', loc: ['body', 'password'], ctx: {min_length: 8}, input: 'secret'}]}}));
  await fillForm(page);
  await page.getByRole('button', {name: 'Buat workspace'}).click();
  await expect(page.getByText('Kata sandi minimal 8 karakter.', {exact: true})).toBeVisible();
  await expect(page.getByLabel('Kata sandi', {exact: true})).toBeFocused();
  await expect(page.getByLabel('Nama perusahaan')).toHaveValue('TeamKu');
  await expect(page.getByText('[object Object]', {exact: true})).toHaveCount(0);
});

test('network errors allow retry without losing input on mobile', async ({page}) => {
  await page.setViewportSize({width: 375, height: 812});
  await page.route('**/api/auth/signup', route => route.abort());
  await fillForm(page);
  await page.getByRole('button', {name: 'Buat workspace'}).click();
  await expect(page.getByRole('alert', {name: 'Pendaftaran belum berhasil'})).toContainText('Periksa koneksi internet Anda');
  await expect(page.getByRole('alert', {name: 'Pendaftaran belum berhasil'})).toBeFocused();
  await expect(page.getByRole('button', {name: 'Buat workspace'})).toBeEnabled();
  await expect(page.getByLabel('Email kerja')).toHaveValue('admin@example.com');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('pending request prevents duplicate submits and success navigates to workspace', async ({page}) => {
  let requests = 0;
  let release = () => {};
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/auth/signup', async route => {
    requests++;
    await pending;
    await route.fulfill({status: 200, json: {access_token: 'test-token'}});
  });
  // Isolate navigation from unrelated dashboard/session requests.
  await page.route('**/app/overview**', route => route.fulfill({contentType: 'text/html', body: '<h1>Workspace</h1>'}));
  await fillForm(page);
  await page.getByRole('button', {name: 'Buat workspace'}).click();
  await expect(page.getByRole('button', {name: 'Membuat workspace'})).toBeDisabled();
  await expect(page.getByLabel('Kata sandi', {exact: true})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Tampilkan kata sandi', exact: true})).toBeDisabled();
  await expect(page.getByRole('status')).toContainText('Sedang memproses');
  expect(requests).toBe(1);
  release();
  await page.waitForURL('**/app/overview');
  expect(await page.evaluate(() => localStorage.getItem('movon_user'))).toBe('test-token');
});

test('duplicate email has recovery guidance beside email', async ({page}) => {
  await page.route('**/api/auth/signup', route => route.fulfill({status: 409, json: {detail: 'Email kerja sudah digunakan'}}));
  await fillForm(page);
  await page.getByRole('button', {name: 'Buat workspace'}).click();
  await expect(page.getByLabel('Email kerja')).toBeFocused();
  await expect(page.getByText('Email kerja sudah digunakan. Gunakan email lain atau masuk ke akun Anda.')).toBeVisible();
});
