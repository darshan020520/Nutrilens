import { test, expect, type Page, type Request } from "@playwright/test";

type MockJsonResult = {
  status?: number;
  body?: unknown;
};

type InventoryItemRecord = {
  id: number;
  item_id: number;
  item_name: string;
  category: string;
  quantity_grams: number;
  expiry_date: string | null;
  days_until_expiry: number | null;
  is_depleted: boolean;
  is_low_stock?: boolean;
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

const BASE_INVENTORY_STATUS = {
  total_items: 12,
  total_weight_g: 12400,
  expiring_soon: [
    {
      item_name: "Spinach",
      quantity_grams: 150,
      days_until_expiry: 2,
    },
  ],
  expired_items: [],
  low_stock: [
    {
      item_name: "Spinach",
      quantity_grams: 150,
      category: "Produce",
    },
  ],
  categories: {
    Produce: 4,
    Protein: 3,
    Dairy: 2,
    Grains: 3,
  },
  nutritional_capacity: {
    protein_g: 420,
    carbs_g: 760,
    fat_g: 180,
    calories: 6420,
  },
  estimated_days_remaining: 6,
  ai_recommendations: ["Prioritize spinach and leafy greens within 48 hours."],
};

const BASE_INVENTORY_ITEMS: InventoryItemRecord[] = [
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
    quantity_grams: 150,
    expiry_date: "2026-03-01",
    days_until_expiry: 2,
    is_depleted: false,
    is_low_stock: true,
  },
  {
    id: 203,
    item_id: 13,
    item_name: "Chicken Breast",
    category: "Protein",
    quantity_grams: 1200,
    expiry_date: null,
    days_until_expiry: null,
    is_depleted: false,
    is_low_stock: false,
  },
];

