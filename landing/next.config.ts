import type { NextConfig } from "next";

const githubPages = process.env.GITHUB_PAGES === "true";
const repositoryName =
  process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "MedCP";
const basePath = githubPages ? `/${repositoryName}` : "";

const nextConfig: NextConfig = githubPages
  ? {
      output: "export",
      basePath,
      assetPrefix: basePath,
      trailingSlash: true,
      images: {
        unoptimized: true,
      },
    }
  : {};

export default nextConfig;
