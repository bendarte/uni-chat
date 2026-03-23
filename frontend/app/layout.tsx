import type { Metadata } from "next";
import "./globals.css";

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
      <body className="min-h-screen bg-gray-50 antialiased">{children}</body>
    </html>
  );
}
