import type { Metadata } from "next";
import "./globals.css";

const publicSiteUrl = "https://baranzinilab.github.io/MedCP/";
const socialImageUrl = new URL("media/medcp-social.png", publicSiteUrl);
const iconUrl = new URL("media/medcp-mark.png", publicSiteUrl);

export const metadata: Metadata = {
  metadataBase: new URL(publicSiteUrl),
  title: {
    default: "MedCP | The private data port for medical AI",
    template: "%s | MedCP",
  },
  description:
    "One read-only MCP interface for approved AI agents, OMOP clinical records, and biomedical knowledge graphs.",
  keywords: [
    "MedCP",
    "Model Context Protocol",
    "OMOP",
    "SPOKE",
    "clinical research",
    "knowledge graph",
  ],
  icons: {
    icon: iconUrl,
    shortcut: iconUrl,
  },
  openGraph: {
    title: "MedCP",
    description:
      "The private data port for medical AI.",
    type: "website",
    siteName: "MedCP",
    images: [
      {
        url: socialImageUrl,
        width: 1200,
        height: 630,
        alt: "MedCP, the private data port for medical AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "MedCP",
    description: "The private data port for medical AI.",
    images: [socialImageUrl],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
