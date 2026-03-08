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

const DASHBOARD_ACTIVITY = {
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

async function mockDashboardAuth(page: Page) {
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

async function mockDashboardData(page: Page, summary = DASHBOARD_SUMMARY, activity = DASHBOARD_ACTIVITY) {
  await mockJsonRoute(page, "**/api/dashboard/v2/summary", async () => ({
    body: summary,
  }));
  await mockJsonRoute(page, "**/api/dashboard/v2/recent-activity*", async () => ({
    body: activity,
  }));
}

test.describe("AUTH", () => {
  test("AUTH-01 register success redirects to verify-pending login", async ({ page }) => {
    let capturedEmail = "";

    await mockJsonRoute(page, "**/api/auth/v2/register", async (request) => {
      const payload = readJsonBody(request);
      capturedEmail = String(payload.email ?? "");
      return {
        body: {
          message: "Registration successful",
        },
      };
    });

    await page.goto("/register");
    await page.getByLabel("Email").fill("new.user@example.com");
    await page.getByLabel("Password", { exact: true }).fill("password123");
    await page.getByLabel("Confirm Password").fill("password123");
    await page.getByRole("button", { name: "Create Account" }).click();

    await expect(page).toHaveURL(/\/login\?/);
    const redirectUrl = new URL(page.url());
    expect(redirectUrl.pathname).toBe("/login");
    expect(redirectUrl.searchParams.get("verify_pending")).toBe("1");
    expect(redirectUrl.searchParams.get("email")).toBe("new.user@example.com");
    expect(capturedEmail).toBe("new.user@example.com");
  });

  test("AUTH-02 duplicate register shows inline email error", async ({ page }) => {
    await mockJsonRoute(page, "**/api/auth/v2/register", async () => ({
      status: 409,
      body: {
        detail: "Email already registered",
      },
    }));

    await page.goto("/register");
    await page.getByLabel("Email").fill("existing@example.com");
    await page.getByLabel("Password", { exact: true }).fill("password123");
    await page.getByLabel("Confirm Password").fill("password123");
    await page.getByRole("button", { name: "Create Account" }).click();

    await expect(page.getByText("This email is already registered").first()).toBeVisible();
  });

  test("AUTH-03 login success redirects based on onboarding status", async ({ page }) => {
    await mockJsonRoute(page, "**/api/auth/v2/login", async () => ({
      body: {
        access_token: "login-token",
        token_type: "bearer",
        user: {
          ...DEFAULT_USER,
          onboarding_completed: false,
          onboarding_current_step: 1,
          basic_info_completed: false,
          goal_selection_completed: false,
          path_selection_completed: false,
          preferences_completed: false,
        },
      },
    }));

    await mockJsonRoute(page, "**/api/auth/v2/me", async () => ({
      body: {
        data: {
          user: {
            ...DEFAULT_USER,
            onboarding_completed: false,
            onboarding_current_step: 1,
          },
          onboarding: {
            completed: false,
            current_step: 1,
            completed_steps: [],
            redirect_to: "/onboarding/basic-info",
            next_step_name: "basic-info",
          },
        },
      },
    }));

    await page.goto("/login");
    await page.getByLabel("Email").fill("user@example.com");
    await page.getByLabel("Password", { exact: true }).fill("password123");
    await page.getByRole("button", { name: "Login" }).click();

    await expect(page).toHaveURL(/\/onboarding\/basic-info/, { timeout: 15000 });
  });

  test("AUTH-04 unverified login enables resend verification flow", async ({ page }) => {
    let resendEmail = "";

    await mockJsonRoute(page, "**/api/auth/v2/login", async () => ({
      status: 403,
      body: {
        detail: "Email not verified",
      },
    }));

    await mockJsonRoute(page, "**/api/auth/v2/resend-verification", async (request) => {
      const payload = readJsonBody(request);
      resendEmail = String(payload.email ?? "");
      return {
        body: {
          message: "Verification email sent",
        },
      };
    });

    await page.goto("/login");
    await page.getByLabel("Email").fill("unverified@example.com");
    await page.getByLabel("Password", { exact: true }).fill("password123");
    await page.getByRole("button", { name: "Login" }).click();

    await expect(page.getByText("Email not verified")).toBeVisible();
    await expect(page.getByRole("button", { name: "Resend Verification Email" })).toBeVisible();

    await page.getByRole("button", { name: "Resend Verification Email" }).click();
    await expect.poll(() => resendEmail).toBe("unverified@example.com");
  });

  test("AUTH-05 verify-email success and failure states", async ({ page }) => {
    await mockJsonRoute(page, "**/api/auth/v2/verify-email", async (request) => {
      const payload = readJsonBody(request);
      const token = String(payload.token ?? "");

      if (token === "good-token") {
        return {
          body: {
            message: "Email verified successfully",
          },
        };
      }

      return {
        status: 400,
        body: {
          detail: "Invalid or expired token",
        },
      };
    });

    await page.goto("/verify-email?token=good-token");
    await expect(page.getByRole("heading", { name: "Email Verified" })).toBeVisible();
    await expect(page.getByText("Email verified successfully")).toBeVisible();

    await page.goto("/verify-email?token=bad-token");
    await expect(page.getByRole("heading", { name: "Verification Failed" })).toBeVisible();
    await expect(page.getByText("Invalid or expired token")).toBeVisible();
  });
});

test.describe("ONBOARDING", () => {
  test("ONB-01 basic info valid submit navigates to goal selection", async ({ page }) => {
    let submittedName = "";

    await mockJsonRoute(page, "**/api/onboarding/v2/basic-info", async (request) => {
      const payload = readJsonBody(request);
      submittedName = String(payload.name ?? "");
      return {
        body: {
          next_step: "/onboarding/goal-selection",
        },
      };
    });

    await page.goto("/onboarding/basic-info");
    await page.getByLabel("Full Name").fill("Darsh QA");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(page).toHaveURL(/\/onboarding\/goal-selection/);
    expect(submittedName).toBe("Darsh QA");
  });

  test("ONB-02 goal selection submits optional target weight", async ({ page }) => {
    let submittedGoal = "";
    let submittedTargetWeight: number | null = null;

    await mockJsonRoute(page, "**/api/onboarding/v2/goal-selection", async (request) => {
      const payload = readJsonBody(request);
      submittedGoal = String(payload.goal_type ?? "");
      submittedTargetWeight = typeof payload.target_weight === "number" ? payload.target_weight : null;
      return {
        body: {
          next_step: "/onboarding/path-selection",
        },
      };
    });

    await page.goto("/onboarding/goal-selection");
    await page.getByLabel("Target Weight (Optional)").fill("65");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(page).toHaveURL(/\/onboarding\/path-selection/);
    expect(submittedGoal).toBe("fat_loss");
    expect(submittedTargetWeight).toBe(65);
  });

  test("ONB-03 path selection submit navigates to preferences", async ({ page }) => {
    let selectedPath = "";

    await mockJsonRoute(page, "**/api/onboarding/v2/path-selection", async (request) => {
      const payload = readJsonBody(request);
      selectedPath = String(payload.path_type ?? "");
      return {
        body: {
          next_step: "/onboarding/preferences",
        },
      };
    });

    await page.goto("/onboarding/path-selection");
    await page.getByText("One Meal A Day (OMAD)").click();
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(page).toHaveURL(/\/onboarding\/preferences/);
    expect(selectedPath).toBe("omad");
  });

  test("ONB-04 preferences completion redirects to dashboard", async ({ page }) => {
    await seedSession(page);
    await mockDashboardAuth(page);
    await mockDashboardData(page);

    await mockJsonRoute(page, "**/api/onboarding/v2/preferences", async () => ({
      body: {
        redirect_to: "/dashboard",
      },
    }));

    await page.goto("/onboarding/preferences");
    await page.getByRole("button", { name: "Complete Setup" }).click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 12000 });
    await expect(page.getByRole("heading", { name: "Plan. Eat. Track. Adapt." })).toBeVisible();
  });
});

