import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

const APP_NAME = "Salary Manager";
const APP_DESCRIPTION =
  "Internal HR compensation management for ACME — manage 10,000+ employees across the US, UK, and India. Effective-dated salary history, comp bands, equity grants, and a natural-language query assistant.";

export const metadata: Metadata = {
  title: {
    default: APP_NAME,
    template: `%s · ${APP_NAME}`,
  },
  description: APP_DESCRIPTION,
  applicationName: APP_NAME,
  authors: [{ name: "ACME HR" }],
  keywords: [
    "HR",
    "compensation",
    "salary",
    "comp bands",
    "people analytics",
    "salary manager",
  ],
  openGraph: {
    title: APP_NAME,
    description: APP_DESCRIPTION,
    type: "website",
    siteName: APP_NAME,
  },
  twitter: {
    card: "summary",
    title: APP_NAME,
    description: APP_DESCRIPTION,
  },
  // Internal tool — don't index publicly even if accidentally exposed.
  robots: {
    index: false,
    follow: false,
  },
  // `app/icon.svg` is picked up automatically by Next.js — declared
  // here for explicitness so it's obvious in the diff that we have one.
  icons: {
    icon: "/icon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light",
  themeColor: "#6366f1",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
