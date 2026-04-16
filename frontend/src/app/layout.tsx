import type { Metadata } from "next";
import { Inter, Roboto_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { NotificationProvider } from "@/components/providers/notification-provider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const robotoMono = Roboto_Mono({
  variable: "--font-roboto-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
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
  icons: {
    icon: '/favicon.svg',
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
        className={`${inter.variable} ${robotoMono.variable} antialiased bg-background text-foreground`}
      >
        <NotificationProvider>
          {children}
        </NotificationProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
