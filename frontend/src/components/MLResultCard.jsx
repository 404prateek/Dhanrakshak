import React, { useState } from 'react';

// ── Professional banking light-theme risk palette ──────────────────
const RISK_STYLES = {
  HIGH: {
    header:  'bg-red-50 border-red-200',
    badge:   'bg-red-100 text-red-700 border border-red-200',
    score:   'text-red-600',
    bar:     'bg-red-500',
    rec:     'bg-red-600 text-white',
    barBg:   'bg-red-100',
    trufor:  { label: 'bg-red-100 text-red-700' },
  },
  MEDIUM: {
    header:  'bg-amber-50 border-amber-200',
    badge:   'bg-amber-100 text-amber-700 border border-amber-200',
    score:   'text-amber-600',
    bar:     'bg-amber-500',
    rec:     'bg-amber-500 text-white',
    barBg:   'bg-amber-100',
    trufor:  { label: 'bg-amber-100 text-amber-700' },
  },
  LOW: {
    header:  'bg-green-50 border-green-200',
    badge:   'bg-green-100 text-green-700 border border-green-200',
    score:   'text-green-600',
    bar:     'bg-green-500',
    rec:     'bg-green-600 text-white',
    barBg:   'bg-green-100',
    trufor:  { label: 'bg-green-100 text-green-700' },
  },
};

const REC_COLORS = {
  BLOCK:         'bg-red-600 text-white',
  MANUAL_REVIEW: 'bg-amber-500 text-white',
  APPROVE:       'bg-green-600 text-white',
};

