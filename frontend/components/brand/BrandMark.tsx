"use client";

type BrandMarkProps = {
  compact?: boolean;
  light?: boolean;
  className?: string;
};

export function BrandMark({ compact = false, light = false, className = "" }: BrandMarkProps) {
  const textColor = light ? "text-white" : "text-[#07192F]";
  const mutedColor = light ? "text-teal-100/80" : "text-[#0F766E]";

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <span
        aria-hidden="true"
        className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#D9F6EF] via-white to-[#63D8C8] shadow-lg shadow-teal-950/15 ring-1 ring-white/35"
      >
        <svg viewBox="0 0 48 48" className="h-9 w-9" fill="none">
          <path
            d="M6 16.5C11.7 14.4 18.1 15.1 24 19.2v17.2C18.6 32.7 12.4 32 6 34V16.5Z"
            fill="#F8FFFC"
            stroke="#0F766E"
            strokeWidth="2.8"
            strokeLinejoin="round"
          />
          <path
            d="M42 16.5C36.3 14.4 29.9 15.1 24 19.2v17.2C29.4 32.7 35.6 32 42 34V16.5Z"
            fill="#F8FFFC"
            stroke="#0F766E"
            strokeWidth="2.8"
            strokeLinejoin="round"
          />
          <path d="M24 19.2v17.2" stroke="#14B8A6" strokeWidth="2.8" strokeLinecap="round" />
          <path
            d="M24.8 6.8 31 23h-4.2l-1-2.9h-5.6l-1 2.9H15l6.1-16.2h3.7Zm-3.5 10.1h3.4L23 11.8l-1.7 5.1Z"
            fill="#0F766E"
          />
          <path d="M12 8.5v3M9.5 10h5M36 9v3M33.5 10.5h5" stroke="#14B8A6" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </span>
      <div className="min-w-0">
        <p className={`truncate text-xl font-black tracking-normal ${textColor}`}>
          MyOdyssey.ai
        </p>
        {!compact ? (
          <p className={`mt-0.5 text-xs font-semibold tracking-[0.22em] uppercase ${mutedColor}`}>
            Learn. Practice. Grow.
          </p>
        ) : null}
      </div>
    </div>
  );
}
