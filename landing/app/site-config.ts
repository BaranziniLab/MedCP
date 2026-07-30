export const siteBase = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function sitePath(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${siteBase}${normalized}`;
}

export const repositoryUrl = "https://github.com/BaranziniLab/MedCP";
export const issuesUrl = `${repositoryUrl}/issues`;
export const releasesUrl = `${repositoryUrl}/releases`;
export const baranziniLabUrl = "https://baranzinilab.ucsf.edu/";
export const bioRouterUrl = "https://biorouter.ucsf.edu/";
export const claudeCodeUrl = "https://claude.com/product/claude-code";
export const claudeDesktopUrl = "https://claude.com/download";
export const codexCliUrl = "https://learn.chatgpt.com/docs/codex/cli";
