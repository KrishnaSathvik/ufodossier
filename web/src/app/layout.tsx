import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Newsreader, Special_Elite } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["300", "400", "500", "600", "700"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["300", "400", "500", "700"],
});

const serif = Newsreader({
  subsets: ["latin"],
  variable: "--font-serif",
  weight: ["400", "500", "700"],
  style: ["normal", "italic"],
});

const type = Special_Elite({
  subsets: ["latin"],
  variable: "--font-type",
  weight: "400",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  metadataBase: new URL("https://ufodossier.com"),
  title: {
    default: "UFO Dossier — Declassified UAP Archive",
    template: "%s — UFO Dossier",
  },
  description:
    "A searchable record of every UAP incident in the U.S. government's declassified files. Every claim sourced. Every document linked.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
  openGraph: {
    title: "UFO Dossier — Declassified UAP Archive",
    description:
      "A searchable record of every UAP incident in the U.S. government's declassified files.",
    type: "website",
    siteName: "UFO Dossier",
  },
  twitter: {
    card: "summary_large_image",
    title: "UFO Dossier",
    description: "Declassified UAP archive. Every claim sourced.",
  },
};

// Inline script to prevent flash of wrong theme on page load.
// Content is a hardcoded constant — no user input, no XSS risk.
const themeScript = `
(function(){
  try {
    var t = localStorage.getItem('theme');
    if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
    }
  } catch(e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} ${serif.variable} ${type.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: themeScript,
          }}
        />
      </head>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
