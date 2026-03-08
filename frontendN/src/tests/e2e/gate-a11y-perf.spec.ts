import { test, expect, type Page, type Request, type Locator } from "@playwright/test";

type MockJsonResult = {
  status?: number;
  body?: unknown;
};

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
  "access-control-allow-headers": "*",
};

const DEFAULT_USER = {
  id: 1,
  email: "qa@example.com",
  email_verified: true,
  is_active: true,
  onboarding_completed: true,
  onboarding_current_step: 4,
  basic_info_completed: true,
  goal_selection_completed: true,
  path_selection_completed: true,
  preferences_completed: true,
};

const DASHBOARD_SUMMARY = {
  meals_card: {
    meals_planned: 3,
    meals_consumed: 1,
    meals_skipped: 0,
    next_meal: "Lunch",
    next_meal_time: "13:00",
  },
  macros_card: {
    calories_consumed: 1200,
    calories_target: 2200,
    calories_percentage: 55,
    protein_consumed: 75,
    protein_target: 150,
    protein_percentage: 50,
    carbs_consumed: 120,
    carbs_target: 220,
    carbs_percentage: 54,
    fat_consumed: 40,
    fat_target: 70,
    fat_percentage: 57,
  },
  inventory_card: {
    expiring_soon_count: 1,
    low_stock_count: 2,
    out_of_stock_count: 0,
    total_items: 26,
  },
  goal_card: {
    goal_type: "fat_loss",
    current_weight: 82.2,
    target_weight: 75,
    weight_change: -7.2,
    current_streak: 5,
    goal_progress_percentage: 42,
  },
};

async function mockJsonRoute(
  page: Page,
  urlPattern: string,
  responder: (request: Request) => MockJsonResult | Promise<MockJsonResult>
) {
  await page.route(urlPattern, async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: CORS_HEADERS,
      });
      return;
    }

    const response = await responder(route.request());
    await route.fulfill({
      status: response.status ?? 200,
      headers: {
        ...CORS_HEADERS,
        "content-type": "application/json",
      },
      body: JSON.stringify(response.body ?? {}),
    });
  });
}

async function seedSession(page: Page, token = "test-access-token", email = "qa@example.com") {
  await page.addInitScript(
    ({ sessionToken, sessionEmail }) => {
      window.localStorage.setItem("access_token", sessionToken);
      window.localStorage.setItem("user_email", sessionEmail);
    },
    { sessionToken: token, sessionEmail: email }
  );
}

async function mockAuth(page: Page) {
  await mockJsonRoute(page, "**/api/auth/v2/me", async () => ({
    body: {
      data: {
        user: DEFAULT_USER,
        onboarding: {
          completed: true,
          current_step: 4,
          completed_steps: [1, 2, 3, 4],
          redirect_to: "/dashboard",
          next_step_name: null,
        },
      },
    },
  }));
}

async function mockDashboardData(page: Page) {
  await mockAuth(page);

  await mockJsonRoute(page, "**/api/dashboard/v2/summary", async () => ({
    body: DASHBOARD_SUMMARY,
  }));

  await mockJsonRoute(page, "**/api/dashboard/v2/recent-activity*", async () => ({
    body: {
      activities: [
        {
          id: 1,
          type: "meal_logged",
          description: "Breakfast logged",
          timestamp: new Date().toISOString(),
          icon: "B",
        },
      ],
      total_count: 1,
    },
  }));
}

