"""
Text Risk Analyzer (InvestShield Adaptation)
--------------------------------------------
Analyzes extracted OCR text for semantic fraud indicators using
regex and NLP heuristics (urgency, authority claims, fear/greed logic).
Returns conflicts that integrate natively with Dhanrakshak's Trust Engine.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class TextRiskAnalyzer:
    """
    Offline text analysis engine to flag semantic anomalies in OCR text.
    Uses regex patterns to detect urgency, fake authority claims, 
    and document-specific manipulation markers.
    """

    def __init__(self):
        # Weighted fraud indicators adapted from InvestShield
        self.fraud_indicators = {
            'urgency_indicators': {
                'patterns': [
                    r'urgent(?:ly)?|immediate(?:ly)?|asap|right now|hurry',
                    r'limited time|expires? (?:soon|today)|last chance',
                    r'act fast|quick(?:ly)?|rush|don\'t wait'
                ],
                'severity': 'MEDIUM',
                'description': 'Language indicates false urgency (common in scam compliance/freeze letters)'
            },
            'authority_claims': {
                'patterns': [
                    r'sebi (?:approved|registered|certified)',
                    r'government (?:approved|backed|endorsed)',
                    r'rbi (?:certified|approved|licensed)',
                    r'official(?:ly)? (?:approved|endorsed)'
                ],
                # If these appear but OCR layout implies it's a Police/ED letter, 
                # this is highly suspicious. We flag as MEDIUM and let fusion decide.
                'severity': 'MEDIUM',
                'description': 'Suspicious authority/regulatory claims detected'
            },
            'payment_requests': {
                'patterns': [
                    r'transfer (?:money|amount|funds|₹\d+)',
                    r'pay (?:now|immediately|₹\d+)',
                    r'send (?:money|payment|₹\d+)',
                    r'deposit (?:₹\d+|money|amount)'
                ],
                'severity': 'HIGH',
                'description': 'Direct payment or transfer requests detected in document text'
            },
            'fear_manipulation': {
                'patterns': [
                    r'crash|collapse|lose|risk|danger',
                    r'warning|alert|crisis|emergency|panic|freeze account'
                ],
                'severity': 'HIGH',
                'description': 'Fear-mongering language detected (common in fake ED/Police letters)'
            }
        }

    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Scan OCR text and return a list of conflicts for the Trust Engine.
        """
        conflicts = []
        if not text:
            return conflicts

        text_clean = text.lower()
        text_clean = re.sub(r'\s+', ' ', text_clean).strip()

        for category, info in self.fraud_indicators.items():
            matches_found = []
            for pattern in info['patterns']:
                found = re.findall(pattern, text_clean)
                if found:
                    matches_found.extend(found)
            
            if matches_found:
                # We cap the number of examples we report
                unique_matches = list(set(matches_found))[:3]
                conflicts.append({
                    "type": f"nlp_{category}",
                    "severity": info['severity'],
                    "message": f"{info['description']} (matches: {', '.join(unique_matches)})"
                })

        # Additional offline feature checks
        if text.count('!') > 3:
            conflicts.append({
                "type": "nlp_excessive_punctuation",
                "severity": "LOW",
                "message": "Unprofessional/excessive exclamation marks detected"
            })
            
        caps_words = re.findall(r'\b[A-Z]{4,}\b', text)
        if len(caps_words) > 30:
            conflicts.append({
                "type": "nlp_excessive_capitalization",
                "severity": "LOW",
                "message": f"Excessive uppercase words detected (e.g. {caps_words[0]}, {caps_words[1] if len(caps_words) > 1 else ''})"
            })

        logger.debug(f"TextRiskAnalyzer found {len(conflicts)} semantic conflicts.")
        return conflicts
