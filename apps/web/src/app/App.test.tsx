import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import App from "./App";

vi.mock("../features/auth/auth-context", () => ({
  useAuth: () => ({ isLoading: false }),
}));

vi.mock("../features/auth/AuthCallbackPage", () => ({
  AuthCallbackPage: () => <div>Auth callback</div>,
}));

vi.mock("../features/dashboard/DashboardLayout", () => ({
  DashboardLayout: () => <div>Dashboard</div>,
}));

function renderPath(pathname: string) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <App />
    </MemoryRouter>,
  );
}

function metaContent(selector: string) {
  return document.head.querySelector<HTMLMetaElement>(selector)?.content;
}

describe("App page metadata", () => {
  beforeEach(() => {
    document.head.innerHTML = "";
  });

  it("uses the games metadata for the root page", async () => {
    renderPath("/");

    await waitFor(() => expect(document.title).toBe("Live Game Alerts"));
    expect(metaContent('meta[name="description"]')).toBe(
      "Live scores and customizable email and push alerts for NBA, WNBA, NFL, MLB, MLS, La Liga, Premier League, and World Cup games.",
    );
    expect(metaContent('meta[name="robots"]')).toBe("index, follow");
    expect(metaContent('meta[property="og:title"]')).toBe("Live Game Alerts");
    expect(metaContent('meta[property="og:url"]')).toBe("https://livegamealerts.com/");
    expect(document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href).toBe(
      "https://livegamealerts.com/",
    );
  });

  it("uses distinct metadata for the public teams page", async () => {
    renderPath("/teams");

    await waitFor(() => expect(document.title).toBe("Teams | Live Game Alerts"));
    expect(metaContent('meta[name="description"]')).toContain(
      "Browse NBA, WNBA, NFL, MLB, MLS, La Liga, Premier League",
    );
    expect(metaContent('meta[name="robots"]')).toBe("index, follow");
    expect(metaContent('meta[property="og:url"]')).toBe("https://livegamealerts.com/teams");
    expect(document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href).toBe(
      "https://livegamealerts.com/teams",
    );
  });

  it.each([
    ["/auth", "Sign in | Live Game Alerts"],
    ["/alerts", "Alerts | Live Game Alerts"],
    ["/admin", "Admin | Live Game Alerts"],
    ["/missing", "Live Game Alerts"],
  ])("uses a concise title and prevents indexing of %s", async (pathname, title) => {
    renderPath(pathname);

    await waitFor(() => expect(document.title).toBe(title));
    await waitFor(() => expect(metaContent('meta[name="robots"]')).toBe("noindex, nofollow"));
    expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
    expect(metaContent('meta[property="og:url"]')).toBeUndefined();
  });
});
