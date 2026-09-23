import {test, expect} from "@playwright/test";

for (const route of ['/signup', '/login', '/reset-password?token=test-token', '/invite?token=test-token']) {
  test(`password visibility is keyboard accessible and never submits on ${route}`, async ({page}) => {
    let submissions = 0;
    await page.route('**/api/**', async request => {
      if (request.request().method() === 'POST') submissions++;
      await request.fulfill({json: {email: 'admin@example.com', name: 'Admin', company: 'TeamKu', role: 'employee', department: 'Operations'}});
    });
    await page.goto(route);
    const input = page.getByLabel(route.startsWith('/reset') ? 'Kata sandi baru' : 'Kata sandi', {exact: true});
    await input.fill('Password123!');
    await expect(input).toHaveAttribute('type', 'password');
    const show = page.getByRole('button', {name: 'Tampilkan kata sandi', exact: true});
    await input.press('Tab');
    await expect(show).toBeFocused();
    await show.press('Space');
    await expect(input).toHaveAttribute('type', 'text');
    await expect(input).toHaveValue('Password123!');
    const hide = page.getByRole('button', {name: 'Sembunyikan kata sandi', exact: true});
    await expect(hide).toBeFocused();
    await hide.press('Enter');
    await expect(input).toHaveAttribute('type', 'password');
    await expect(input).toHaveValue('Password123!');
    expect(submissions).toBe(0);
  });
}

test('toggle has a 44px touch target, preserves error description, and does not overlap text', async ({page}) => {
  await page.setViewportSize({width: 375, height: 812});
  await page.goto('/signup');
  const input = page.getByLabel('Kata sandi', {exact: true});
  await input.fill('test');
  await page.getByRole('button', {name: 'Buat workspace'}).click();
  await expect(input).toHaveAttribute('aria-invalid', 'true');
  const show = page.getByRole('button', {name: 'Tampilkan kata sandi', exact: true});
  const bounds = await show.boundingBox();
  expect(bounds?.width).toBeGreaterThanOrEqual(44);
  expect(bounds?.height).toBeGreaterThanOrEqual(44);
  await show.click();
  await expect(input).toHaveAttribute('aria-describedby', 'signup-password-hint signup-password-error');
  await expect(page.getByText('Kata sandi minimal 8 karakter.', {exact: true})).toBeVisible();
  expect(await input.evaluate(element => parseFloat(getComputedStyle(element).paddingRight))).toBeGreaterThanOrEqual(52);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('disabled password cannot be revealed', async ({page}) => {
  await page.goto('/invite');
  await expect(page.getByLabel('Kata sandi', {exact: true})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Tampilkan kata sandi', exact: true})).toBeDisabled();
});
