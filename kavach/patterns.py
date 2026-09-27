"""Fraud-pattern taxonomy shared by the LLM prompt, the rule engine and the scorer.

Built from the public advisories of India's Cyber Crime Coordination Centre (I4C) /
cybercrime.gov.in and RBI's consumer-awareness material on common frauds:
"digital arrest", fake KYC, courier/parcel, prize/refund, task-based jobs,
remote-access apps and requests for OTP/PIN.

`weight` is the probability-like contribution of one high-severity, verified
occurrence to the overall risk (combined with noisy-OR in scoring.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    description: str
    weight: float


PATTERNS: dict[str, Pattern] = {
    p.id: p
    for p in [
        Pattern("DIGITAL_ARREST", "Fake 'digital arrest' / arrest threat",
                "Threatens arrest, a warrant or a case unless the person complies over a call or video call. "
                "Indian law has no 'digital arrest'; real agencies never arrest over video calls.", 0.9),
        Pattern("CREDENTIAL_REQUEST", "Asks for OTP / PIN / password",
                "Asks the person to share an OTP, UPI PIN, CVV, card number, password or login. "
                "Banks and government never ask for these.", 0.85),
        Pattern("REMOTE_ACCESS", "Asks to install a screen-sharing or unknown app",
                "Asks to install AnyDesk, TeamViewer, an APK file or to share the screen.", 0.8),
        Pattern("PAYMENT_TO_UNOFFICIAL", "Money to a personal / 'safe' account",
                "Demands payment to a UPI ID, personal account, 'RBI safe account', gift card or crypto, "
                "or a 'verification'/'clearance' fee.", 0.7),
        Pattern("SECRECY_ISOLATION", "Tells you to keep it secret",
                "Insists the matter is confidential, not to tell family, or not to disconnect the call.", 0.6),
        Pattern("PARCEL_CONTRABAND", "Fake parcel / courier case",
                "Claims a parcel in the person's name contains drugs, fake passports or contraband.", 0.6),
        Pattern("AUTHORITY_IMPERSONATION", "Claims to be police / CBI / RBI / court",
                "Claims to be from a police force, CBI, ED, NCB, customs, TRAI, RBI, a court or a ministry.", 0.5),
        Pattern("KYC_ACCOUNT_BLOCK", "Account / SIM will be blocked",
                "Says KYC has expired or the bank account / SIM / electricity will be cut off imminently "
                "unless the person acts through the caller.", 0.5),
        Pattern("PRIZE_REFUND_LURE", "Prize, lottery, refund or cashback lure",
                "Promises a prize, lottery, KBC win, refund or cashback that needs a fee or details first.", 0.5),
        Pattern("JOB_INVESTMENT_LURE", "Easy money: job tasks or guaranteed returns",
                "Part-time 'tasks', like-and-earn, guaranteed or doubled investment returns, trading groups.", 0.55),
        Pattern("SUSPICIOUS_LINK", "Suspicious link or file",
                "Shortened links, unknown domains, lookalike sites or .apk files.", 0.5),
        Pattern("URGENCY_PRESSURE", "Extreme urgency or threats",
                "Very short deadlines (minutes/hours), threats of police or legal action to force quick action.", 0.35),
        Pattern("UNOFFICIAL_CONTACT", "Official matter over personal channels",
                "An 'official' matter handled via WhatsApp, a personal mobile number or personal email.", 0.35),
        Pattern("OTHER_RED_FLAG", "Other red flag",
                "Any other concrete sign of fraud not covered above.", 0.3),
    ]
}

SEVERITY_FACTOR = {"high": 1.0, "medium": 0.65, "low": 0.35}


def taxonomy_for_prompt() -> str:
    return "\n".join(f"- {p.id}: {p.description}" for p in PATTERNS.values())
