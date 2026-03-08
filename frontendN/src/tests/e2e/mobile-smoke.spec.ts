import { test, expect, type Page, type Request } from "@playwright/test";

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

const TRACKING_TODAY = {
  date: "2026-02-27",
  meals_planned: 1,
  meals_consumed: 0,
  meals_skipped: 0,
  total_calories: 0,
  total_macros: {
    calories: 0,
    protein_g: 0,
    carbs_g: 0,
    fat_g: 0,
    fiber_g: 0,
  },
  target_calories: 2200,
  target_macros: {
    calories: 2200,
    protein_g: 150,
    carbs_g: 220,
    fat_g: 70,
    fiber_g: 30,
  },
  remaining_calories: 2200,
  remaining_macros: {
    calories: 2200,
    protein_g: 150,
    carbs_g: 220,
    fat_g: 70,
    fiber_g: 30,
  },
  compliance_rate: 0,
  meal_details: [
    {
      id: 11,
      meal_type: "breakfast",
      planned_time: "2026-02-27T08:30:00.000Z",
      recipe: "Greek Yogurt Bowl",
      status: "pending",
      recipe_id: 101,
      macros: {
        calories: 420,
        protein_g: 28,
        carbs_g: 42,
        fat_g: 12,
        fiber_g: 6,
      },
    },
  ],
  recommendations: ["Start with hydration before breakfast."],
};

const TRACKING_HISTORY = {
  period: { start_date: "2026-02-21", end_date: "2026-02-27", days: 7 },
  statistics: {
    total_meals: 21,
    logged_meals: 17,
    skipped_meals: 4,
    adherence_rate: 81,
  },
  history: [
    {
      date: "2026-02-27",
      meals: [
        { status: "logged" },
        { status: "logged" },
        { status: "skipped" },
      ],
    },
  ],
};

const MEAL_PLAN = {
  id: 1,
  week_start_date: "2026-02-23",
  plan_data: {
    day_0: {
      meals: {
        breakfast: {
          id: 101,
          title: "Greek Yogurt Bowl",
          macros_per_serving: {
            calories: 420,
            protein_g: 28,
            carbs_g: 42,
            fat_g: 12,
          },
          status: "pending",
        },
      },
    },
  },
};

const INVENTORY_STATUS = {
  total_items: 12,
  total_weight_g: 12400,
  expiring_soon: [],
  expired_items: [],
  low_stock: [],
  categories: {
    Produce: 4,
    Protein: 3,
  },
  nutritional_capacity: {
    protein_g: 420,
    carbs_g: 760,
    fat_g: 180,
    calories: 6420,
  },
  estimated_days_remaining: 6,
  ai_recommendations: ["Prioritize leafy greens this week."],
};

const INVENTORY_ITEMS = {
  count: 2,
  items: [
    {
      id: 201,
      item_id: 11,
      item_name: "Greek Yogurt",
      category: "Dairy",
      quantity_grams: 900,
      expiry_date: "2026-03-03",
      days_until_expiry: 4,
      is_depleted: false,
      is_low_stock: false,
    },
    {
      id: 202,
      item_id: 12,
      item_name: "Spinach",
      category: "Produce",
      quantity_grams: 300,
      expiry_date: "2026-03-01",
      days_until_expiry: 2,
      is_depleted: false,
      is_low_stock: true,
    },
  ],
};

async function mockJsonRoute(
  page: Page,
  urlPattern: string,
  responder: (request: Request) => MockJsonResult | Promise<MockJsonResult>
) {
  await page.route(urlPattern, async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: CORS_HEADERS });
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

