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

const DEFAULT_ONBOARDING = {
  completed: true,
  current_step: 4,
  completed_steps: [1, 2, 3, 4],
  redirect_to: "/dashboard",
  next_step_name: null,
};

function buildHistory(days: number) {
  if (days === 7) {
    return {
      period: { start_date: "2026-02-21", end_date: "2026-02-27", days: 7 },
      statistics: {
        total_meals: 21,
        logged_meals: 17,
        skipped_meals: 4,
        adherence_rate: 81,
      },
      history: [
        {
          date: "2026-02-21",
          meals: [
            { status: "logged" },
            { status: "logged" },
            { status: "skipped" },
          ],
        },
        {
          date: "2026-02-22",
          meals: [
            { status: "logged" },
            { status: "logged" },
            { status: "logged" },
          ],
        },
        {
          date: "2026-02-23",
          meals: [
            { status: "logged" },
            { status: "skipped" },
            { status: "logged" },
          ],
        },
      ],
    };
  }

  return {
    period: { start_date: "2026-01-29", end_date: "2026-02-27", days: 30 },
    statistics: {
      total_meals: 90,
      logged_meals: 62,
      skipped_meals: 28,
      adherence_rate: 69,
    },
    history: [],
  };
}

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

async function mockAuth(page: Page, overrides?: { email?: string; goal_type?: string }) {
  await mockJsonRoute(page, "**/api/auth/v2/me", async () => ({
    body: {
      data: {
        user: {
          ...DEFAULT_USER,
          email: overrides?.email ?? DEFAULT_USER.email,
          goal_type: overrides?.goal_type,
        },
        onboarding: DEFAULT_ONBOARDING,
      },
    },
  }));
}

async function mockNutritionScaffold(page: Page) {
  await mockAuth(page);

  await mockJsonRoute(page, "**/api/tracking/v2/today", async () => ({
    body: {
      total_macros: {
        calories: 1550,
        protein_g: 118,
        carbs_g: 142,
        fat_g: 50,
      },
      target_macros: {
        calories: 2200,
        protein_g: 150,
        carbs_g: 220,
        fat_g: 70,
      },
    },
  }));

  await mockJsonRoute(page, "**/api/tracking/v2/history*", async (request) => {
    const days = Number(new URL(request.url()).searchParams.get("days") ?? "7");
    return {
      body: buildHistory(days),
    };
  });

  await mockJsonRoute(page, "**/api/dashboard/v2/summary", async () => ({
    body: {
      macros_card: {
        protein_percentage: 79,
        carbs_percentage: 65,
        fat_percentage: 71,
      },
    },
  }));
}

async function mockNutritionChatRoutes(
  page: Page,
  responder: (request: Request) => MockJsonResult | Promise<MockJsonResult>
) {
  // Match backend-only routes so we do not intercept frontend route /dashboard/nutrition/chat.
  await mockJsonRoute(page, "http://localhost:8000/api/nutrition/chat", responder);
  await mockJsonRoute(page, "http://localhost:8000/nutrition/chat", responder);
}

