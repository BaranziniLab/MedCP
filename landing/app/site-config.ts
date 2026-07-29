export const siteBase = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function sitePath(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${siteBase}${normalized}`;
}

export const repositoryUrl = "https://github.com/BaranziniLab/MedCP";
export const issuesUrl = `${repositoryUrl}/issues`;
export const releasesUrl = `${repositoryUrl}/releases`;
