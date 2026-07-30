import type { ReactNode } from "react";

export function ProductLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a className="product-link" href={href}>
      {children}
    </a>
  );
}
