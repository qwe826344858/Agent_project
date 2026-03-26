import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI智能保险顾问",
  description: "专业、客观、中立的AI保险咨询助手",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}
