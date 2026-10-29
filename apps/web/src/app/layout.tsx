import type { Metadata } from "next";
import "./style.css";
import "./chat.css";
import localFont from "next/font/local";
const persian = localFont({
  src: "./fonts/Vazirmatn-Variable.woff2",
  variable: "--font-persian",
  weight: "100 900",
  display: "swap",
  preload: false,
});
export const metadata: Metadata = {
  title: `${process.env.HAVEN_NAME || "HAVEN"} · Private community`,
  description: "Self-hosted private messenger. Security qualification pending.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={persian.variable}>
      <body>{children}</body>
    </html>
  );
}
