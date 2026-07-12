"use client";

import type { CSSProperties } from "react";

type ProgressRingProps = {
  value: number;
  label?: string;
  caption?: string;
  size?: number;
  stroke?: number;
  isDark?: boolean;
};

export function ProgressRing({
  value,
  label,
  caption,
  size = 148,
  stroke = 16,
  isDark = false,
}: ProgressRingProps) {
  const normalizedValue = Math.max(0, Math.min(100, Math.round(value)));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (normalizedValue / 100) * circumference;

  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={isDark ? "rgba(255,255,255,0.1)" : "#E4F0EC"}
          strokeWidth={stroke}
        />
        <circle
          className="progress-ring"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#odysseyRing)"
          strokeLinecap="round"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ "--ring-circumference": circumference } as CSSProperties}
        />
        <defs>
          <linearGradient id="odysseyRing" x1="0" x2={size} y1="0" y2={size} gradientUnits="userSpaceOnUse">
            <stop stopColor="#14B8A6" />
            <stop offset="1" stopColor="#0F766E" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="text-3xl font-black tracking-normal">{label || `${normalizedValue}%`}</p>
          {caption ? (
            <p className={isDark ? "mt-1 text-xs font-semibold text-teal-100/70" : "mt-1 text-xs font-semibold text-[#0F766E]"}>
              {caption}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
