/**
 * Production Task 25.1: End-to-End Tests (Playwright)
 *
 * Full E2E test suite covering:
 * - Signup → Upload → Render → Download flow
 * - Payment flow (Stripe test mode)
 * - Error states (upload failure, render failure, payment failure)
 */
import { test, expect, Page, BrowserContext } from '@playwright/test';

// ---------------------------------------------------------------------------
// Page Object Helpers
// ---------------------------------------------------------------------------

class AuthPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/auth/signup');
  }

  async signup(email: string, password: string, name: string) {
    await this.page.fill('[data-testid="signup-name"]', name);
    await this.page.fill('[data-testid="signup-email"]', email);
    await this.page.fill('[data-testid="signup-password"]', password);
    await this.page.fill('[data-testid="signup-confirm-password"]', password);
    await this.page.click('[data-testid="signup-submit"]');
    await this.page.waitForURL(/\/(dashboard|onboarding)/);
  }

  async login(email: string, password: string) {
    await this.page.goto('/auth/login');
    await this.page.fill('[data-testid="login-email"]', email);
    await this.page.fill('[data-testid="login-password"]', password);
    await this.page.click('[data-testid="login-submit"]');
    await this.page.waitForURL(/\/dashboard/);
  }

  async logout() {
    await this.page.click('[data-testid="user-menu"]');
    await this.page.click('[data-testid="logout-button"]');
    await this.page.waitForURL(/\/(auth\/login|\/)/);
  }
}

class UploadPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/dashboard');
  }

  async uploadVideo(filePath: string) {
    const fileInput = this.page.locator('[data-testid="video-upload-input"]');
    await fileInput.setInputFiles(filePath);
    await this.page.waitForSelector('[data-testid="upload-progress"]');
    await this.page.waitForSelector('[data-testid="upload-complete"]', {
      timeout: 60000,
    });
  }

  async uploadVideoByDragDrop(filePath: string) {
    const dropZone = this.page.locator('[data-testid="drop-zone"]');
    await dropZone.dispatchEvent('drop', {
      dataTransfer: { files: [filePath] },
    });
  }

  async waitForAnalysisComplete() {
    await this.page.waitForSelector('[data-testid="analysis-complete"]', {
      timeout: 120000,
    });
  }

  async getSegmentCount(): Promise<number> {
    const segments = this.page.locator('[data-testid="segment-card"]');
    return segments.count();
  }
}

class RenderPage {
  constructor(private page: Page) {}

  async selectAllSegments() {
    await this.page.click('[data-testid="select-all-segments"]');
  }

  async selectSegment(index: number) {
    await this.page.click(`[data-testid="segment-card-${index}"]`);
  }

  async startRender() {
    await this.page.click('[data-testid="start-render-button"]');
  }

  async waitForRenderComplete(timeout = 300000) {
    await this.page.waitForSelector('[data-testid="render-complete"]', {
      timeout,
    });
  }

  async getRenderProgress(): Promise<string> {
    const progress = this.page.locator('[data-testid="render-progress"]');
    return (await progress.textContent()) || '0%';
  }
}

class DownloadPage {
  constructor(private page: Page) {}

  async downloadClip(index: number) {
    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      this.page.click(`[data-testid="download-clip-${index}"]`),
    ]);
    return download;
  }

  async downloadAll() {
    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      this.page.click('[data-testid="download-all-button"]'),
    ]);
    return download;
  }
}

class BillingPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/billing');
  }

  async selectPlan(plan: 'pro' | 'business') {
    await this.page.click(`[data-testid="select-plan-${plan}"]`);
  }

  async completeStripeCheckout(cardNumber = '4242424242424242') {
    // Stripe Checkout is in an iframe
    const stripeFrame = this.page.frameLocator('iframe[name*="stripe"]');

    await stripeFrame.locator('[data-testid="card-number"]').fill(cardNumber);
    await stripeFrame.locator('[data-testid="card-expiry"]').fill('12/30');
    await stripeFrame.locator('[data-testid="card-cvc"]').fill('123');
    await stripeFrame.locator('[data-testid="postal-code"]').fill('10001');
    await stripeFrame.locator('[data-testid="submit-button"]').click();

    // Wait for redirect back to app
    await this.page.waitForURL(/\/billing\/success/);
  }

  async getCreditsRemaining(): Promise<string> {
    const credits = this.page.locator('[data-testid="credits-remaining"]');
    return (await credits.textContent()) || '0';
  }

  async getPlanName(): Promise<string> {
    const plan = this.page.locator('[data-testid="current-plan"]');
    return (await plan.textContent()) || 'Free';
  }
}

