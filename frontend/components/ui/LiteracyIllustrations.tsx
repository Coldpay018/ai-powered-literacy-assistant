"use client";

export type LiteracyIconName =
  | "book"
  | "write"
  | "vocabulary"
  | "comprehension"
  | "path"
  | "trophy"
  | "lightbulb"
  | "growth"
  | "profile";

type IconProps = {
  name: LiteracyIconName;
  className?: string;
};

export function LiteracyIcon({ name, className = "h-8 w-8" }: IconProps) {
  const common = "stroke-[#0F766E] dark:stroke-[#63D8C8]";

  if (name === "write") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path className={common} d="M12 34h15M14 30 32.5 11.5a4 4 0 0 1 5.7 5.7L19.7 35.7 11 38l3-8Z" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (name === "vocabulary") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path className={common} d="M10 34 18.5 12h4L31 34M13 27h15M34 18v16M29 24h10" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (name === "comprehension") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path className={common} d="M24 8c-7 0-12 4.7-12 11 0 4 2.1 7.1 5.2 9l.8 6 5-4h1c7 0 12-4.7 12-11S31 8 24 8Z" strokeWidth="3" strokeLinejoin="round" />
        <path className={common} d="M20 19h8M20 25h5" strokeWidth="3" strokeLinecap="round" />
      </svg>
    );
  }

  if (name === "path") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path d="M14 36c9-1 5-19 20-24" stroke="#A7F3D0" strokeWidth="10" strokeLinecap="round" />
        <path className={common} d="M12 36c10-1 6-20 22-24M34 12h-7M34 12v7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (name === "trophy") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path d="M17 10h14v8c0 5-3 9-7 9s-7-4-7-9v-8Z" fill="#F7D774" />
        <path className={common} d="M17 10h14v8c0 5-3 9-7 9s-7-4-7-9v-8ZM17 14h-5v2c0 4 2 7 6 8M31 14h5v2c0 4-2 7-6 8M24 27v7M18 38h12" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (name === "lightbulb") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path d="M17 21a7 7 0 1 1 14 0c0 4-3 5.4-4 9h-6c-1-3.6-4-5-4-9Z" fill="#FBE7A2" />
        <path className={common} d="M17 21a7 7 0 1 1 14 0c0 4-3 5.4-4 9h-6c-1-3.6-4-5-4-9ZM21 36h6M22 41h4M24 6v3M12 12l2.2 2.2M36 12l-2.2 2.2" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (name === "growth") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path className={common} d="M10 36h28M15 32V20M24 32V12M33 32V18M24 12l-4 5M24 12l5 4" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (name === "profile") {
    return (
      <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
        <path className={common} d="M24 24a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM11 39c2.5-7 7-10 13-10s10.5 3 13 10" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 48 48" className={className} fill="none" aria-hidden="true">
      <path className={common} d="M7 15c6-2 12.4-1.2 17 3.2V38c-5-3.8-10.7-4.5-17-2.4V15ZM41 15c-6-2-12.4-1.2-17 3.2V38c5-3.8 10.7-4.5 17-2.4V15ZM24 18v20" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HeroBookIllustration({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 520 420" className={className} fill="none" role="img" aria-label="Open book with a large letter A">
      <ellipse cx="260" cy="342" rx="142" ry="34" fill="#031827" opacity="0.28" />
      <rect x="132" y="238" width="260" height="86" rx="24" fill="#79D8C6" />
      <path d="M130 155c47-20 96-17 132 16v142c-37-29-84-35-132-18V155Z" fill="#FFFDF6" stroke="#0F766E" strokeWidth="10" strokeLinejoin="round" />
      <path d="M390 155c-47-20-96-17-132 16v142c37-29 84-35 132-18V155Z" fill="#FFFDF6" stroke="#0F766E" strokeWidth="10" strokeLinejoin="round" />
      <path d="M258 171v142" stroke="#63D8C8" strokeWidth="9" strokeLinecap="round" />
      <path d="M160 196c32-8 59-5 80 9M160 235c32-8 59-5 80 9M360 196c-32-8-59-5-80 9M360 235c-32-8-59-5-80 9" stroke="#B8D7D0" strokeWidth="8" strokeLinecap="round" />
      <path d="M282 58 335 206h-43l-8-25h-50l-8 25h-42L237 58h45Zm-38 89h30l-15-48-15 48Z" fill="url(#heroA)" />
      <path d="M83 91h18M92 82v18M424 97h18M433 88v18M382 52h14M389 45v14" stroke="#F7D774" strokeWidth="8" strokeLinecap="round" />
      <defs>
        <linearGradient id="heroA" x1="184" x2="335" y1="58" y2="206" gradientUnits="userSpaceOnUse">
          <stop stopColor="#D9F6EF" />
          <stop offset="0.45" stopColor="#63D8C8" />
          <stop offset="1" stopColor="#0F766E" />
        </linearGradient>
      </defs>
    </svg>
  );
}
