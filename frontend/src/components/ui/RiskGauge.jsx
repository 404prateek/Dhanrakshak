import React from 'react';

export function RiskGauge({ score = 0, size = 96 }) {
  const radius = 40;
  const stroke = 8;
  const normalized = Math.max(0, Math.min(100, Math.round(score)));
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (normalized / 100) * circumference;

  // color stops: green 0-40, amber 40-75, red 75+
  const color = normalized > 75 ? '#DC2626' : normalized > 40 ? '#F59E0B' : '#16A34A';

  return (
    <div className="flex items-center space-x-4">
      <svg width={size} height={size} viewBox="0 0 100 100">
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" x2="100%">
            <stop offset="0%" stopColor="#10B981" />
            <stop offset="50%" stopColor="#F59E0B" />
            <stop offset="100%" stopColor="#DC2626" />
          </linearGradient>
        </defs>
        <g transform="translate(50,50)">
          <circle r={radius} fill="transparent" stroke="#EFF2F6" strokeWidth={stroke} />
          <circle
            r={radius}
            fill="transparent"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${circumference} ${circumference}`}
            strokeDashoffset={offset}
            transform="rotate(-90)"
          />
          <text x="0" y="6" textAnchor="middle" fontSize="18" fontWeight="700" fill="#0F172A">{normalized}</text>
          <text x="0" y="24" textAnchor="middle" fontSize="10" fill="#64748B">Risk</text>
        </g>
      </svg>
      <div>
        <div className="text-sm font-semibold text-[var(--primary-text,#0F172A)]">Risk Score</div>
        <div className="text-xs text-[var(--secondary-text,#64748B)]">Confidence & recommendation included</div>
      </div>
    </div>
  );
}

export default RiskGauge;
