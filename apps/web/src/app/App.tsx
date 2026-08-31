import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router";

import { AuthCallbackPage } from "../features/auth/AuthCallbackPage";
import { DashboardLayout } from "../features/dashboard/DashboardLayout";
import { useAuth } from "../features/auth/auth-context";

type PageMetadata = {
  title: string;
  description: string | null;
  robots: "index, follow" | "noindex, nofollow";
  canonical: string | null;
};

const PAGE_METADATA: Record<string, PageMetadata> = {
  "/": {
    title: "Live Game Alerts",
    description:
      "Live scores and customizable email and push alerts for NBA, WNBA, NFL, MLB, MLS, La Liga, Premier League, and World Cup games.",
    robots: "index, follow",
    canonical: "https://livegamealerts.com/",
  },
  "/teams": {
    title: "Teams | Live Game Alerts",
    description:
      "Browse NBA, WNBA, NFL, MLB, MLS, La Liga, Premier League, and World Cup teams and sign in to follow teams for live game email and push alerts.",
    robots: "index, follow",
    canonical: "https://livegamealerts.com/teams",
  },
  "/alerts": {
    title: "Alerts | Live Game Alerts",
    description: "Manage alert rules, delivery settings, and alert history.",
    robots: "noindex, nofollow",
    canonical: null,
  },
  "/admin": {
    title: "Admin | Live Game Alerts",
    description: "Manage competition availability and monitor Live Game Alerts operations.",
    robots: "noindex, nofollow",
    canonical: null,
  },
  "/auth": {
    title: "Sign in | Live Game Alerts",
    description: "Sign in securely to Live Game Alerts.",
    robots: "noindex, nofollow",
    canonical: null,
  },
};

const UNKNOWN_PAGE_METADATA: PageMetadata = {
  title: "Live Game Alerts",
  description: null,
  robots: "noindex, nofollow",
  canonical: null,
};

function setMeta(attribute: "name" | "property", key: string, content: string | null) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (content === null) {
    element?.remove();
    return;
  }
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
    const metadata = PAGE_METADATA[normalizedPath] ?? UNKNOWN_PAGE_METADATA;

    document.title = metadata.title;
    setMeta("name", "description", metadata.description);
    setMeta("name", "robots", metadata.robots);
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
