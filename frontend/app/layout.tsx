import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EDH Bulk Up",
  description: "Find Decks Hidden in Your Bulk",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
