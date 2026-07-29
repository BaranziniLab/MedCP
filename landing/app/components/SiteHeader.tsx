import Image from "next/image";
import { repositoryUrl, sitePath } from "../site-config";

export function SiteHeader({ current }: { current: "about" | "docs" }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="brand-link" href={sitePath("/")} aria-label="MedCP home">
          <Image
            className="brand-mark"
            src={sitePath("/media/medcp-mark.png")}
            alt=""
            width="34"
            height="28"
            unoptimized
          />
          <span>MedCP</span>
        </a>
        <nav className="desktop-nav" aria-label="Primary navigation">
          <a aria-current={current === "about" ? "page" : undefined} href={sitePath("/")}>
            About
          </a>
          <a href={sitePath("/#evidence")}>Evidence</a>
          <a aria-current={current === "docs" ? "page" : undefined} href={sitePath("/docs/")}>
            Docs
          </a>
          <a className="nav-github" href={repositoryUrl}>
            GitHub <span aria-hidden="true">↗</span>
          </a>
        </nav>
        <details className="mobile-nav">
          <summary aria-label="Open navigation">Menu</summary>
          <nav aria-label="Mobile navigation">
            <a
              aria-current={current === "about" ? "page" : undefined}
              href={sitePath("/")}
            >
              About
            </a>
            <a href={sitePath("/#evidence")}>Evidence</a>
            <a
              aria-current={current === "docs" ? "page" : undefined}
              href={sitePath("/docs/")}
            >
              Docs
            </a>
            <a href={repositoryUrl}>GitHub ↗</a>
          </nav>
        </details>
      </div>
    </header>
  );
}
