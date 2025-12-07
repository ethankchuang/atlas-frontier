import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, VT323 } from "next/font/google";
import { Analytics } from "@vercel/analytics/next"
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const vt323 = VT323({
  weight: "400",
  variable: "--font-vt323",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Atlas Frontier - Infinite AI-Powered Multiplayer World",
  description: "Atlas Frontier is the infinite AI-powered multiplayer world and sandbox game. Explore, build, and play in an endless procedurally generated universe with friends.",
  keywords: ["Atlas Frontier", "AI-powered game", "multiplayer world", "sandbox game", "infinite world", "procedural generation", "online multiplayer", "browser game", "AI game"],
  authors: [{ name: "Atlas Frontier Team" }],
  creator: "Atlas Frontier",
  publisher: "Atlas Frontier",
  applicationName: "Atlas Frontier",
  generator: "Next.js",
  metadataBase: new URL("https://atlasfrontier.app"),
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://atlasfrontier.app",
    siteName: "Atlas Frontier",
    title: "Atlas Frontier - Infinite AI-Powered Multiplayer World",
    description: "Atlas Frontier is the infinite AI-powered multiplayer world and sandbox game. Explore, build, and play in an endless procedurally generated universe with friends.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Atlas Frontier - Infinite AI-Powered Multiplayer World",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@atlasfrontier",
    creator: "@atlasfrontier",
    title: "Atlas Frontier - Infinite AI-Powered Multiplayer World",
    description: "Atlas Frontier is the infinite AI-powered multiplayer world and sandbox game. Explore, build, and play in an endless procedurally generated universe with friends.",
    images: ["/og-image.png"],
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Atlas Frontier - Infinite AI-Powered Multiplayer World",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover", // Allows content to extend under iOS UI
  interactiveWidget: "resizes-visual",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#000000" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${vt323.variable} antialiased`}
      >
        {children}
        <Analytics />
      </body>
    </html>
  );
}
