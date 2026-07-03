import React, { useState } from 'react';

const RISK_STYLES = {
  HIGH: {
    header:  'bg-red-50 border-red-200',
    badge:   'bg-red-100 text-red-700 border border-red-200',
    score:   'text-red-600',
    bar:     'bg-red-500',
    barBg:   'bg-red-100',
  },
  MEDIUM: {
    header:  'bg-amber-50 border-amber-200',
    badge:   'bg-amber-100 text-amber-700 border border-amber-200',
    score:   'text-amber-600',
    bar:     'bg-amber-500',
    barBg:   'bg-amber-100',
  },
  LOW: {
    header:  'bg-green-50 border-green-200',
    badge:   'bg-green-100 text-green-700 border border-green-200',
    score:   'text-green-600',
    bar:     'bg-green-500',
    barBg:   'bg-green-100',
  },
};

const REC_COLORS = {
  BLOCK:         'bg-red-600 text-white',
  REJECT:        'bg-red-600 text-white',
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

// Helper to safely get string values for comparison
const getStr = (val) => {
  if (Array.isArray(val)) return val.length > 0 ? val.map(v => String(v).trim()).join(', ') : 'None';
  return val ? String(val).trim() : 'None';
};

export function CrossDocComparisonCard({ result }) {
  const [copied, setCopied] = useState(false);

  if (!result) return null;

  const risk    = result.risk_level    || 'LOW';
  const rec     = result.recommendation || 'APPROVE';
  const score   = result.final_score_pct ?? result.risk_score ?? 0;
  const styles  = RISK_STYLES[risk] || RISK_STYLES.LOW;

  const copyReport = () => {
    navigator.clipboard.writeText(result.llm_report || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Extract entities
  const ent1 = result.entities_primary || {};
  const ent2 = result.entities_secondary || {};
  
  // Extract forensics
  const f1 = result.forensic_primary?.integrity_score;
  const f2 = result.forensic_secondary?.integrity_score;
  const truforMeta1 = getTruForMeta(f1 !== undefined ? f1 : 0.5);
  const truforMeta2 = getTruForMeta(f2 !== undefined ? f2 : 0.5);

  const docTypes = (result.doc_type || 'Primary + Secondary').split('+').map(s => s.trim());
  const type1 = docTypes[0] || 'Primary Document';
  const type2 = docTypes[1] || 'Secondary Document';

  const names1 = getStr(ent1.names);
  const names2 = getStr(ent2.names);
  const namesMatch = names1 === names2 || names1.includes(names2) || names2.includes(names1);

  const pan1 = getStr(ent1.pan);
  const pan2 = getStr(ent2.pan);
  const panMatch = pan1 === pan2 && pan1 !== 'None';

  const amounts1 = getStr(ent1.amounts);
  const amounts2 = getStr(ent2.amounts);
  
  const dates1 = getStr(ent1.dates);
  const dates2 = getStr(ent2.dates);

  return (
    <div className="w-full rounded-xl border border-gray-200 shadow-sm bg-white overflow-hidden mb-6">
      {/* Header */}
      <div className={`px-6 py-4 border-b ${styles.header}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
              Cross-Document Pair Analysis
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

      {/* Score */}
      <div className="px-6 py-5 border-b border-gray-100 bg-slate-50">
        <div className="flex items-end gap-3">
          <span className={`text-7xl font-black leading-none ${styles.score}`}>
            {Math.round(score)}
          </span>
          <div className="mb-2">
            <span className="text-2xl text-gray-400">/ 100</span>
            <p className="text-xs text-gray-500 mt-1 font-medium uppercase tracking-wide">
              Combined Risk Score
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

      {/* Side-by-side comparison */}
      <div className="grid grid-cols-2 divide-x divide-gray-200">
        
        {/* PRIMARY DOCUMENT */}
        <div className="p-6 bg-white">
          <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wider mb-4 border-b border-gray-100 pb-2">
            {type1}
          </h3>
          
          {/* Integrity */}
          {truforMeta1 && (
            <div className={`mb-6 p-3 rounded-lg border ${truforMeta1.bgColor} ${truforMeta1.borderColor}`}>
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-semibold text-gray-600">Forensic Integrity</span>
                <span className={`text-sm font-bold ${truforMeta1.textColor}`}>{truforMeta1.icon} {(f1 * 100).toFixed(0)}%</span>
              </div>
              <p className={`text-xs ${truforMeta1.textColor}`}>{truforMeta1.label}</p>
            </div>
          )}

          {/* Extracted Fields */}
          <div className="space-y-4">
            {names1 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase">Names Extracted</p>
                <p className="text-sm font-semibold text-gray-800 break-words">{names1}</p>
              </div>
            )}
            {pan1 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase">PAN Number</p>
                <p className="text-sm font-semibold font-mono text-gray-800">{pan1}</p>
              </div>
            )}
            {amounts1 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase">Amounts</p>
                <p className="text-sm text-gray-700">{amounts1}</p>
              </div>
            )}
            {dates1 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase">Dates</p>
                <p className="text-sm text-gray-700">{dates1}</p>
              </div>
            )}
            {names1 === 'None' && pan1 === 'None' && amounts1 === 'None' && dates1 === 'None' && (
              <p className="text-xs text-gray-400 italic">No text entities extracted</p>
            )}
          </div>
        </div>

        {/* SECONDARY DOCUMENT */}
        <div className="p-6 bg-slate-50/50">
          <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wider mb-4 border-b border-gray-100 pb-2">
            {type2}
          </h3>
          
          {/* Integrity */}
          {truforMeta2 && (
            <div className={`mb-6 p-3 rounded-lg border ${truforMeta2.bgColor} ${truforMeta2.borderColor}`}>
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-semibold text-gray-600">Forensic Integrity</span>
                <span className={`text-sm font-bold ${truforMeta2.textColor}`}>{truforMeta2.icon} {(f2 * 100).toFixed(0)}%</span>
              </div>
              <p className={`text-xs ${truforMeta2.textColor}`}>{truforMeta2.label}</p>
            </div>
          )}

          {/* Extracted Fields */}
          <div className="space-y-4">
            {names2 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase flex items-center justify-between">
                  <span>Names Extracted</span>
                  {names1 !== 'None' && (
                    namesMatch ? <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-bold">MATCH</span> 
                               : <span className="text-[10px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-bold">MISMATCH</span>
                  )}
                </p>
                <p className={`text-sm font-semibold break-words ${!namesMatch && names2 !== 'None' && names1 !== 'None' ? 'text-red-600' : 'text-gray-800'}`}>
                  {names2}
                </p>
              </div>
            )}
            {pan2 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase flex items-center justify-between">
                  <span>PAN Number</span>
                  {pan1 !== 'None' && (
                    panMatch ? <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-bold">MATCH</span> 
                             : <span className="text-[10px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-bold">MISMATCH</span>
                  )}
                </p>
                <p className={`text-sm font-semibold font-mono ${!panMatch && pan1 !== 'None' && pan2 !== 'None' ? 'text-red-600' : 'text-gray-800'}`}>
                  {pan2}
                </p>
              </div>
            )}
            {amounts2 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase">Amounts</p>
                <p className="text-sm text-gray-700">{amounts2}</p>
              </div>
            )}
            {dates2 !== 'None' && (
              <div>
                <p className="text-xs text-gray-500 mb-1 font-medium uppercase">Dates</p>
                <p className="text-sm text-gray-700">{dates2}</p>
              </div>
            )}
            {names2 === 'None' && pan2 === 'None' && amounts2 === 'None' && dates2 === 'None' && (
              <p className="text-xs text-gray-400 italic">No text entities extracted</p>
            )}
          </div>
        </div>

      </div>

      {/* Cross-Document Conflicts */}
      {result.conflicts?.length > 0 && (
        <div className="px-6 py-4 border-t border-gray-200 bg-red-50/30">
          <p className="text-xs font-semibold text-red-600 uppercase tracking-widest mb-3 flex items-center">
            <span className="mr-2">⚡</span> Detected Conflicts & Anomalies
          </p>
          <div className="space-y-2">
            {result.conflicts.map((c, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-red-50 rounded-lg border border-red-100 shadow-sm">
                <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded font-bold mt-0.5 whitespace-nowrap">
                  {c.severity}
                </span>
                <div>
                  <p className="text-sm font-semibold text-red-900">{c.type || 'Anomaly'}</p>
                  <p className="text-sm text-red-700 mt-0.5">{c.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LLM Report */}
      <div className="px-6 py-4 border-t border-gray-200">
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

      {/* Raw OCR Text */}
      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
        <details className="group cursor-pointer">
          <summary className="text-xs font-semibold text-gray-500 uppercase tracking-widest flex items-center justify-between outline-none">
            Raw OCR Extracted Text
            <span className="text-gray-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded p-3 max-h-60 overflow-y-auto">
              <p className="text-[10px] font-bold text-gray-400 mb-2">{type1}</p>
              <pre className="text-[11px] text-gray-600 whitespace-pre-wrap font-mono">
                {result.entities_primary?.full_text || 'No text was successfully extracted from this document.'}
              </pre>
            </div>
            <div className="bg-white border border-gray-200 rounded p-3 max-h-60 overflow-y-auto">
              <p className="text-[10px] font-bold text-gray-400 mb-2">{type2}</p>
              <pre className="text-[11px] text-gray-600 whitespace-pre-wrap font-mono">
                {result.entities_secondary?.full_text || 'No text was successfully extracted from this document.'}
              </pre>
            </div>
          </div>
        </details>
      </div>

    </div>
  );
}
