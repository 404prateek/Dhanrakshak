import sys
sys.path.insert(0, '.')

from ml_engine.ocr_nlp.benford_checker import BenfordChecker
b = BenfordChecker()

# Real-ish amounts (should pass)
real = ['1,20,000', '2,30,000', '1,85,000', '3,10,000', '1,50,000', '2,00,000', '1,75,000', '2,95,000']
r1 = b.check(real)
print('Real data  score:', r1['benford_score'], 'suspicious:', r1['is_suspicious'], 'chi2:', r1['chi_square'])
print('  flag:', r1['flag'])

# Suspicious (all starting with 8 or 9)
fake = ['8,40,000', '9,00,000', '8,75,000', '9,50,000', '8,25,000', '9,10,000', '8,60,000', '9,80,000']
r2 = b.check(fake)
print('Fake data  score:', r2['benford_score'], 'suspicious:', r2['is_suspicious'], 'chi2:', r2['chi_square'])
print('  flag:', r2['flag'])

assert r2['benford_score'] > r1['benford_score'], 'FAIL: fake score should be > real score'
print('PASS')

# Edge case: too few amounts
tiny = ['1,000', '2,000']
r3 = b.check(tiny)
print('Too few:   score:', r3['benford_score'], 'suspicious:', r3['is_suspicious'])
assert r3['is_suspicious'] == False, 'FAIL: too few samples should not be suspicious'

# Verify score_fusion accepts benford_score
from ml_engine.trust_engine.score_fusion import TrustEngine
t = TrustEngine()
risk = t.compute_risk(
    trufor_score=0.9, ela_score=0.9, ocr_conflicts=[],
    behavioral_score=0.1, metadata_flags=[], rule_base_score=5,
    benford_score=r2['benford_score']
)
benford_in_breakdown = risk['component_scores']['doc_forensic_breakdown']['benford']
print('TrustEngine benford in breakdown:', benford_in_breakdown)
assert benford_in_breakdown == round(r2['benford_score'], 6), 'FAIL: benford not in breakdown'
print('ALL PASS')