type InventoryScaffoldOptions = {
  status?: unknown;
  items?: InventoryItemRecord[];
  pendingItems?: unknown[];
  onItemsRequest?: (query: string) => void;
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

function filterInventoryItems(items: InventoryItemRecord[], requestUrl: string): InventoryItemRecord[] {
  const url = new URL(requestUrl);
  const category = url.searchParams.get("category");
  const lowStockOnly = url.searchParams.get("low_stock_only") === "true";
  const expiringSoon = url.searchParams.get("expiring_soon") === "true";

  let filtered = [...items];

  if (category) {
    filtered = filtered.filter((item) => item.category === category);
  }

  if (lowStockOnly) {
    filtered = filtered.filter((item) => item.is_low_stock);
  }

  if (expiringSoon) {
    filtered = filtered.filter(
      (item) => item.days_until_expiry !== null && item.days_until_expiry >= 0 && item.days_until_expiry <= 7
    );
  }

  return filtered;
}

async function mockInventoryScaffold(page: Page, options?: InventoryScaffoldOptions) {
  await mockAuth(page);

  await mockJsonRoute(page, "**/api/inventory/v2/status", async () => ({
    body: options?.status ?? BASE_INVENTORY_STATUS,
  }));

  await mockJsonRoute(page, "**/api/inventory/v2/items*", async (request) => {
    const url = new URL(request.url());
    options?.onItemsRequest?.(url.search);

    const items = filterInventoryItems(options?.items ?? BASE_INVENTORY_ITEMS, request.url());
    return {
      body: {
        count: items.length,
        items,
      },
    };
  });

  await mockJsonRoute(page, "**/api/receipt/v2/pending", async () => ({
    body: {
      count: options?.pendingItems?.length ?? 0,
      items: options?.pendingItems ?? [],
    },
  }));
}

test.describe("INVENTORY", () => {
  test("INV-01 inventory list search/filter/grid-list switch works", async ({ page }) => {
    await seedSession(page);

    const inventoryQueryLog: string[] = [];
    await mockInventoryScaffold(page, {
      onItemsRequest: (query) => {
        inventoryQueryLog.push(query);
      },
    });

    await page.goto("/dashboard/inventory");

    await expect(page.getByText("Greek Yogurt")).toBeVisible();
    await expect(page.getByText("Spinach", { exact: true })).toBeVisible();

    await page.getByPlaceholder("Search items...").fill("spinach");
    await expect(page.getByText("1 item found", { exact: true })).toBeVisible();
    await expect(page.getByText("Spinach", { exact: true })).toBeVisible();

    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "Produce" }).click();

    await expect.poll(() => inventoryQueryLog.some((query) => query.includes("category=Produce"))).toBeTruthy();

    const categoryCombobox = page.getByRole("combobox").first();
    await categoryCombobox.locator("xpath=following-sibling::button[1]").click();
    await page.getByRole("menuitem", { name: /Low Stock Only/ }).click();

    await expect.poll(() => inventoryQueryLog.some((query) => query.includes("low_stock_only=true"))).toBeTruthy();

    await categoryCombobox.locator("xpath=following-sibling::div[1]//button[2]").click();
    await expect(page.locator("div.divide-y").first()).toBeVisible();
  });

  test("INV-02 add-items fuzzy parse success and confirmation branch", async ({ page }) => {
    await seedSession(page);
    await mockInventoryScaffold(page);

    let confirmPayload: Record<string, unknown> | null = null;

    await mockJsonRoute(page, "**/api/inventory/v2/add-items", async () => ({
      body: {
        status: "ok",
        message: "Processed",
        results: {
          successful: [
            {
              original: "2 apples",
              matched: "Apple",
              quantity: "2 units",
              confidence: 0.95,
            },
          ],
          needs_confirmation: [
            {
              original: "bananas x3",
              suggested: "Banana",
              item_id: 501,
              confidence: 0.72,
              quantity: 3,
              unit: "units",
              quantity_grams: 300,
            },
          ],
          failed: [
            {
              original: "unknown ???",
              reason: "Could not parse item",
            },
          ],
          summary: {
            successful: 1,
            needs_confirmation: 1,
            failed: 1,
          },
        },
      },
    }));

    await mockJsonRoute(page, "**/api/inventory/v2/confirm-item", async (request) => {
      confirmPayload = readJsonBody(request);
      return {
        body: {
          item: "Banana",
        },
      };
    });

    await page.goto("/dashboard/inventory");
    await page.getByRole("button", { name: "Add Items" }).click();

    const dialog = page.getByRole("dialog");
    await dialog
      .getByPlaceholder("E.g., 2 apples, 500g chicken, 1L milk, 250g cheddar cheese...")
      .fill("2 apples, bananas x3, unknown ???");
    await dialog.getByRole("button", { name: "Add Items" }).click();

    await expect(dialog.getByText("Please Confirm These Items")).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Could Not Process" })).toBeVisible();

    await dialog.getByRole("button", { name: /Yes, add as Banana/i }).click();

    await expect.poll(() => confirmPayload?.item_id).toBe(501);
    await expect.poll(() => confirmPayload?.quantity_grams).toBe(300);
  });

  test("INV-03 receipt upload to review to confirm-and-seed completes", async ({ page }) => {
    await seedSession(page);
    await mockInventoryScaffold(page);

    let uploadedFilename = "";
    let confirmPayload: Record<string, unknown> | null = null;

    type PendingReceiptItem = {
      id: number;
      item_name: string;
      quantity: number;
      unit: string;
      canonical_name: string | null;
      category: string | null;
      fdc_id: string | null;
      nutrition_data: {
        calories?: number;
        protein_g?: number;
        carbs_g?: number;
        fat_g?: number;
      } | null;
      enrichment_confidence: number | null;
      enrichment_reasoning: string | null;
    };

    let pendingItems: PendingReceiptItem[] = [
      {
        id: 9101,
        item_name: "avocado",
        quantity: 2,
        unit: "units",
        canonical_name: "Avocado",
        category: "Produce",
        fdc_id: "1001",
        nutrition_data: {
          calories: 160,
          fat_g: 14,
        },
        enrichment_confidence: 0.91,
        enrichment_reasoning: "Matched avocado with high confidence.",
      },
      {
        id: 9102,
        item_name: "sprouted quinoa",
        quantity: 1,
        unit: "pack",
        canonical_name: "Sprouted Quinoa",
        category: "Grains",
        fdc_id: null,
        nutrition_data: null,
        enrichment_confidence: 0.42,
        enrichment_reasoning: "No matches found in canonical database.",
      },
    ];

    await mockJsonRoute(page, "**/api/receipt/v2/initiate", async (request) => {
      const payload = readJsonBody(request);
      uploadedFilename = String(payload.filename ?? "");

      return {
        body: {
          presigned_url: "https://storage.example.com/uploads/receipt-88.png",
          s3_key: "uploads/receipt-88.png",
          receipt_id: 88,
        },
      };
    });

    await page.route("https://storage.example.com/**", async (route) => {
      if (route.request().method() !== "PUT") {
        await route.fulfill({
          status: 405,
          headers: CORS_HEADERS,
          body: "",
        });
        return;
      }

      await route.fulfill({
        status: 200,
        headers: CORS_HEADERS,
        body: "",
      });
    });

    await mockJsonRoute(page, "**/api/receipt/v2/process", async () => ({
      body: {
        receipt_id: 88,
        status: "processed",
        image_url: "https://storage.example.com/uploads/receipt-88.png",
        total_items: 3,
        auto_added_count: 1,
        auto_added: [
          {
            item_name: "Milk",
            quantity: 1,
            unit: "L",
          },
        ],
        needs_confirmation_count: 2,
        needs_confirmation: [
          {
            item_name: "avocado",
            quantity: 2,
            unit: "units",
            suggested_item_id: 701,
            suggested_item_name: "Avocado",
            confidence: 0.91,
          },
          {
            item_name: "sprouted quinoa",
            quantity: 1,
            unit: "pack",
            suggested_item_id: null,
            suggested_item_name: null,
            confidence: 0.42,
          },
        ],
      },
    }));

    await mockJsonRoute(page, "**/api/receipt/v2/88/pending", async () => ({
      body: {
        receipt_id: 88,
        count: pendingItems.length,
        items: pendingItems,
      },
    }));

    await mockJsonRoute(page, "**/api/receipt/v2/confirm-and-seed", async (request) => {
      confirmPayload = readJsonBody(request);
      pendingItems = [];

      return {
        body: {
          status: "ok",
          seeded_count: 1,
          added_count: 2,
          seeded_items: [
            {
              canonical_name: "Sprouted Quinoa",
              category: "Grains",
              item_id: 702,
            },
          ],
        },
      };
    });

    await page.goto("/dashboard/inventory");
    await page.getByRole("button", { name: "Scan Receipt" }).click();

    const dialog = page.getByRole("dialog");
    await dialog.locator("input[type='file']").setInputFiles({
      name: "receipt.png",
      mimeType: "image/png",
      buffer: Buffer.from("fake-receipt-image"),
    });

    await dialog.getByRole("button", { name: "Scan Receipt" }).click();

    await expect(dialog.getByText("Added Automatically")).toBeVisible();
    await expect(dialog.getByText("Items Needing Confirmation (2)")).toBeVisible();

    await dialog.getByRole("button", { name: "Confirm All" }).first().click();

    await expect.poll(() => {
      const items = confirmPayload?.items;
      return Array.isArray(items) ? items.length : 0;
    }).toBe(2);

    expect(uploadedFilename).toBe("receipt.png");
    await expect(dialog.getByText(/Items Needing Confirmation/)).toHaveCount(0);
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeVisible();
  });

  test("INV-04 expiring list day filter and action states work", async ({ page }) => {
    await seedSession(page);
    await mockInventoryScaffold(page);

    const expiringRequests: number[] = [];
    const deletedIds: number[] = [];

    await mockJsonRoute(page, "**/api/tracking/v2/expiring-items*", async (request) => {
      const days = Number(new URL(request.url()).searchParams.get("days") ?? "3");
      expiringRequests.push(days);

      if (days === 7) {
        return {
          body: {
            total_expiring: 2,
            expired_count: 0,
            urgent_count: 1,
            high_priority_count: 0,
            medium_priority_count: 1,
            action_recommendations: ["Cook Greek Yogurt meals first."],
            items: [
              {
                inventory_id: 501,
                item_id: 31,
                item_name: "Greek Yogurt",
                quantity_grams: 600,
                expiry_date: "2026-02-28",
                days_remaining: 1,
                priority: "urgent",
                recipe_suggestions: [
                  {
                    recipe_id: 4001,
                    recipe_name: "Berry Yogurt Bowl",
                    uses_quantity: 200,
                    match_percentage: 92,
                  },
                ],
              },
              {
                inventory_id: 502,
                item_id: 32,
                item_name: "Brown Rice",
                quantity_grams: 1000,
                expiry_date: "2026-03-05",
                days_remaining: 6,
                priority: "medium",
                recipe_suggestions: [],
              },
            ],
          },
        };
      }

      return {
        body: {
          total_expiring: 1,
          expired_count: 0,
          urgent_count: 1,
          high_priority_count: 0,
          medium_priority_count: 0,
          action_recommendations: ["Use yogurt in breakfast tomorrow."],
          items: [
            {
              inventory_id: 501,
              item_id: 31,
              item_name: "Greek Yogurt",
              quantity_grams: 600,
              expiry_date: "2026-02-28",
              days_remaining: 1,
              priority: "urgent",
              recipe_suggestions: [
                {
                  recipe_id: 4001,
                  recipe_name: "Berry Yogurt Bowl",
                  uses_quantity: 200,
                  match_percentage: 92,
                },
              ],
            },
          ],
        },
      };
    });

    await mockJsonRoute(page, "**/api/inventory/v2/item/*", async (request) => {
      if (request.method() !== "DELETE") {
        return {
          status: 405,
          body: {
            detail: "Method not allowed",
          },
        };
      }

      const id = Number(request.url().split("/").pop());
      deletedIds.push(id);
      return {
        body: {
          success: true,
        },
      };
    });

    await page.goto("/dashboard/inventory");
    await page.getByRole("tab", { name: "Expiring Soon" }).click();

    await expect(page.getByText("Greek Yogurt", { exact: true })).toBeVisible();

    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "Next 7 days" }).click();

    await expect.poll(() => expiringRequests.includes(7)).toBeTruthy();
    await expect(page.getByText("Brown Rice", { exact: true })).toBeVisible();

    page.once("dialog", (dialog) => {
      void dialog.accept();
    });
    const brownRiceCard = page.locator("div[data-slot='card']").filter({ hasText: "Brown Rice" }).first();
    await brownRiceCard.getByRole("button", { name: "Remove" }).click();

    await expect.poll(() => deletedIds[0]).toBe(502);
  });

  test("INV-05 restock select, quantity edit, and bulk-add flow works", async ({ page }) => {
    await seedSession(page);
    await mockInventoryScaffold(page);

    let bulkAddPayload: Record<string, unknown> | null = null;

    await mockJsonRoute(page, "**/api/tracking/v2/restock-list", async () => ({
      body: {
        total_items: 2,
        urgent_items: [
          {
            item_id: 41,
            item_name: "Oats",
            category: "Grains",
            current_quantity: 120,
            recommended_quantity: 600,
            priority: "urgent",
            usage_frequency: 5,
            days_until_depleted: 1,
          },
        ],
        soon_items: [
          {
            item_id: 42,
            item_name: "Almonds",
            category: "Nuts",
            current_quantity: 80,
            recommended_quantity: 300,
            priority: "soon",
            usage_frequency: 3,
            days_until_depleted: 4,
          },
        ],
        routine_items: [],
        estimated_total_cost: 24.5,
        shopping_strategy: ["Buy urgent staples first."],
      },
    }));

    await mockJsonRoute(page, "**/api/inventory/v2/bulk-add-from-restock", async (request) => {
      bulkAddPayload = readJsonBody(request);
      return {
        body: {
          success: true,
          total_requested: 1,
          successfully_added: 1,
          failed_count: 0,
          added_items: [
            {
              item_id: 41,
              item_name: "Oats",
              quantity_added: 650,
              total_quantity: 770,
            },
          ],
          failed_items: [],
        },
      };
    });

    await page.goto("/dashboard/inventory");
    await page.getByRole("tab", { name: "Shopping List" }).click();

    await expect(page.getByText("Items to Buy (2)")).toBeVisible();

    const oatsRow = page
      .getByRole("heading", { name: "Oats", exact: true })
      .locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");

    await oatsRow.getByRole("checkbox").click();
    await oatsRow.locator("input[type='number']").fill("650");

    await page.getByRole("button", { name: /Add 1 to Inventory/ }).click();

    await expect.poll(() => {
      const items = bulkAddPayload?.items;
      if (!Array.isArray(items) || items.length === 0) {
        return "";
      }

      const firstItem = items[0] as { item_id: number; quantity_grams: number };
      return `${firstItem.item_id}:${firstItem.quantity_grams}`;
    }).toBe("41:650");
  });

  test("INV-06 makeable and AI recipe generation works for both modes", async ({ page }) => {
    await seedSession(page);
    await mockInventoryScaffold(page);

    const aiModes: string[] = [];

    await mockJsonRoute(page, "**/api/inventory/v2/makeable-recipes*", async () => ({
      body: {
        count: 2,
        fully_makeable: [
          {
            recipe_id: 901,
            recipe_name: "Spinach Omelette",
            description: "High-protein breakfast",
            prep_time_minutes: 15,
            servings: 1,
            available_ingredients: 4,
            total_ingredients: 4,
            available_ingredient_names: ["Eggs", "Spinach", "Salt", "Pepper"],
            missing_ingredient_names: [],
            match_percentage: 100,
          },
        ],
        partially_makeable: [
          {
            recipe_id: 902,
            recipe_name: "Protein Pasta",
            description: "Balanced lunch option",
            prep_time_minutes: 25,
            servings: 2,
            available_ingredients: 3,
            total_ingredients: 5,
            available_ingredient_names: ["Pasta", "Tomato", "Garlic"],
            missing_ingredient_names: ["Chicken", "Parmesan"],
            match_percentage: 60,
          },
        ],
      },
    }));

    await mockJsonRoute(page, "**/api/inventory/v2/ai-recipes*", async (request) => {
      const mode = new URL(request.url()).searchParams.get("mode") ?? "goal_adherent";
      aiModes.push(mode);

      if (mode === "guilt_free") {
        return {
          body: {
            mode,
            recipes: [
              {
                name: "Chocolate Banana Bites",
                description: "Sweet snack made from pantry staples",
                cuisine: "fusion",
                ingredients: [
                  { name: "Banana", quantity_grams: 120 },
                  { name: "Cocoa", quantity_grams: 10 },
                  { name: "Greek Yogurt", quantity_grams: 80 },
                ],
                instructions: ["Slice banana", "Mix cocoa and yogurt", "Assemble and serve"],
                estimated_prep_time_min: 10,
                estimated_calories: 180,
                estimated_protein_g: 8,
                estimated_carbs_g: 24,
                estimated_fat_g: 5,
                difficulty: "easy",
                suitable_meal_times: ["snack"],
                goals: ["general_health"],
                dietary_tags: ["vegetarian"],
              },
            ],
          },
        };
      }

      return {
        body: {
          mode,
          recipes: [
            {
              name: "Lean Power Bowl",
              description: "High-protein bowl aligned to your targets",
              cuisine: "high_protein",
              ingredients: [
                { name: "Chicken Breast", quantity_grams: 180 },
                { name: "Spinach", quantity_grams: 60 },
                { name: "Brown Rice", quantity_grams: 120 },
              ],
              instructions: ["Cook rice", "Saute chicken", "Assemble with spinach"],
              estimated_prep_time_min: 22,
              estimated_calories: 520,
              estimated_protein_g: 42,
              estimated_carbs_g: 48,
              estimated_fat_g: 14,
              difficulty: "medium",
              suitable_meal_times: ["lunch", "dinner"],
              goals: ["muscle_gain"],
              dietary_tags: ["high_protein"],
            },
          ],
        },
      };
    });

    await page.goto("/dashboard/inventory");
    await page.getByRole("tab", { name: "Cookable Recipes" }).click();

    await expect(page.getByText("Spinach Omelette", { exact: true })).toBeVisible();
    await expect(page.getByText("Protein Pasta", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Goal Adherent" }).click();
    await expect(page.getByText("Lean Power Bowl", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Guilt Free" }).click();
    await expect(page.getByText("Chocolate Banana Bites", { exact: true })).toBeVisible();

    await expect.poll(() => aiModes.includes("goal_adherent")).toBeTruthy();
    await expect.poll(() => aiModes.includes("guilt_free")).toBeTruthy();
  });
});



