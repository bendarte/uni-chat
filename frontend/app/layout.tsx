import type { Metadata } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "UniChat – Hitta rätt utbildning",
  description:
    "AI-rådgivare som hjälper dig hitta rätt universitets- och högskoleutbildning i Sverige.",
  openGraph: {
    title: "UniChat – Hitta rätt utbildning",
    description:
      "AI-rådgivare som hjälper dig hitta rätt universitets- och högskoleutbildning i Sverige.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="sv">
      <body
        className={`${spaceGrotesk.variable} ${ibmPlexMono.variable} min-h-screen antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
