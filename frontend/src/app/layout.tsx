import type { Metadata } from "next";
import "./globals.css";
import "./chat.css";
import "./workspace.css";
import "./sidebar.css";
import { cookies } from "next/headers";
import { ThemeProvider, type Theme } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "My Talking RAG — Vos documents, vos sources",
  description: "Un assistant documentaire personnel, avec des réponses reliées à leurs sources.",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const preference = (await cookies()).get("mtr-theme")?.value;
  const theme: Theme = preference === "light" || preference === "dark" ? preference : "system";
  return (
    <html lang="fr" data-theme={theme}>
      <body><ThemeProvider initialTheme={theme}>{children}</ThemeProvider></body>
    </html>
  );
}
