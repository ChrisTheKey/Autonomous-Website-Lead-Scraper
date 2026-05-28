import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Autonomous Lead Scraper",
  description: "AI-powered autonomous website lead scraper with CRM sync",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <Providers>
          <nav className="border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
            <span className="text-lg font-bold text-blue-700">Lead Scraper</span>
          </nav>
          <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
