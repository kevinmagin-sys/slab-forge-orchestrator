import { test, expect } from '@playwright/test';

// SUITE "Decoupled Scraper UI Gateway - Lifecycle Assertions"
test.describe('Decoupled Scraper UI Gateway - Lifecycle Assertions', () => {

  // TEST "Should transition from configuration form to polling loader, then render results"
  test('Should transition from configuration form to polling loader, then render results', async ({ page }) => {
    
    // SETUP Context
    // Step 1: Boot headless browser context (handled natively via Playwright test runner fixture)

    // Step 2: Intercept network routes to simulate worker backend (SPOF Mitigation)
    await page.route('/api/gateway/start', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'mock-job-12345' }),
      });
    });

    // Track how many times polling endpoint is hit to change mock data dynamically
    let pollingCount = 0;

    // EXECUTE Page.Route("/api/gateway/poll?id=mock-job-12345", (Route) => { ... })
    await page.route(/\/api\/gateway\/poll\?id=mock-job-12345/, async (route) => {
      pollingCount++;

      // IF PollingCount == 1 THEN
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
      } // END IF
    });
    // END SETUP

    // EXECUTE Test_Execution
    const baseUrl = process.env.BASE_URL || 'http://localhost:3000';

    // Step 3: Navigate to local or pipeline web server target
    await page.goto(`${baseUrl}/gateway`);

    // Step 4: Interact with form using explicit, resilient locators
    await page.locator("input[name='targetUrl']").fill('https://target-to-scrape.com');
    await page.locator("textarea[name='selectorConfig']").fill('div.target-selector');

    // Step 5: Submit form to trigger React 19 Action and subsequent TanStack Query loop
    await page.locator("button[type='submit']").click();

    // Step 6: Assert UI state mutations structurally matching the mock data timelines
    const progressIndicator = page.locator("[data-testid='progress-indicator']");
    await progressIndicator.waitFor({ state: 'visible' });

    const dataGridLocator = page.locator("[data-testid='data-grid-view']");
    await dataGridLocator.waitFor({ state: 'visible', timeout: 10000 });

    const innerText = await dataGridLocator.innerText();
    expect(innerText).toContain('Extracted Target Data');
  });
});