function getTruForMeta(integrity) {
  if (integrity === null || integrity === undefined) return null;
  if (integrity < 0.30) return { label: 'Critical Tampering', pct: Math.round(integrity * 100), barColor: '#ef4444', textColor: 'text-red-600', bgColor: 'bg-red-50', borderColor: 'border-red-200', icon: '🚨' };
  if (integrity < 0.50) return { label: 'High Suspicion',     pct: Math.round(integrity * 100), barColor: '#f97316', textColor: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-200', icon: '⚠️' };
  if (integrity < 0.70) return { label: 'Moderate Anomaly',   pct: Math.round(integrity * 100), barColor: '#f59e0b', textColor: 'text-amber-600', bgColor: 'bg-amber-50', borderColor: 'border-amber-200', icon: '⚠' };
  if (integrity < 0.85) return { label: 'Minor Concern',      pct: Math.round(integrity * 100), barColor: '#3b82f6', textColor: 'text-blue-600', bgColor: 'bg-blue-50', borderColor: 'border-blue-200', icon: 'ℹ️' };
  return                       { label: 'Appears Authentic',  pct: Math.round(integrity * 100), barColor: '#22c55e', textColor: 'text-green-600', bgColor: 'bg-green-50', borderColor: 'border-green-200', icon: '✅' };
}

export function MLResultCard({ result }) {
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [copied, setCopied]           = useState(false);

  if (!result) return null;

  const risk    = result.risk_level    || 'LOW';
  const rec     = result.recommendation || 'APPROVE';
  const score   = result.final_score_pct ?? result.risk_score ?? 0;
  const styles  = RISK_STYLES[risk] || RISK_STYLES.LOW;

  const forensicRisk    = result.forensic_score ?? result.breakdown?.doc_forensic ?? null;
  const truforIntegrity = forensicRisk !== null ? Math.max(0, Math.min(1, 1 - forensicRisk)) : null;
  const truforMeta      = getTruForMeta(truforIntegrity);

  const copyReport = () => {
    navigator.clipboard.writeText(result.llm_report || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const forensicPct = ((result.breakdown?.forensic_score ?? result.forensic_score ?? 0) * 100).toFixed(0);
  const behavPct    = ((result.breakdown?.behavioral_score ?? result.behavioral_score ?? 0) * 100).toFixed(0);
  const conflictCnt = result.conflicts?.length ?? 0;
  const benfordOk   = (result.benford_score ?? 0) <= 0.3;

  const statCards = [
    {
      label: 'Forensics',
      value: forensicPct + '%',
      sub:   'Document integrity risk',
      icon:  '🔍',
      color: Number(forensicPct) > 50 ? 'text-red-600' : Number(forensicPct) > 25 ? 'text-amber-600' : 'text-green-600',
    },
    {
      label: 'Behavioral',
      value: behavPct + '%',
      sub:   'Session anomaly score',
      icon:  '👁',
      color: Number(behavPct) > 50 ? 'text-red-600' : Number(behavPct) > 25 ? 'text-amber-600' : 'text-blue-600',
    },
    {
      label: 'Conflicts',
      value: conflictCnt + ' found',
      sub:   result.doc_type && result.doc_type.includes('+') ? 'Cross-document mismatches' : 'OCR & Semantic Anomalies',
      icon:  conflictCnt > 0 ? '⚡' : '✓',
      color: conflictCnt > 0 ? 'text-red-600' : 'text-green-600',
    },
    {
      label: 'Benford',
      value: benfordOk ? '✓ Normal' : '⚠ Suspect',
      sub:   'Number distribution law',
      icon:  benfordOk ? '📊' : '📉',
      color: benfordOk ? 'text-green-600' : 'text-amber-600',
    },
  ];

  return (
    <div className="w-full rounded-xl border border-gray-200 shadow-sm bg-white overflow-hidden">

      {/* ── Header — colored by risk level ── */}
      <div className={`px-6 py-4 border-b ${styles.header}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
              AI Fraud Analysis
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              Audit ID: {result.audit_id || 'N/A'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${styles.badge}`}>
              {risk}
            </span>
            <span className={`px-4 py-1 rounded-full text-sm font-semibold ${REC_COLORS[rec] || 'bg-gray-500 text-white'}`}>
              {rec.replace('_', ' ')}
            </span>
          </div>
        </div>
      </div>

      {/* ── Score + progress bar ── */}
      <div className="px-6 py-5 border-b border-gray-100">
        <div className="flex items-end gap-3">
          <span className={`text-7xl font-black leading-none ${styles.score}`}>
            {Math.round(score)}
          </span>
          <div className="mb-2">
            <span className="text-2xl text-gray-400">/ 100</span>
            <p className="text-xs text-gray-500 mt-1 font-medium uppercase tracking-wide">
              Risk Score
            </p>
          </div>
        </div>
        <div className={`mt-3 w-full ${styles.barBg} rounded-full h-2 overflow-hidden`}>
          <div
            className={`h-2 rounded-full ${styles.bar} transition-all duration-500`}
            style={{ width: `${Math.min(score, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>0 — Safe</span>
          <span>50 — Medium</span>
          <span>100 — Critical</span>
        </div>
      </div>

      {/* ── Math reconciliation ── */}
      {result.math_passed !== undefined && (
        <div className={`px-6 py-3 border-b border-gray-100 flex items-center gap-2 text-sm ${
          result.math_passed
            ? 'bg-green-50 text-green-700'
            : 'bg-red-50 text-red-700'
        }`}>
          <span className="text-base">{result.math_passed ? '✓' : '⚠'}</span>
          <span className="font-medium">
            Math Reconciliation: {result.math_passed
              ? 'Totals consistent'
              : 'Total mismatch detected — possible tampering'}
          </span>
        </div>
      )}

      {/* ── 4 stat cards ── */}
      <div className="px-6 py-4 grid grid-cols-2 sm:grid-cols-4 gap-3 border-b border-gray-100">
        {statCards.map(({ label, value, sub, icon, color }) => (
          <div key={label} className="bg-gray-50 rounded-lg p-3 border border-gray-100 hover:shadow-sm transition-shadow">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm">{icon}</span>
              <p className="text-xs text-gray-500 font-medium">{label}</p>
            </div>
            <p className={`text-sm font-bold ${color}`}>{value}</p>
            <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* ── TruFor Integrity Gauge ── */}
      {truforIntegrity !== null && truforMeta && (
        <div className={`px-6 py-4 border-b border-gray-100 ${truforMeta.bgColor}`}>
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
                Document Integrity (TruFor)
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                Scale: 0.0 = Forged → 1.0 = Authentic
              </p>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{truforMeta.icon}</span>
                <span className={`text-2xl font-black ${truforMeta.textColor}`}>
                  {truforIntegrity.toFixed(3)}
                </span>
              </div>
              <p className={`text-xs font-semibold ${truforMeta.textColor} mt-0.5`}>
                {truforMeta.label}
              </p>
            </div>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="h-2 rounded-full transition-all duration-700"
              style={{
                width: `${truforIntegrity * 100}%`,
                backgroundColor: truforMeta.barColor,
              }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0.0 Forged</span>
            <span>0.5 Uncertain</span>
            <span>1.0 Authentic</span>
          </div>
        </div>
      )}

      {/* ── Applicant info ── */}
      {result.applicant_name && result.applicant_name !== 'Unknown' && (
        <div className="px-6 py-4 bg-blue-50 border-b border-blue-100">
          <p className="text-xs font-semibold text-blue-600 uppercase tracking-widest mb-3">
            Extracted Information
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-gray-500">Applicant</p>
              <p className="text-sm font-semibold text-gray-800">{result.applicant_name}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">PAN</p>
              <p className="text-sm font-semibold text-gray-800 font-mono">{result.pan_number || 'N/A'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Document Type</p>
              <p className="text-sm font-semibold text-gray-800">{result.doc_type || 'Unknown'}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Top risk factors ── */}
      {result.top_risk_factors?.length > 0 && (
        <div className="px-6 py-4 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
            Risk Factors
          </p>
          <div className="space-y-2">
            {result.top_risk_factors.map((f, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <span className={`text-xs px-2 py-0.5 rounded font-semibold mt-0.5 ${
                  f.severity === 'HIGH' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                }`}>
                  {f.severity}
                </span>
                <div>
                  <p className="text-sm font-semibold text-gray-800">{f.factor}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{f.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Document conflicts ── */}
      {result.conflicts?.length > 0 && (
        <div className="px-6 py-4 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
            Document Conflicts
          </p>
          <div className="space-y-2">
            {result.conflicts.map((c, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-red-50 rounded-lg border border-red-100">
                <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded font-semibold mt-0.5 whitespace-nowrap">
                  {c.severity}
                </span>
                <p className="text-sm text-gray-700">{c.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Metadata flags ── */}
      {result.metadata_flags?.length > 0 && (
        <div className="px-6 py-4 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
            Metadata Flags
          </p>
          <div className="space-y-1">
            {result.metadata_flags.map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 rounded-lg px-3 py-2 border border-amber-100 font-medium">
                <span>⚠️</span><span>{f}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── ELA Heatmap toggle ── */}
      {result.heatmap_b64 && (
        <div className="px-6 py-4 border-b border-gray-100">
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className="text-sm text-blue-700 hover:text-blue-900 font-medium flex items-center gap-1 transition-colors"
          >
            {showHeatmap ? '▼ Hide' : '▶ Show'} ELA Tamper Heatmap
          </button>
          {showHeatmap && (
            <div className="mt-3 rounded-lg overflow-hidden border border-gray-200">
              <img
                src={`data:image/png;base64,${result.heatmap_b64}`}
                alt="ELA tamper heatmap"
                className="w-full"
                style={{ minHeight: '200px' }}
              />
              <p className="text-xs text-gray-400 p-2 text-center bg-gray-50">
                Highlighted regions indicate potential pixel manipulation
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── LLM Underwriter Report ── */}
      <div className="px-6 py-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
            AI Underwriter Report
          </p>
          <button
            onClick={copyReport}
            className="text-xs text-blue-700 hover:text-blue-900 font-medium border border-blue-200 bg-blue-50 px-3 py-1 rounded-md transition-colors"
          >
            {copied ? '✓ Copied' : 'Copy'}
          </button>
        </div>
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
          <pre
            className="text-sm text-gray-700 whitespace-pre-wrap font-mono leading-relaxed overflow-auto"
            style={{ maxHeight: '300px' }}
          >
            {result.llm_report || 'No report generated'}
          </pre>
        </div>
      </div>

      {/* ── Raw OCR Text ── */}
      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
        <details className="group cursor-pointer">
          <summary className="text-xs font-semibold text-gray-500 uppercase tracking-widest flex items-center justify-between outline-none">
            Raw OCR Extracted Text
            <span className="text-gray-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 bg-white border border-gray-200 rounded p-3 max-h-60 overflow-y-auto">
            <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono">
              {result.entities?.full_text || 'No text was successfully extracted from this document.'}
            </pre>
          </div>
        </details>
      </div>
    </div>
  );
}
