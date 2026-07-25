import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router";

import { AuthCallbackPage } from "../features/auth/AuthCallbackPage";
import { DashboardLayout } from "../features/dashboard/DashboardLayout";
import { useAuth } from "../features/auth/auth-context";

const PAGE_METADATA = {
  games: {
    title: "Live Game Alerts | Live Sports Scores & Email and Push Alerts",
    description:
      "Live scores and customizable email and push alerts for NBA, WNBA, MLB, MLS, and World Cup games.",
    canonical: "https://livegamealerts.com/",
  },
  teams: {
    title: "Sports Teams | Live Game Alerts",
    description:
      "Browse NBA, WNBA, MLB, MLS, and World Cup teams and sign in to follow teams for live game email and push alerts.",
    canonical: "https://livegamealerts.com/teams",
  },
} as const;

function setMeta(attribute: "name" | "property", key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, key);
    document.head.append(element);
  }
  element.content = content;
}

function setCanonical(href: string | null) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!href) {
    element?.remove();
    return;
  }
  if (!element) {
    element = document.createElement("link");
    element.rel = "canonical";
    document.head.append(element);
  }
  element.href = href;
}

export default function App() {
  const { isLoading } = useAuth();
  const { pathname } = useLocation();

  useEffect(() => {
    const normalizedPath = pathname === "/" ? pathname : pathname.replace(/\/+$/, "");
    const metadata =
      normalizedPath === "/"
        ? PAGE_METADATA.games
        : normalizedPath === "/teams"
          ? PAGE_METADATA.teams
          : null;

    if (!metadata) {
      document.title = "Live Game Alerts";
      setMeta("name", "robots", "noindex, nofollow");
      setCanonical(null);
      return;
    }

    document.title = metadata.title;
    setMeta("name", "description", metadata.description);
    setMeta("name", "robots", "index, follow");
    setMeta("property", "og:title", metadata.title);
    setMeta("property", "og:description", metadata.description);
    setMeta("property", "og:url", metadata.canonical);
    setCanonical(metadata.canonical);
  }, [pathname]);

  if (isLoading) {
    return <div className="container">Loading...</div>;
  }

  return (
    <Routes>
      <Route path="/auth" element={<AuthCallbackPage />} />
      <Route path="/*" element={<DashboardLayout />} />
    </Routes>
  );
}