// ---------------------------------------------------------------------------
// Test Fixtures
// ---------------------------------------------------------------------------

interface TestFixtures {
  authPage: AuthPage;
  uploadPage: UploadPage;
  renderPage: RenderPage;
  downloadPage: DownloadPage;
  billingPage: BillingPage;
}

const testWithPages = test.extend<TestFixtures>({
  authPage: async ({ page }, use) => {
    await use(new AuthPage(page));
  },
  uploadPage: async ({ page }, use) => {
    await use(new UploadPage(page));
  },
  renderPage: async ({ page }, use) => {
    await use(new RenderPage(page));
  },
  downloadPage: async ({ page }, use) => {
    await use(new DownloadPage(page));
  },
  billingPage: async ({ page }, use) => {
    await use(new BillingPage(page));
  },
});

// Test user credentials
const TEST_USER = {
  name: 'E2E Test User',
  email: `e2e-test-${Date.now()}@example.com`,
  password: 'TestPassword123!',
};

const TEST_VIDEO_PATH = './e2e/fixtures/sample-video.mp4';

// ---------------------------------------------------------------------------
// Test Suite: Full Signup → Upload → Render → Download Flow
// ---------------------------------------------------------------------------

testWithPages.describe('Full User Flow: Signup → Upload → Render → Download', () => {
  testWithPages(
    'complete flow from signup through video download',
    async ({ authPage, uploadPage, renderPage, downloadPage, page }) => {
      // Step 1: Sign up
      await authPage.goto();
      await authPage.signup(TEST_USER.email, TEST_USER.password, TEST_USER.name);
      await expect(page).toHaveURL(/\/(dashboard|onboarding)/);

      // Step 2: Upload video
      await uploadPage.goto();
      await uploadPage.uploadVideo(TEST_VIDEO_PATH);
      await uploadPage.waitForAnalysisComplete();

      // Verify segments were generated
      const segmentCount = await uploadPage.getSegmentCount();
      expect(segmentCount).toBeGreaterThan(0);

      // Step 3: Render
      await renderPage.selectAllSegments();
      await renderPage.startRender();
      await renderPage.waitForRenderComplete();

      // Step 4: Download
      const download = await downloadPage.downloadClip(0);
      expect(download).toBeTruthy();
      const fileName = download.suggestedFilename();
      expect(fileName).toMatch(/\.(mp4|webm)$/);
    }
  );

  testWithPages('user can re-login and access previous projects', async ({ authPage, page }) => {
    // Login with existing test account
    await authPage.login(TEST_USER.email, TEST_USER.password);
    await expect(page).toHaveURL(/\/dashboard/);

    // Verify project history is visible
    const projects = page.locator('[data-testid="project-card"]');
    await expect(projects.first()).toBeVisible();
  });

  testWithPages('upload progress shows percentage', async ({ authPage, uploadPage, page }) => {
    await authPage.login(TEST_USER.email, TEST_USER.password);
    await uploadPage.goto();

    // Start upload and verify progress indicator appears
    const fileInput = page.locator('[data-testid="video-upload-input"]');
    await fileInput.setInputFiles(TEST_VIDEO_PATH);

    const progress = page.locator('[data-testid="upload-progress"]');
    await expect(progress).toBeVisible();
  });

  testWithPages('render progress updates via SSE/WebSocket', async ({ authPage, uploadPage, renderPage, page }) => {
    await authPage.login(TEST_USER.email, TEST_USER.password);
    await uploadPage.goto();
    await uploadPage.uploadVideo(TEST_VIDEO_PATH);
    await uploadPage.waitForAnalysisComplete();

    await renderPage.selectSegment(0);
    await renderPage.startRender();

    // Verify progress updates appear
    const progressEl = page.locator('[data-testid="render-progress"]');
    await expect(progressEl).toBeVisible();

    // Progress should eventually reach 100% or show complete
    await renderPage.waitForRenderComplete();
  });
});

