import type { Metadata } from "next";
import "./globals.css";
import AuthSessionProvider from "@/lib/session-provider";
import Navbar from "./components/Navbar";

export const metadata: Metadata = {
  title: "Shorts Engine Studio",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthSessionProvider>
          <Navbar />
          {children}
        </AuthSessionProvider>
      </body>
    </html>
  );
}
