import { test, expect } from '@playwright/test';

test.describe('Decoupled Scraper UI Gateway - Lifecycle Assertions', () => {
  test('Should transition from configuration form to polling loader, then render results', async ({ page }) => {
    await page.route('/api/gateway/start', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'mock-job-12345' }),
      });
    });

    let pollingCount = 0;
    await page.route(/\/api\/gateway\/poll\?id=mock-job-12345/, async (route) => {
      pollingCount++;
      if (pollingCount === 1) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ Status: 'RUNNING', Result: null }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            Status: 'COMPLETED',
            Result: [{ title: 'Extracted Target Data', url: 'https://example.com' }],
          }),
        });
      }
    });

    const baseUrl = process.env.BASE_URL || 'http://localhost:3000';
    await page.goto(`${baseUrl}/gateway`);

    await page.locator("input[name='targetUrl']").fill('https://target-to-scrape.com');
    await page.locator("textarea[name='selectorConfig']").fill('div.target-selector');
    await page.locator("button[type='submit']").click();

    const progressIndicator = page.locator("[data-testid='progress-indicator']");
    await progressIndicator.waitFor({ state: 'visible' });

    const dataGridLocator = page.locator("[data-testid='data-grid-view']");
    await dataGridLocator.waitFor({ state: 'visible', timeout: 10000 });

    const innerText = await dataGridLocator.innerText();
    expect(innerText).toContain('Extracted Target Data');
  });
});