// ---------------------------------------------------------------------------
// Test Suite: Payment Flow (Stripe Test Mode)
// ---------------------------------------------------------------------------

testWithPages.describe('Payment Flow (Stripe Test Mode)', () => {
  testWithPages.beforeEach(async ({ authPage }) => {
    await authPage.login(TEST_USER.email, TEST_USER.password);
  });

  testWithPages('upgrade from Free to Pro plan', async ({ billingPage, page }) => {
    await billingPage.goto();

    // Verify starting on Free plan
    const currentPlan = await billingPage.getPlanName();
    expect(currentPlan.toLowerCase()).toContain('free');

    // Select Pro plan
    await billingPage.selectPlan('pro');

    // Complete Stripe checkout with test card
    await billingPage.completeStripeCheckout('4242424242424242');

    // Verify upgrade successful
    await page.waitForURL(/\/billing\/success/);
    await billingPage.goto();
    const updatedPlan = await billingPage.getPlanName();
    expect(updatedPlan.toLowerCase()).toContain('pro');
  });

  testWithPages('displays correct credit balance after upgrade', async ({ billingPage }) => {
    await billingPage.goto();
    const credits = await billingPage.getCreditsRemaining();
    expect(parseInt(credits)).toBe(30); // Pro plan = 30 credits/month
  });

  testWithPages('stripe checkout with declined card shows error', async ({ billingPage, page }) => {
    await billingPage.goto();
    await billingPage.selectPlan('business');

    // Use Stripe's test declined card number
    await billingPage.completeStripeCheckout('4000000000000002');

    // Should show error message
    const error = page.locator('[data-testid="payment-error"]');
    await expect(error).toBeVisible();
  });

  testWithPages('customer portal allows subscription management', async ({ billingPage, page }) => {
    await billingPage.goto();
    await page.click('[data-testid="manage-subscription"]');

    // Should redirect to Stripe Customer Portal
    await page.waitForURL(/.*stripe\.com.*portal.*/);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: Error States
// ---------------------------------------------------------------------------

testWithPages.describe('Error States', () => {
  testWithPages.beforeEach(async ({ authPage }) => {
    await authPage.login(TEST_USER.email, TEST_USER.password);
  });

  testWithPages('upload failure: unsupported file type shows error', async ({ uploadPage, page }) => {
    await uploadPage.goto();

    // Try uploading a non-video file
    const fileInput = page.locator('[data-testid="video-upload-input"]');
    await fileInput.setInputFiles('./e2e/fixtures/invalid-file.txt');

    const error = page.locator('[data-testid="upload-error"]');
    await expect(error).toBeVisible();
    await expect(error).toContainText(/unsupported|invalid/i);
  });

  testWithPages('upload failure: file too large shows error', async ({ uploadPage, page }) => {
    await uploadPage.goto();

    // Mock a file size check failure
    await page.route('**/api/upload/presign', (route) => {
      route.fulfill({
        status: 413,
        body: JSON.stringify({ error: 'File too large. Maximum size is 2GB.' }),
      });
    });

    const fileInput = page.locator('[data-testid="video-upload-input"]');
    await fileInput.setInputFiles(TEST_VIDEO_PATH);

    const error = page.locator('[data-testid="upload-error"]');
    await expect(error).toBeVisible();
    await expect(error).toContainText(/too large|size limit/i);
  });

  testWithPages('render failure: shows retry option', async ({ uploadPage, renderPage, page }) => {
    await uploadPage.goto();

    // Mock render failure
    await page.route('**/api/v1/projects/*/render', (route) => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Render worker unavailable' }),
      });
    });

    await uploadPage.uploadVideo(TEST_VIDEO_PATH);
    await uploadPage.waitForAnalysisComplete();
    await renderPage.selectSegment(0);
    await renderPage.startRender();

    // Should show error with retry button
    const error = page.locator('[data-testid="render-error"]');
    await expect(error).toBeVisible();

    const retryButton = page.locator('[data-testid="retry-render"]');
    await expect(retryButton).toBeVisible();
  });

  testWithPages('render failure: timeout shows timeout message', async ({ uploadPage, renderPage, page }) => {
    await uploadPage.goto();

    // Mock render timeout via SSE
    await page.route('**/api/v1/projects/*/status', (route) => {
      route.fulfill({
        status: 408,
        body: JSON.stringify({ error: 'Render timed out after 5 minutes' }),
      });
    });

    await uploadPage.uploadVideo(TEST_VIDEO_PATH);
    await uploadPage.waitForAnalysisComplete();
    await renderPage.selectSegment(0);
    await renderPage.startRender();

    const timeout = page.locator('[data-testid="render-timeout"]');
    await expect(timeout).toBeVisible({ timeout: 310000 });
  });

  testWithPages('payment failure: credits exhausted blocks render', async ({ uploadPage, renderPage, page }) => {
    // Mock credits check returning 0
    await page.route('**/api/v1/credits', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          credits_remaining: 0,
          credits_total: 3,
          plan: 'free',
          unlimited: false,
        }),
      });
    });

    await uploadPage.goto();
    await uploadPage.uploadVideo(TEST_VIDEO_PATH);
    await uploadPage.waitForAnalysisComplete();
    await renderPage.selectSegment(0);
    await renderPage.startRender();

    // Should show upgrade prompt
    const upgradePrompt = page.locator('[data-testid="upgrade-prompt"]');
    await expect(upgradePrompt).toBeVisible();
    await expect(upgradePrompt).toContainText(/upgrade|credits/i);
  });

  testWithPages('network error shows offline indicator', async ({ page }) => {
    // Simulate going offline
    await page.context().setOffline(true);

    // Navigate (will fail)
    await page.goto('/dashboard').catch(() => {});

    const offlineIndicator = page.locator('[data-testid="offline-indicator"]');
    await expect(offlineIndicator).toBeVisible();

    // Restore online
    await page.context().setOffline(false);
  });

  testWithPages('session expired redirects to login', async ({ page }) => {
    // Mock 401 response
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 401,
        body: JSON.stringify({ error: 'Session expired' }),
      });
    });

    await page.goto('/dashboard');
    await page.waitForURL(/\/auth\/login/);
  });

  testWithPages('API rate limiting shows appropriate message', async ({ uploadPage, page }) => {
    // Mock 429 response
    await page.route('**/api/v1/projects', (route) => {
      route.fulfill({
        status: 429,
        body: JSON.stringify({
          error: 'Rate limit exceeded. Please wait before trying again.',
        }),
        headers: { 'Retry-After': '60' },
      });
    });

    await uploadPage.goto();
    const rateLimitMsg = page.locator('[data-testid="rate-limit-error"]');
    // Trigger action that calls the API
    await page.click('[data-testid="new-project-button"]').catch(() => {});
    await expect(rateLimitMsg).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Test Suite: Accessibility & Navigation
// ---------------------------------------------------------------------------

testWithPages.describe('Accessibility & Navigation', () => {
  testWithPages('signup form is keyboard navigable', async ({ page }) => {
    await page.goto('/auth/signup');

    // Tab through all form fields
    await page.keyboard.press('Tab');
    const activeElement = page.locator(':focus');
    await expect(activeElement).toHaveAttribute('data-testid', 'signup-name');

    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toHaveAttribute('data-testid', 'signup-email');
  });

  testWithPages('page has proper heading hierarchy', async ({ page }) => {
    await page.goto('/');

    const h1Count = await page.locator('h1').count();
    expect(h1Count).toBe(1); // Only one h1 per page
  });
});
