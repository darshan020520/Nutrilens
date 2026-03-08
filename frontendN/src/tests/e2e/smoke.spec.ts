import { test, expect } from "@playwright/test";

test("landing page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/NutriLens/i);
  await expect(page.getByRole("heading", { name: "Plan. Eat. Track. Adapt." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get Started" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Log In" })).toBeVisible();
});

test("login page renders auth form and register link", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome Back" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign up" })).toHaveAttribute("href", "/register");
});

test("register page renders form and login link", async ({ page }) => {
  await page.goto("/register");
  await expect(page.getByRole("heading", { name: "Create Account" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Confirm Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create Account" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Login" })).toHaveAttribute("href", "/login");
});

test("dashboard route redirects unauthenticated users to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);
});

test("verify-email without token shows invalid-link state", async ({ page }) => {
  await page.goto("/verify-email");
  await expect(page.getByRole("heading", { name: "Verification Failed" })).toBeVisible();
  await expect(page.getByText("Invalid verification link.")).toBeVisible();
});
