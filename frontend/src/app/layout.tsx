import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { NotificationProvider } from "@/components/providers/notification-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SmartDalali - Tanzania's Premier Marketplace",
  description: "Buy and sell quality products from trusted sellers across Tanzania. Secure payments with M-Pesa, Tigo Pesa, and more. Fast delivery nationwide.",
  keywords: ["SmartDalali", "Tanzania", "marketplace", "e-commerce", "online shopping", "M-Pesa", "Dar es Salaam"],
  authors: [{ name: "SmartDalali" }],
  openGraph: {
    title: "SmartDalali - Tanzania's Premier Marketplace",
    description: "Buy and sell quality products from trusted sellers across Tanzania.",
    siteName: "SmartDalali",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <NotificationProvider>
          {children}
        </NotificationProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
