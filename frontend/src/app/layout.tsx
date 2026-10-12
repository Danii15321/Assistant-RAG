import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Assistant RAG — Vos documents, vos sources",
  description: "Un assistant documentaire personnel, avec des réponses reliées à leurs sources.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
