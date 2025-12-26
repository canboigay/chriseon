import type { Metadata } from "next";
import Script from "next/script";
import { IBM_Plex_Mono, Libre_Baskerville } from "next/font/google";
import "./globals.css";

import { TextureBackground } from "./_components/texture-background";
import { ThemeToggle } from "./_components/theme-toggle";

const editorial = Libre_Baskerville({
  variable: "--font-editorial",
  subsets: ["latin"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
});

const typewriter = IBM_Plex_Mono({
  variable: "--font-typewriter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "chriseon",
  description: "Multi-model AI orchestrator",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script
          id="chr-theme-init"
          strategy="beforeInteractive"
        >{`
(function () {
  try {
    var t = localStorage.getItem('chr-theme');
    if (t === 'light' || t === 'dark') {
      document.documentElement.setAttribute('data-theme', t);
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  } catch (e) {}
})();
        `}</Script>
      </head>
      <body className={`${editorial.variable} ${typewriter.variable} antialiased`}>
        <TextureBackground />
        <div className="fixed right-4 top-4 z-10">
          <ThemeToggle />
        </div>
        {children}
      </body>
    </html>
  );
}