test.describe("HOME", () => {
  test("HOME-01 dashboard summary and activity render", async ({ page }) => {
    await seedSession(page);
    await mockDashboardAuth(page);
    await mockDashboardData(page);

    await page.goto("/dashboard");

    await expect(page.getByText("Next meal: Lunch at 13:00")).toBeVisible();
    await expect(page.getByText("1 / 3")).toBeVisible();
    await expect(page.getByText("Breakfast logged")).toBeVisible();
  });

  test("HOME-02 dashboard error state recovers via retry", async ({ page }) => {
    await seedSession(page);
    await mockDashboardAuth(page);

    await mockJsonRoute(page, "**/api/dashboard/v2/recent-activity*", async () => ({
      body: DASHBOARD_ACTIVITY,
    }));

    await mockJsonRoute(page, "**/api/dashboard/v2/summary", async () => ({
      status: 500,
      body: { detail: "Temporary failure" },
    }));

    await page.goto("/dashboard");
    await expect(page.getByText("Failed to load dashboard data")).toBeVisible({ timeout: 12000 });

    await page.unroute("**/api/dashboard/v2/summary");
    await mockJsonRoute(page, "**/api/dashboard/v2/summary", async () => ({
      body: {
        ...DASHBOARD_SUMMARY,
        meals_card: {
          ...DASHBOARD_SUMMARY.meals_card,
          next_meal: "Dinner",
          next_meal_time: "19:30",
        },
      },
    }));

    await page.getByRole("button", { name: "Try Again" }).click();
    await expect(page.getByText("Next meal: Dinner at 19:30")).toBeVisible();
  });

  test("HOME-03 notification center renders websocket event", async ({ page }) => {
    await page.addInitScript(() => {
      const NativeWebSocket = window.WebSocket;

      class MockWebSocket {
        static CONNECTING = 0;
        static OPEN = 1;
        static CLOSING = 2;
        static CLOSED = 3;
        readyState = MockWebSocket.OPEN;
        url: string;
        onopen: ((event: Event) => void) | null = null;
        onmessage: ((event: MessageEvent) => void) | null = null;
        onclose: ((event: CloseEvent) => void) | null = null;
        onerror: ((event: Event) => void) | null = null;

        constructor(url: string) {
          this.url = url;
          window.setTimeout(() => {
            this.onopen?.(new Event("open"));
            this.onmessage?.(
              new MessageEvent("message", {
                data: JSON.stringify({
                  event_type: "meal_logged",
                  message: "Realtime test alert",
                  timestamp: new Date().toISOString(),
                }),
              })
            );
          }, 100);
        }

        close() {
          this.readyState = MockWebSocket.CLOSED;
          this.onclose?.(new CloseEvent("close"));
        }

        send() {}
      }

      const PatchedWebSocket = function (
        url: string | URL,
        protocols?: string | string[]
      ) {
        const urlValue = String(url);
        if (urlValue.includes("/ws/tracking")) {
          return new MockWebSocket(urlValue);
        }

        if (protocols === undefined) {
          return new NativeWebSocket(url);
        }
        return new NativeWebSocket(url, protocols);
      };

      Object.assign(PatchedWebSocket, NativeWebSocket);
      // @ts-expect-error test-only websocket override
      window.WebSocket = PatchedWebSocket;
    });

    await seedSession(page);
    await mockDashboardAuth(page);
    await mockDashboardData(page);

    await page.goto("/dashboard");

    await page.getByRole("button", { name: "Open notifications" }).click();
    await expect(page.getByText("Realtime test alert").first()).toBeVisible({ timeout: 10000 });
  });
});
