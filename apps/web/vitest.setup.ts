// Test runtime setup — pulls in jest-dom matchers (toBeInTheDocument etc.)
// and any global stubs the page views need under jsdom.

import "@testing-library/jest-dom/vitest";

// next/navigation isn't available outside a Next runtime — every page view
// that uses useRouter / useSearchParams stubs it via vi.mock() locally.

// IntersectionObserver and matchMedia are commonly poked by component libs
// (Radix / Recharts) and aren't implemented in jsdom. Minimal shims so
// renders don't crash on import.
if (typeof globalThis.IntersectionObserver === "undefined") {
  class IO {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
    root = null;
    rootMargin = "";
    thresholds = [];
  }
  globalThis.IntersectionObserver = IO;
}

if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
