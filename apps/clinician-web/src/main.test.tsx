import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

async function mountApp() {
  document.body.innerHTML = '<div id="root"></div>';
  vi.resetModules();
  await import("./main");
}

describe("clinician-web App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // A shared Response instance can only have its body read once; every app
    // mount here makes several fetch calls (demo, auth/me, patients list), so
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
  });

  it("carries the non-clinical disclaimer once past login, ported from the former string-assertion test", async () => {
    window.localStorage.setItem("phoenix.clinician.token", "fake-token");
    await mountApp();

    expect(await screen.findByText(/клинических решениях|клинических решений/i)).toBeTruthy();
  });
});
