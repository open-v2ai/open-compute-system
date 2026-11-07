"use client";

import Link from "next/link";
import { useId } from "react";
import { usePreferences } from "./PreferencesProvider";

type BrandVariant = "responsive" | "lockup" | "mark";

function MarkGeometry({ maskId }: { maskId: string }) {
  const sPath = "M378.119 68.801C349.192 47.763 286.517 50.101 269.642 80.488C251.563 112.434 298.57 119.447 338.344 124.901C386.556 131.134 401.02 149.835 381.735 169.314C356.424 194.247 287.722 187.235 260 163.86";

  return (
    <>
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="430" height="240">
          <rect width="430" height="240" fill="#000" />
          <path d={sPath} fill="none" stroke="#fff" strokeWidth="62" strokeLinecap="round" strokeLinejoin="round" />
          <path d={sPath} fill="none" stroke="#000" strokeWidth="42" strokeLinecap="round" strokeLinejoin="round" />
        </mask>
      </defs>
      <g fill="none" stroke="currentColor" strokeWidth="10">
        <circle cx="112" cy="120" r="91" />
        <circle cx="112" cy="120" r="54" />
      </g>
      <path d="M247 70A64 64 0 1 0 247 170" fill="none" stroke="var(--accent)" strokeWidth="64" />
      <rect width="430" height="240" fill="currentColor" mask={`url(#${maskId})`} />
    </>
  );
}

function LogoMark({ className }: { className: string }) {
  const maskId = useId();
  return (
    <svg className={className} viewBox="0 0 430 240" aria-hidden="true" focusable="false">
      <MarkGeometry maskId={maskId} />
    </svg>
  );
}

function LogoLockup({ className }: { className: string }) {
  const maskId = useId();
  return (
    <svg className={className} viewBox="0 0 860 240" aria-hidden="true" focusable="false">
      <g transform="translate(8 12) scale(.9)">
        <MarkGeometry maskId={maskId} />
      </g>
      <line x1="414" y1="42" x2="414" y2="198" stroke="currentColor" strokeWidth="4" />
      <g fill="currentColor" fontFamily="Arial, Helvetica, sans-serif">
        <text x="454" y="111" fontSize="72" fontWeight="600" textLength="186" lengthAdjust="spacingAndGlyphs">Open</text>
        <text x="454" y="171" fontSize="43" fontWeight="400" textLength="330" lengthAdjust="spacingAndGlyphs">Compute System</text>
      </g>
    </svg>
  );
}

export function Brand({ href = "/", variant = "responsive" }: { href?: string; variant?: BrandVariant }) {
  const { t } = usePreferences();
  return (
    <Link className={`brand brand-${variant}`} href={href} aria-label={t("Open Compute System 首页")}>
      {variant !== "mark" && <LogoLockup className="brand-lockup" />}
      {variant !== "lockup" && <LogoMark className="brand-symbol" />}
    </Link>
  );
}
