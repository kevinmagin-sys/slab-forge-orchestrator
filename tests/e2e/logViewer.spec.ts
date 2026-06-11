import { test, expect } from '@playwright/test';

// SUITE "Decoupled Scraper UI Gateway - Lifecycle Assertions"
test.describe('Decoupled Scraper UI Gateway - Lifecycle Assertions', () => {

  // TEST "Should transition from configuration form to polling loader, then render results"
  test('Should transition from configuration form to polling loader, then render results', async ({ page }) => {
    
    // SETUP Context
    // Step 1: Boot headless browser context (handled natively via Playwright test runner fixture)

    // Step 2: Intercept network routes to simulate worker backend (SPOF Mitigation)
    // EXECUTE Page.Route("/api/gateway/start", (Route) => { ... })
    await page.route('/api/gateway/start', async (route) => {
      // Simulate successful job acceptance handler (Task DSG-FE-006)
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'mock-job-12345' }),
      });
    });

    // Track how many times polling endpoint is hit to change mock data dynamically
    // SET PollingCount = 0
    let pollingCount = 0;

    // EXECUTE Page.Route("/api/gateway/poll?id=mock-job-12345", (Route) => { ... })
    await page.route(/\/api\/gateway\/poll\?id=mock-job-12345/, async (route) => {
      // Increment PollingCount
      pollingCount++;

      // IF PollingCount == 1 THEN
      if (pollingCount === 1) {
        // Return active processing state first
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ Status: 'RUNNING', Result: null }),
        });
      } else {
        // ELSE Return terminal completed state on second poll
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
    const baseUrl = process.env.BASE_URL || 'http://localhost:3000'; // Resolves GetEnvironmentBaseUrl()

    // Step 3: Navigate to local or pipeline web server target
    // AWAIT Page.Navigate(GetEnvironmentBaseUrl() + "/gateway")
    await page.goto(`${baseUrl}/gateway`);

    // Step 4: Interact with form using explicit, resilient locators
    // AWAIT Page.Locator("input[name='targetUrl']").Fill("https://target-to-scrape.com")
    await page.locator("input[name='targetUrl']").fill('https://target-to-scrape.com');
    
    // AWAIT Page.Locator("textarea[name='selectorConfig']").Fill("div.target-selector")
    await page.locator("textarea[name='selectorConfig']").fill('div.target-selector');

    // Step 5: Submit form to trigger React 19 Action and subsequent TanStack Query loop
    // AWAIT Page.Locator("button[type='submit']").Click()
    await page.locator("button[type='submit']").click();

    // Step 6: Assert UI state mutations structurally matching the mock data timelines
    // Assert loading/processing component manifests immediately
    // AWAIT Page.Locator("[data-testid='progress-indicator']").WaitForElementState("visible")
    const progressIndicator = page.locator("[data-testid='progress-indicator']");
    await progressIndicator.waitFor({ state: 'visible' });

    // Assert final data rendering component displays after mock switches state to COMPLETED
    // SET DataGridLocator = Page.Locator("[data-testid='data-grid-view']")
    const dataGridLocator = page.locator("[data-testid='data-grid-view']");
    
    // AWAIT DataGridLocator.WaitForElementState("visible", Timeout = 10000)
    await dataGridLocator.waitFor({ state: 'visible', timeout: 10000 });

    // Verify content correctness inside container to prevent layout thrashing or ghost text
    // ASSERT DataGridLocator.InnerText().Contains("Extracted Target Data")
    const innerText = await dataGridLocator.innerText();
    expect(innerText).toContain('Extracted Target Data');
    // END EXECUTE

    // TEARDOWN (Page and browser context scopes are terminated natively by the runner environment)
  }); // END TEST
}); // END SUITE