async function mockMobileScaffold(page: Page) {
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

  await mockJsonRoute(page, "**/api/tracking/v2/today", async () => ({
    body: TRACKING_TODAY,
  }));

  await mockJsonRoute(page, "**/api/tracking/v2/history*", async () => ({
    body: TRACKING_HISTORY,
  }));

  await mockJsonRoute(page, "**/api/meal-plans/v2/current/with-status", async () => ({
    body: MEAL_PLAN,
  }));

  await mockJsonRoute(page, "**/api/meal-plans/v2/1/grocery-list", async () => ({
    body: { categorized: {} },
  }));

  await mockJsonRoute(page, "**/api/inventory/v2/status", async () => ({
    body: INVENTORY_STATUS,
  }));

  await mockJsonRoute(page, "**/api/inventory/v2/items*", async () => ({
    body: INVENTORY_ITEMS,
  }));

  await mockJsonRoute(page, "**/api/receipt/v2/pending", async () => ({
    body: { count: 0, items: [] },
  }));

  await mockJsonRoute(page, "http://localhost:8000/api/nutrition/chat", async () => ({
    body: {
      response: "Your lunch is low on protein. Add 25g protein from available pantry items.",
      intent: "macro_guidance",
      processing_time_ms: 510,
      cost_usd: 0.0017,
    },
  }));

  await mockJsonRoute(page, "http://localhost:8000/nutrition/chat", async () => ({
    body: {
      response: "Your lunch is low on protein. Add 25g protein from available pantry items.",
      intent: "macro_guidance",
      processing_time_ms: 510,
      cost_usd: 0.0017,
    },
  }));
}

test.describe("MOBILE_SMOKE", () => {
  test.use({
    viewport: {
      width: 390,
      height: 844,
    },
  });

  test("MOB-01 mobile bottom navigation reaches all core modules", async ({ page }) => {
    await seedSession(page);
    await mockMobileScaffold(page);

    await page.goto("/dashboard");

    await expect(page.getByRole("heading", { name: "Plan. Eat. Track. Adapt." })).toBeVisible();

    const mobileNav = page.locator("nav.fixed.bottom-0.left-0.right-0");
    await expect(mobileNav).toBeVisible();

    const navRoutes: Record<string, string> = {
      Meals: "/dashboard/meals",
      Inventory: "/dashboard/inventory",
      Nutrition: "/dashboard/nutrition",
      Profile: "/dashboard/profile",
    };

    const navTo = async (label: string) => {
      const targetRoute = navRoutes[label];
      const link = mobileNav.getByRole("link", { name: label });

      await Promise.all([
        page.waitForURL(`**${targetRoute}`),
        link.evaluate((element) => (element as HTMLAnchorElement).click()),
      ]);
    };

    await navTo("Meals");
    await expect(page.getByRole("heading", { name: "Meal Execution Hub" })).toBeVisible();

    await navTo("Inventory");
    await expect(page.getByRole("heading", { name: "Inventory Intelligence" })).toBeVisible();

    await navTo("Nutrition");
    await expect(page.getByRole("heading", { name: "Nutrition Intelligence" })).toBeVisible();

    await navTo("Profile");
    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
  });

  test("MOB-02 inventory dialogs are reachable and operable on mobile", async ({ page }) => {
    await seedSession(page);
    await mockMobileScaffold(page);

    await page.goto("/dashboard/inventory");

    await page.getByRole("button", { name: "Add Items" }).click({ force: true });
    const addDialog = page.getByRole("dialog");
    await expect(addDialog).toBeVisible();
    await expect(
      addDialog.getByPlaceholder("E.g., 2 apples, 500g chicken, 1L milk, 250g cheddar cheese...")
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);

    await page.getByRole("button", { name: "Scan Receipt" }).click({ force: true });
    const receiptDialog = page.getByRole("dialog");
    await expect(receiptDialog).toBeVisible();
    await expect(receiptDialog.getByRole("button", { name: "Choose File" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("MOB-03 nutrition chat composer works on mobile viewport", async ({ page }) => {
    await seedSession(page);
    await mockMobileScaffold(page);

    await page.goto("/dashboard/nutrition/chat");

    const input = page.getByPlaceholder("Ask anything about your nutrition...");
    await input.fill("How can I improve dinner protein?");
    await input.press("Enter");

    await expect(page.getByText("intent: macro_guidance")).toBeVisible();
    await expect(
      page.getByText("Your lunch is low on protein. Add 25g protein from available pantry items.")
    ).toBeVisible();
  });
});