async function mockInventoryData(page: Page) {
  await mockAuth(page);

  await mockJsonRoute(page, "**/api/inventory/v2/status", async () => ({
    body: {
      total_items: 12,
      total_weight_g: 12400,
      expiring_soon: [],
      expired_items: [],
      low_stock: [],
      categories: {
        Produce: 4,
      },
      nutritional_capacity: {
        protein_g: 120,
        carbs_g: 240,
        fat_g: 90,
        calories: 2200,
      },
      estimated_days_remaining: 5,
      ai_recommendations: ["Keep pantry rotation weekly."],
    },
  }));

  await mockJsonRoute(page, "**/api/inventory/v2/items*", async () => ({
    body: {
      count: 2,
      items: [
        {
          id: 1,
          item_id: 11,
          item_name: "Spinach",
          category: "Produce",
          quantity_grams: 300,
          expiry_date: "2026-03-02",
          days_until_expiry: 3,
          is_depleted: false,
          is_low_stock: false,
        },
        {
          id: 2,
          item_id: 12,
          item_name: "Greek Yogurt",
          category: "Dairy",
          quantity_grams: 900,
          expiry_date: "2026-03-05",
          days_until_expiry: 6,
          is_depleted: false,
          is_low_stock: false,
        },
      ],
    },
  }));

  await mockJsonRoute(page, "**/api/receipt/v2/pending", async () => ({
    body: {
      count: 0,
      items: [],
    },
  }));
}

async function tabToElement(page: Page, locator: Locator, maxTabs = 80): Promise<boolean> {
  for (let idx = 0; idx < maxTabs; idx += 1) {
    await page.keyboard.press("Tab");
    const isFocused = await locator
      .evaluate((element) => element === document.activeElement)
      .catch(() => false);

    if (isFocused) {
      return true;
    }
  }

  return false;
}

test.describe("A11Y_PERF", () => {
  test("A11Y-01 keyboard navigation works for top bar, dialogs, and forms", async ({ page }) => {
    await seedSession(page);
    await mockInventoryData(page);

    await page.goto("/dashboard/inventory");

    const globalSearch = page.getByLabel("Global command search");
    const addItemsButton = page.getByRole("button", { name: "Add Items" });
    const notificationsButton = page.getByRole("button", { name: "Open notifications" });

    await page.locator("body").click();

    const reachedSearch = await tabToElement(page, globalSearch, 40);
    expect(reachedSearch).toBeTruthy();
    await expect(globalSearch).toBeFocused();

    await globalSearch.fill("spinach");

    const reachedAddItems = await tabToElement(page, addItemsButton, 40);
    expect(reachedAddItems).toBeTruthy();
    await expect(addItemsButton).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);

    await notificationsButton.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText("Notifications")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByText("Notifications")).toHaveCount(0);
  });

  test("A11Y-02 focus ring behavior and aria labels are present on critical controls", async ({ page }) => {
    await seedSession(page);
    await mockDashboardData(page);

    await page.goto("/dashboard");

    const globalSearch = page.getByLabel("Global command search");
    const notificationsButton = page.getByRole("button", { name: "Open notifications" });

    await expect(globalSearch).toHaveAttribute("aria-label", "Global command search");
    await expect(notificationsButton).toHaveAttribute("aria-label", "Open notifications");

    await page.locator("body").click();
    const reachedNotifications = await tabToElement(page, notificationsButton, 40);
    expect(reachedNotifications).toBeTruthy();
    await expect(notificationsButton).toBeFocused();

    const focusStyle = await notificationsButton.evaluate((element) => {
      const styles = window.getComputedStyle(element);
      return {
        outlineStyle: styles.outlineStyle,
        boxShadow: styles.boxShadow,
      };
    });

    expect(focusStyle.outlineStyle !== "none" || focusStyle.boxShadow !== "none").toBeTruthy();
  });

  test("PERF-01 dashboard warm navigation remains within agreed baseline", async ({ page }) => {
    test.setTimeout(45000);

    await seedSession(page);
    await mockDashboardData(page);

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Plan. Eat. Track. Adapt." })).toBeVisible();

    const start = Date.now();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Plan. Eat. Track. Adapt." })).toBeVisible();
    const elapsed = Date.now() - start;

    const navigationTiming = await page.evaluate(() => {
      const entries = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
      const latest = entries[entries.length - 1];
      return {
        domContentLoaded: latest?.domContentLoadedEventEnd ?? 0,
        load: latest?.loadEventEnd ?? 0,
      };
    });

    expect(elapsed).toBeLessThan(12000);
    expect(navigationTiming.domContentLoaded).toBeLessThan(10000);
    expect(navigationTiming.load).toBeLessThan(12000);
  });
});
