import sys
sys.path.insert(0, '.')

from ml_engine.forensic_vision.trufor_wrapper    import TruForDetector
from ml_engine.behavioral_twin.behavior_analyzer  import BehaviorAnalyzer
from ml_engine.trust_engine.score_fusion          import TrustEngine
from ml_engine.ocr_nlp.document_ocr              import CrossDocValidator
from ml_engine.llm_reporter.ollama_reporter       import OllamaReporter

trufor   = TruForDetector()
behavior = BehaviorAnalyzer()
trust    = TrustEngine()
reporter = OllamaReporter()

scenarios = []

# Scenario A: Clean documents
r = trufor.analyze('tools/demo_docs/legitimate_itr.jpg')
risk = trust.compute_risk(trufor_score=r['integrity_score'], ela_score=r['integrity_score'],
    ocr_conflicts=[], behavioral_score=0.1, metadata_flags=[], rule_base_score=5)
scenarios.append(('A: Clean ITR', risk['final_score_pct'], risk['risk_level'], risk['recommendation']))

# Scenario B: Forged doc + income fraud
r = trufor.analyze('tools/demo_docs/forged_itr.jpg')
cv = CrossDocValidator()
income = cv.validate_income(840000, 28000, None)
conflicts = [{'type':'income_mismatch','severity':'HIGH','message':income['flags'][0],'doc1_value':'','doc2_value':''}] if income['flags'] else []
risk = trust.compute_risk(trufor_score=r['integrity_score'], ela_score=r['integrity_score'],
    ocr_conflicts=conflicts, behavioral_score=0.15, metadata_flags=[], rule_base_score=45,
    income_fraud_score=income['income_fraud_score'])
scenarios.append(('B: Forged ITR + Income fraud', risk['final_score_pct'], risk['risk_level'], risk['recommendation']))

# Scenario C: Bot behavior
risk = trust.compute_risk(trufor_score=0.1, ela_score=0.1,
    ocr_conflicts=[], behavioral_score=0.92, metadata_flags=[], rule_base_score=10)
scenarios.append(('C: Bot application', risk['final_score_pct'], risk['risk_level'], risk['recommendation']))

print(f"{'Scenario':<35} {'Score':>6} {'Level':<8} {'Decision'}")
print("-" * 65)
for name, score, level, rec in scenarios:
    print(f"{name:<35} {score:>5.0f}% {level:<8} {rec}")
