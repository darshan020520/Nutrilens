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

const DEFAULT_MACROS = {
  calories: 420,
  protein_g: 28,
  carbs_g: 42,
  fat_g: 12,
  fiber_g: 6,
};

function buildWeekPlan(status: "pending" | "logged" | "skipped", recipeName: string, recipeId = 101) {
  return {
    id: 1,
    week_start_date: "2026-02-23",
    plan_data: {
      day_0: {
        meals: {
          breakfast: {
            id: recipeId,
            title: recipeName,
            macros_per_serving: {
              calories: 420,
              protein_g: 28,
              carbs_g: 42,
              fat_g: 12,
            },
            status,
          },
        },
      },
    },
  };
}

function buildToday(status: "pending" | "consumed" | "skipped", recipeName: string, id = 11) {
  return {
    date: "2026-02-27",
    meals_planned: 1,
    meals_consumed: status === "consumed" ? 1 : 0,
    meals_skipped: status === "skipped" ? 1 : 0,
    total_calories: status === "consumed" ? 420 : 0,
    total_macros: {
      calories: status === "consumed" ? 420 : 0,
      protein_g: status === "consumed" ? 28 : 0,
      carbs_g: status === "consumed" ? 42 : 0,
      fat_g: status === "consumed" ? 12 : 0,
      fiber_g: status === "consumed" ? 6 : 0,
    },
    target_calories: 2200,
    target_macros: {
      calories: 2200,
      protein_g: 150,
      carbs_g: 220,
      fat_g: 70,
      fiber_g: 30,
    },
    remaining_calories: status === "consumed" ? 1780 : 2200,
    remaining_macros: {
      calories: status === "consumed" ? 1780 : 2200,
      protein_g: status === "consumed" ? 122 : 150,
      carbs_g: status === "consumed" ? 178 : 220,
      fat_g: status === "consumed" ? 58 : 70,
      fiber_g: status === "consumed" ? 24 : 30,
    },
    compliance_rate: status === "pending" ? 0 : 100,
    meal_details: [
      {
        id,
        meal_type: "breakfast",
        planned_time: "2026-02-27T08:30:00.000Z",
        recipe: recipeName,
        status,
        consumed_time: status === "consumed" ? "2026-02-27T08:45:00.000Z" : undefined,
        recipe_id: 101,
        macros: DEFAULT_MACROS,
      },
    ],
    recommendations: status === "pending" ? ["Start with hydration before breakfast."] : [],
  };
}

function buildHistory(days: number) {
  if (days === 30) {
    return {
      period: { start_date: "2026-01-28", end_date: "2026-02-27", days: 30 },
      statistics: {
        total_meals: 90,
        logged_meals: 54,
        skipped_meals: 36,
        adherence_rate: 60,
      },
      history: [
        {
          date: "2026-02-27",
          meals: [
            { meal_type: "breakfast", recipe_name: "Greek Yogurt Bowl", status: "logged", time: "08:45" },
            { meal_type: "lunch", recipe_name: "Chicken Bowl", status: "skipped" },
          ],
        },
      ],
    };
  }

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
        date: "2026-02-27",
        meals: [
          { meal_type: "breakfast", recipe_name: "Greek Yogurt Bowl", status: "logged", time: "08:45" },
          { meal_type: "lunch", recipe_name: "Chicken Bowl", status: "logged", time: "13:10" },
          { meal_type: "dinner", recipe_name: "Paneer Stir Fry", status: "skipped" },
        ],
      },
    ],
  };
}

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