test.describe("NUTRITION", () => {
  test("NUT-01 nutrition analytics view loads trend cards", async ({ page }) => {
    await seedSession(page);
    await mockNutritionScaffold(page);

    await page.goto("/dashboard/nutrition");

    await expect(page.getByRole("heading", { name: "Nutrition Intelligence" })).toBeVisible();
    await expect(page.getByText("of 2200 target")).toBeVisible();
    await expect(page.getByText("of 150g target")).toBeVisible();
    await expect(page.getByText("17 logged meals this period")).toBeVisible();
    await expect(page.getByText("Adherence Trend (7 days)")).toBeVisible();
    await expect(page.getByText("Macro Snapshot")).toBeVisible();
    await expect(page.getByRole("button", { name: "Open AI Coach" })).toBeVisible();
  });

  test("NUT-02 chat request success and error recovery states", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page);

    let chatCalls = 0;
    await mockNutritionChatRoutes(page, async () => {
      chatCalls += 1;

      if (chatCalls === 1) {
        return {
          body: {
            response: "You are slightly below your protein target. Add 30g protein at dinner.",
            intent: "macro_guidance",
            processing_time_ms: 610,
            cost_usd: 0.0021,
          },
        };
      }

      return {
        status: 500,
        body: {
          detail: "Model unavailable",
        },
      };
    });

    await page.goto("/dashboard/nutrition/chat");

    const chatInput = page.getByPlaceholder("Ask anything about your nutrition...");

    await chatInput.fill("How is my protein today?");
    await chatInput.press("Enter");

    await expect(page.getByText("You are slightly below your protein target. Add 30g protein at dinner.")).toBeVisible();
    await expect(page.getByText("intent: macro_guidance")).toBeVisible();

    await chatInput.fill("What should I do for dinner?");
    await chatInput.press("Enter");

    await expect(page.getByText("I could not process that request. Please try again.")).toBeVisible();
    await expect.poll(() => chatCalls).toBe(2);

    await page.getByRole("button", { name: "New Chat" }).click();
    await expect(page.getByText("Hi! I am your AI nutrition assistant powered by LangGraph.")).toBeVisible();
  });

  test("NUT-03 chat context chips and session controls render correctly", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page);

    await mockNutritionChatRoutes(page, async () => ({
      body: {
        response: "Swap lunch carbs for a higher-protein option from your inventory.",
        intent: "meal_adjustment",
        processing_time_ms: 540,
        cost_usd: 0.0018,
      },
    }));

    await page.goto("/dashboard/nutrition/chat");

    const chatShell = page.locator("div[data-slot='card']").first();
    await expect(chatShell.getByText("Meals", { exact: true })).toBeVisible();
    await expect(chatShell.getByText("Inventory", { exact: true })).toBeVisible();
    await expect(chatShell.getByText("Goals", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "New Chat" })).toBeVisible();

    const chatInput = page.getByPlaceholder("Ask anything about your nutrition...");
    await chatInput.fill("Suggest a better lunch option");
    await chatInput.press("Enter");

    await expect(page.getByText("Swap lunch carbs for a higher-protein option from your inventory.")).toBeVisible();
    await expect(page.getByText("intent: meal_adjustment")).toBeVisible();
  });
});

test.describe("PROFILE_SETTINGS", () => {
  test("PRO-01 profile MVP renders user info and saves editable safe fields", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page, {
      email: "pro.user@example.com",
      goal_type: "muscle_gain",
    });

    await page.goto("/dashboard/profile");

    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
    await expect(page.getByText("pro.user@example.com")).toBeVisible();
    await expect(page.getByText("muscle_gain")).toBeVisible();

    const displayNameInput = page.getByLabel("Display Name");
    await displayNameInput.fill("Darsh");
    await page.getByRole("button", { name: "Save Preferences" }).click();

    await expect(page.getByText("Profile preferences saved")).toBeVisible();

    await page.reload();
    await expect(page.getByText("Darsh")).toBeVisible();
    await expect(displayNameInput).toHaveValue("Darsh");
  });

  test("SET-01 settings MVP persists allowed local preferences", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page);

    await page.goto("/dashboard/settings");

    const autoRefresh = page.getByLabel("Auto Refresh Data");
    const compactMode = page.getByLabel("Compact Layout Mode");
    const showHints = page.getByLabel("Show Action Hints");

    await expect(autoRefresh).toHaveAttribute("data-state", "checked");
    await expect(compactMode).toHaveAttribute("data-state", "unchecked");
    await expect(showHints).toHaveAttribute("data-state", "checked");

    await autoRefresh.click();
    await compactMode.click();
    await showHints.click();

    await expect(autoRefresh).toHaveAttribute("data-state", "unchecked");
    await expect(compactMode).toHaveAttribute("data-state", "checked");
    await expect(showHints).toHaveAttribute("data-state", "unchecked");

    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByText("Settings saved locally")).toBeVisible();

    await page.reload();

    await expect(autoRefresh).toHaveAttribute("data-state", "unchecked");
    await expect(compactMode).toHaveAttribute("data-state", "checked");
    await expect(showHints).toHaveAttribute("data-state", "unchecked");
  });
});
