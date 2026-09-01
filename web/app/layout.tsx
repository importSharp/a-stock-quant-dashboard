import type { Metadata, Viewport } from "next";
import "./globals.css";
import { PwaRegister } from "./components/PwaRegister";

export const metadata: Metadata = {
  title: "a-stock-data｜A股数据工作台",
  description: "仅使用 a-stock-data 数据能力的本地A股可视化工作台。",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "A股数据台",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#101312",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <PwaRegister />
        {children}
      </body>
    </html>
  );
}