function readJsonBody(request: Request): Record<string, unknown> {
  try {
    return request.postDataJSON() as Record<string, unknown>;
  } catch {
    return {};
  }
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

async function mockCommonMealsScaffold(page: Page, options?: { today?: unknown; week?: unknown; history7?: unknown }) {
  await mockAuth(page);

  await mockJsonRoute(page, "**/api/tracking/v2/today", async () => ({
    body: options?.today ?? buildToday("pending", "Greek Yogurt Bowl"),
  }));

  await mockJsonRoute(page, "**/api/meal-plans/v2/current/with-status", async () => ({
    body: options?.week ?? buildWeekPlan("pending", "Greek Yogurt Bowl"),
  }));

  await mockJsonRoute(page, "**/api/meal-plans/v2/1/grocery-list", async () => ({
    body: {
      categorized: {
        produce: [{ item_name: "Banana", to_buy: 500 }],
      },
    },
  }));

  await mockJsonRoute(page, "**/api/tracking/v2/history*", async (request) => {
    const url = new URL(request.url());
    const days = Number(url.searchParams.get("days") ?? "7");
    if (days === 7) {
      return { body: options?.history7 ?? buildHistory(7) };
    }
    return { body: buildHistory(days) };
  });
}

test.describe("MEALS", () => {
  test("MEAL-01 week plan renders with status badges", async ({ page }) => {
    await seedSession(page);
    await mockCommonMealsScaffold(page, {
      week: {
        id: 1,
        week_start_date: "2026-02-23",
        plan_data: {
          day_0: {
            meals: {
              breakfast: {
                id: 101,
                title: "Greek Yogurt Bowl",
                macros_per_serving: { calories: 420, protein_g: 28, carbs_g: 42, fat_g: 12 },
                status: "logged",
              },
              lunch: {
                id: 102,
                title: "Chicken Rice Bowl",
                macros_per_serving: { calories: 560, protein_g: 42, carbs_g: 55, fat_g: 16 },
                status: "pending",
              },
              dinner: {
                id: 103,
                title: "Paneer Stir Fry",
                macros_per_serving: { calories: 500, protein_g: 30, carbs_g: 36, fat_g: 22 },
                status: "skipped",
              },
            },
          },
        },
      },
    });

    await page.goto("/dashboard/meals?tab=week");

    await expect(page.getByText("Greek Yogurt Bowl")).toBeVisible();
    await expect(page.getByText("Chicken Rice Bowl")).toBeVisible();
    await expect(page.getByText("Paneer Stir Fry")).toBeVisible();
    await expect(page.getByText("Logged")).toBeVisible();
    await expect(page.getByText("Pending")).toBeVisible();
    await expect(page.getByText("Skipped")).toBeVisible();
  });

  test("MEAL-02 regenerate meal plan handles failure then success", async ({ page }) => {
    await seedSession(page);
    await mockCommonMealsScaffold(page);

    let regenerateCalls = 0;
    await mockJsonRoute(page, "**/api/meal-plans/v2/generate", async () => {
      regenerateCalls += 1;
      if (regenerateCalls === 1) {
        return { status: 500, body: { detail: "Generation failed" } };
      }
      return { body: { plan_id: 2, message: "generated" } };
    });

    await page.goto("/dashboard/meals?tab=week");
    await page.getByRole("button", { name: "Regenerate Plan" }).click();
    await expect(page.getByText("Generation failed")).toBeVisible();

    await page.getByRole("button", { name: "Regenerate Plan" }).click();
    await expect(page.getByText("New meal plan generated successfully!")).toBeVisible();
    await expect.poll(() => regenerateCalls).toBe(2);
  });

  test("MEAL-03 swap flow loads alternatives and commits swap", async ({ page }) => {
    await seedSession(page);
    await mockCommonMealsScaffold(page);

    let currentRecipe = "Greek Yogurt Bowl";
    let swapPayload: Record<string, unknown> | null = null;

    await page.unroute("**/api/meal-plans/v2/current/with-status");
    await mockJsonRoute(page, "**/api/meal-plans/v2/current/with-status", async () => ({
      body: buildWeekPlan("pending", currentRecipe, currentRecipe === "Greek Yogurt Bowl" ? 101 : 201),
    }));

    await mockJsonRoute(page, "**/api/meal-plans/v2/1/alternatives/101*", async () => ({
      body: [
        {
          recipe: {
            id: 201,
            title: "Cottage Cheese Bowl",
            macros_per_serving: { calories: 430, protein_g: 30, carbs_g: 40, fat_g: 13 },
            tags: ["high-protein"],
          },
          similarity_score: 0.94,
          calorie_difference: 10,
          protein_difference: 2,
          carbs_difference: -2,
          fat_difference: 1,
        },
      ],
    }));

    await mockJsonRoute(page, "**/api/meal-plans/v2/1/swap-meal", async (request) => {
      swapPayload = readJsonBody(request);
      currentRecipe = "Cottage Cheese Bowl";
      return { body: { message: "swapped" } };
    });

    await page.goto("/dashboard/meals?tab=week");
    await page.getByText("Greek Yogurt Bowl").first().click();
    await page.getByRole("button", { name: "Swap Meal" }).click();

    await expect(page.getByRole("heading", { name: "Swap Meal" })).toBeVisible();
    await expect(page.getByText("Cottage Cheese Bowl")).toBeVisible();
    await page.getByText("Cottage Cheese Bowl").click();
    await page.getByRole("button", { name: /^Swap Meal$/ }).click();

    await expect.poll(() => swapPayload?.new_recipe_id).toBe(201);
    await expect(page.getByText("Cottage Cheese Bowl")).toBeVisible();
  });

  test("MEAL-04 log meal updates today and week status", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page);

    let logged = false;
    await mockJsonRoute(page, "**/api/tracking/v2/today", async () => ({
      body: buildToday(logged ? "consumed" : "pending", "Greek Yogurt Bowl"),
    }));
    await mockJsonRoute(page, "**/api/meal-plans/v2/current/with-status", async () => ({
      body: buildWeekPlan(logged ? "logged" : "pending", "Greek Yogurt Bowl"),
    }));
    await mockJsonRoute(page, "**/api/meal-plans/v2/1/grocery-list", async () => ({
      body: { categorized: {} },
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/history*", async () => ({
      body: buildHistory(7),
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/log-meal", async () => {
      logged = true;
      return {
        body: {
          recipe_name: "Greek Yogurt Bowl",
          recommendations: ["Keep hydration high for the next meal."],
          remaining_targets: { calories: 1780 },
        },
      };
    });

    await page.goto("/dashboard/meals?tab=today");
    await page.getByRole("button", { name: "Log Meal" }).click();

    await expect(page.getByText("Greek Yogurt Bowl logged!")).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
    await expect(page.getByText("Logged").first()).toBeVisible();

    await page.getByRole("tab", { name: "This Week" }).click();
    await expect(page.getByText("Logged").first()).toBeVisible();
  });

  test("MEAL-05 skip meal captures reason and renders recommendations", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page);

    let skipped = false;
    let capturedReason = "";

    await mockJsonRoute(page, "**/api/tracking/v2/today", async () => ({
      body: buildToday(skipped ? "skipped" : "pending", "Greek Yogurt Bowl"),
    }));
    await mockJsonRoute(page, "**/api/meal-plans/v2/current/with-status", async () => ({
      body: buildWeekPlan("pending", "Greek Yogurt Bowl"),
    }));
    await mockJsonRoute(page, "**/api/meal-plans/v2/1/grocery-list", async () => ({
      body: { categorized: {} },
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/history*", async () => ({
      body: buildHistory(7),
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/skip-meal", async (request) => {
      const payload = readJsonBody(request);
      capturedReason = String(payload.skip_reason ?? "");
      skipped = true;
      return {
        body: {
          recipe_name: "Greek Yogurt Bowl",
          recommendations: ["Add a high-protein snack before lunch."],
          updated_adherence_rate: 0.74,
        },
      };
    });

    await page.goto("/dashboard/meals?tab=today");
    await page.getByRole("button", { name: "Skip" }).click();
    await page.getByLabel("Reason (optional)").fill("Travel schedule changed");
    await page.getByRole("button", { name: "Skip Meal" }).click();

    await expect.poll(() => capturedReason).toBe("Travel schedule changed");
    await expect(page.getByRole("heading", { name: "Recommendations", exact: true })).toBeVisible();
    await expect(page.getByText("Add a high-protein snack before lunch.")).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
    await expect(page.getByText("Skipped").first()).toBeVisible();
  });

  test("MEAL-06 external meal estimate-adjust-confirm flow works", async ({ page }) => {
    await seedSession(page);
    await mockAuth(page);

    let capturedCalories = 0;
    let replacedMealId: number | null = null;

    await mockJsonRoute(page, "**/api/tracking/v2/today", async () => ({
      body: buildToday("pending", "Greek Yogurt Bowl"),
    }));
    await mockJsonRoute(page, "**/api/meal-plans/v2/current/with-status", async () => ({
      body: buildWeekPlan("pending", "Greek Yogurt Bowl"),
    }));
    await mockJsonRoute(page, "**/api/meal-plans/v2/1/grocery-list", async () => ({
      body: { categorized: {} },
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/history*", async () => ({
      body: buildHistory(7),
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/estimate-external-meal", async () => ({
      body: {
        calories: 720,
        protein_g: 32,
        carbs_g: 80,
        fat_g: 24,
        fiber_g: 8,
        confidence: 0.81,
        reasoning: "Estimated from dish and portion size.",
        estimation_method: "llm",
      },
    }));
    await mockJsonRoute(page, "**/api/tracking/v2/log-external-meal", async (request) => {
      const payload = readJsonBody(request);
      capturedCalories = Number(payload.calories ?? 0);
      replacedMealId = Number(payload.meal_log_id_to_replace ?? 0);
      return {
        body: {
          replaced_meal: true,
          original_recipe: "Greek Yogurt Bowl",
          recommendations: ["Keep dinner lighter to balance calories."],
          insights: ["Higher carbs than your planned breakfast."],
          remaining_calories: 1380,
        },
      };
    });

    await page.goto("/dashboard/meals?tab=today");
    await page.getByRole("button", { name: "External Meal" }).click();

    await page.getByLabel(/Dish Name/i).fill("Chicken Burrito Bowl");
    await page.getByLabel(/Portion Size/i).fill("1 large bowl");
    await page.getByRole("button", { name: "Get AI Estimate" }).click();

    await expect(page.getByRole("heading", { name: "Estimated Nutrition" })).toBeVisible();
    await page.getByLabel("Calories (kcal)").fill("680");
    await page.getByRole("button", { name: "Replace & Log Meal" }).click();

    await expect.poll(() => capturedCalories).toBe(680);
    await expect.poll(() => replacedMealId).toBe(11);
    await expect(page.getByRole("heading", { name: "Recommendations", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
  });

  test("MEAL-07 recipe search, filters, and pagination work", async ({ page }) => {
    await seedSession(page);
    await mockCommonMealsScaffold(page);

    const queryLog: string[] = [];
    await mockJsonRoute(page, "**/api/recipes/v2/*", async (request) => {
      const url = new URL(request.url());
      queryLog.push(url.search);
      const offset = Number(url.searchParams.get("offset") ?? "0");
      const search = url.searchParams.get("search") ?? "";
      const goal = url.searchParams.get("goal") ?? "";

      const prefix = search ? "Chicken Recipe" : "Recipe";
      if (offset >= 20) {
        return {
          body: Array.from({ length: 5 }, (_, idx) => ({
            id: 200 + idx + 1,
            title: `${prefix} ${offset + idx + 1}`,
            cuisine: goal ? "weight_loss" : "indian",
            macros_per_serving: { calories: 400, protein_g: 30, carbs_g: 35, fat_g: 12 },
            servings: 1,
          })),
        };
      }

      return {
        body: Array.from({ length: 20 }, (_, idx) => ({
          id: idx + 1,
          title: `${prefix} ${idx + 1}`,
          cuisine: goal ? "weight_loss" : "indian",
          macros_per_serving: { calories: 420, protein_g: 28, carbs_g: 42, fat_g: 12 },
          servings: 1,
        })),
      };
    });

    await page.goto("/dashboard/meals");
    await page.getByRole("tab", { name: "Recipes" }).click();
    await page.getByPlaceholder("Search recipes...").fill("chicken");
    await page.getByRole("button", { name: "Search" }).click();

    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "Weight Loss" }).click();

    await expect(page.getByRole("heading", { name: "Chicken Recipe 1", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("Page 2")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Chicken Recipe 21", exact: true })).toBeVisible();

    expect(queryLog.some((q) => q.includes("search=chicken"))).toBeTruthy();
    expect(queryLog.some((q) => q.includes("goal=weight_loss"))).toBeTruthy();
    expect(queryLog.some((q) => q.includes("offset=20"))).toBeTruthy();
  });

  test("MEAL-08 recipe details modal is stable with missing optional fields", async ({ page }) => {
    await seedSession(page);
    await mockCommonMealsScaffold(page);

    await mockJsonRoute(page, "**/api/recipes/v2/*", async (request) => {
      const url = new URL(request.url());
      if (url.pathname.endsWith("/recipes/v2/99")) {
        return {
          body: {
            id: 99,
            title: "Minimal Macro Salad",
            servings: 1,
            macros_per_serving: { calories: 310, protein_g: 18, carbs_g: 24, fat_g: 14 },
            // intentionally missing description, ingredients, instructions
          },
        };
      }

      return {
        body: [
          {
            id: 99,
            title: "Minimal Macro Salad",
            macros_per_serving: { calories: 310, protein_g: 18, carbs_g: 24, fat_g: 14 },
            servings: 1,
          },
        ],
      };
    });

    await page.goto("/dashboard/meals");
    await page.getByRole("tab", { name: "Recipes" }).click();
    await page.getByText("Minimal Macro Salad").click();

    await expect(page.getByRole("heading", { name: "Minimal Macro Salad" })).toBeVisible();
    await expect(page.getByText("Nutrition (per serving)")).toBeVisible();
    await expect(page.getByText("Calories")).toBeVisible();
  });

  test("MEAL-09 history range changes update adherence analytics", async ({ page }) => {
    await seedSession(page);
    await mockCommonMealsScaffold(page, {
      history7: buildHistory(7),
    });

    await page.goto("/dashboard/meals");
    await page.getByRole("tab", { name: "History" }).click();

    await expect(page.getByText("81%", { exact: true })).toBeVisible();

    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "Last 30 Days" }).click();

    await expect(page.getByText("60%", { exact: true })).toBeVisible();
    await expect(page.getByText("90")).toBeVisible(); // total meals updated
  });
});
