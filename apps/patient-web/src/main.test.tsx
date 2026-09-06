import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// main.tsx mounts itself on import (createRoot(...).render(<App/>)), so the
// smoke test provides the #root element it expects and imports it fresh per
// test rather than restructuring the app's existing single-file convention.
// `findBy*` (not `getBy*`) is required for the first query after mount:
// React's initial commit is scheduled, not synchronous, so the DOM is empty
// until a microtask flush -- `findBy*` polls for it.
async function mountApp() {
  document.body.innerHTML = '<div id="root"></div>';
  vi.resetModules();
  await import("./main");
}

describe("patient-web App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // A shared Response instance can only have its body read once; every app
    // mount here makes several fetch calls (demo, auth/me, patients/me), so
    // each call must get its own fresh Response.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () => new Response("{}", { status: 200 }))
    );
  });

  it("renders the login screen when no token is stored", async () => {
    await mountApp();

    expect(await screen.findByRole("heading", { name: "Вход" })).toBeTruthy();
    expect(screen.getByLabelText("Организация")).toBeTruthy();
    expect(screen.getByLabelText("Email")).toBeTruthy();
  });

  it("carries the non-clinical disclaimer and locale switcher, ported from the former string-assertion test", async () => {
    await mountApp();
    expect(await screen.findByRole("combobox", { name: "Язык" })).toBeTruthy();

    // The disclaimer only renders once past login; remount with a token
    // pre-set to reach it without driving the full login form.
    window.localStorage.setItem("phoenix.patient.token", "fake-token");
    await mountApp();
    expect(await screen.findByText(/synthetic replay/i)).toBeTruthy();
  });
});
