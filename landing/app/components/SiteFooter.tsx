import Image from "next/image";
import {
  baranziniLabUrl,
  issuesUrl,
  repositoryUrl,
  sitePath,
} from "../site-config";
import { ProductLink } from "./ProductLink";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div>
          <a className="brand-link footer-brand" href={sitePath("/")}>
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
          <p>
            Research software from the{" "}
            <ProductLink href={baranziniLabUrl}>Baranzini Lab</ProductLink> at UCSF.
            <br />
            MIT licensed. Not for patient-care decisions.
          </p>
        </div>
        <nav aria-label="Footer navigation">
          <a href={sitePath("/docs/")}>Documentation</a>
          <a href={sitePath("/llms.txt")}>Agent setup</a>
          <a href={repositoryUrl}>Source</a>
          <a href={issuesUrl}>Issues</a>
        </nav>
      </div>
      <div className="footer-rule">
        <span>MedCP © 2025-2026</span>
        <ProductLink href={baranziniLabUrl}>Baranzini Lab</ProductLink>
      </div>
    </footer>
  );
}
