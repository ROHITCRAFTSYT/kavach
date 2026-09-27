# Kavach evaluation report

- Run: 2026-09-27T17:03:35+05:30 | model: `sarvam-105b` | dataset: `dataset.jsonl`
- Cases: 40 (40 ok, 0 errors) | concurrency 4 | wall time 151s
- Dataset is synthetic and hand-written; see eval/README.md. Small n: treat differences of one or two cases as noise.

## Lenient: positive = verdict in {scam, suspicious}

| System | Acc | Precision | Recall | F1 | FPR | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|---|---|
| Rules only (independent) | 55.0% | 60.0% | 30.0% | 40.0% | 20.0% | 6 | 4 | 16 | 14 |
| Rules residual (in fused) | 47.5% | 0.0% | 0.0% | 0.0% | 5.0% | 0 | 1 | 19 | 20 |
| AI only (verified claims) | 92.5% | 94.7% | 90.0% | 92.3% | 5.0% | 18 | 1 | 19 | 2 |
| Fused (product) | 90.0% | 90.0% | 90.0% | 90.0% | 10.0% | 18 | 2 | 18 | 2 |

## Strict: positive = verdict == scam

| System | Acc | Precision | Recall | F1 | FPR | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|---|---|
| Rules only (independent) | 52.5% | 100.0% | 5.0% | 9.5% | 0.0% | 1 | 0 | 20 | 19 |
| Rules residual (in fused) | 50.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | 20 | 20 |
| AI only (verified claims) | 82.5% | 93.3% | 70.0% | 80.0% | 5.0% | 14 | 1 | 19 | 6 |
| Fused (product) | 82.5% | 93.3% | 70.0% | 80.0% | 5.0% | 14 | 1 | 19 | 6 |

## Evidence grounding

| AI claims | Verified | Rejected (quote not in source) | Verification rate | Cases with rejections | Corroborated findings | Degraded (LLM down) |
|---|---|---|---|---|---|---|
| 56 | 54 | 2 | 96.4% | 2 | 24 | 2 |

## Latency (per case, end-to-end analyse)

| p50 | p95 | max | mean |
|---|---|---|---|
| 6.6s | 46.4s | 63.6s | 14.1s |

## Per-language accuracy (lenient)

| Language | n | Rules | AI | Fused |
|---|---|---|---|---|
| bn | 4 | 75.0% | 100.0% | 100.0% |
| en | 8 | 50.0% | 87.5% | 87.5% |
| gu | 2 | 50.0% | 100.0% | 100.0% |
| hi | 6 | 50.0% | 83.3% | 83.3% |
| hinglish | 4 | 25.0% | 100.0% | 75.0% |
| kn | 2 | 50.0% | 100.0% | 100.0% |
| ml | 2 | 100.0% | 100.0% | 100.0% |
| mr | 2 | 50.0% | 100.0% | 100.0% |
| pa | 2 | 50.0% | 100.0% | 100.0% |
| ta | 4 | 100.0% | 100.0% | 100.0% |
| te | 4 | 25.0% | 75.0% | 75.0% |

## Per-category accuracy (fused, lenient)

| Category | n | Fused acc |
|---|---|---|
| legit:appointment_reminder | 2 | 100.0% |
| legit:bank_credit_alert | 1 | 100.0% |
| legit:bank_debit_alert | 1 | 100.0% |
| legit:bank_kyc_advisory | 1 | 0.0% |
| legit:court_notice | 1 | 100.0% |
| legit:delivery_notification | 2 | 100.0% |
| legit:govt_scheme | 1 | 100.0% |
| legit:municipal_notice | 1 | 100.0% |
| legit:otp_delivery | 2 | 50.0% |
| legit:police_verification | 1 | 100.0% |
| legit:school_notice | 2 | 100.0% |
| legit:tax_reminder | 2 | 100.0% |
| legit:utility_bill | 3 | 100.0% |
| scam:cashback_link | 1 | 0.0% |
| scam:courier_drugs | 2 | 50.0% |
| scam:digital_arrest | 2 | 100.0% |
| scam:electricity_disconnection | 2 | 100.0% |
| scam:fake_customer_care | 1 | 100.0% |
| scam:fake_kyc | 2 | 100.0% |
| scam:fake_loan | 1 | 100.0% |
| scam:investment_group | 2 | 100.0% |
| scam:lottery | 2 | 100.0% |
| scam:otp_request | 1 | 100.0% |
| scam:relative_impersonation | 1 | 100.0% |
| scam:remote_access_refund | 1 | 100.0% |
| scam:task_job | 2 | 100.0% |

## Per-case results

| id | lang | label | fused | risk | rules | AI | findings | rejected | latency | note |
|---|---|---|---|---|---|---|---|---|---|---|
| s01_en_digital_arrest | en | scam | scam | 100 | scam | scam | 6 | 0 | 11.6s | AUTHORITY_IMPERSONATION,CREDENTIAL_REQUEST,DIGITAL_ARREST,PAYMENT_TO_UNOFFICIAL,SECRECY_ISOLATION,URGENCY_PRESSURE |
| l01_en_bank_debit | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 5.1s |  |
| s02_en_courier_drugs | en | scam | low_risk | 31 | low_risk | low_risk | 3 | 0 | 63.6s | **MISS** degraded AUTHORITY_IMPERSONATION,PARCEL_CONTRABAND,URGENCY_PRESSURE |
| l02_en_otp_delivery | en | legit | low_risk | 31 | suspicious | low_risk | 2 | 0 | 5.2s | CREDENTIAL_REQUEST,URGENCY_PRESSURE |
| s03_en_task_job | en | scam | scam | 86 | low_risk | scam | 4 | 0 | 6.6s | JOB_INVESTMENT_LURE,PRIZE_REFUND_LURE,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l03_en_delivery | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 6.6s |  |
| s04_en_investment | en | scam | scam | 85 | low_risk | scam | 3 | 1 | 6.7s | JOB_INVESTMENT_LURE,SUSPICIOUS_LINK,URGENCY_PRESSURE |
| l04_en_itr_reminder | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 4.1s |  |
| s05_hi_fake_kyc | hi | scam | scam | 84 | low_risk | scam | 4 | 0 | 23.4s | KYC_ACCOUNT_BLOCK,SUSPICIOUS_LINK,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l05_hi_electricity_bill | hi | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 5.7s |  |
| s06_hi_electricity_cut | hi | scam | suspicious | 69 | low_risk | suspicious | 3 | 0 | 46.4s | KYC_ACCOUNT_BLOCK,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l06_hi_otp_delivery | hi | legit | scam | 98 | suspicious | scam | 4 | 0 | 7.2s | **MISS** AUTHORITY_IMPERSONATION,CREDENTIAL_REQUEST,SECRECY_ISOLATION,URGENCY_PRESSURE |
| s07_hi_anydesk_refund | hi | scam | scam | 99 | suspicious | scam | 3 | 0 | 6.8s | AUTHORITY_IMPERSONATION,CREDENTIAL_REQUEST,REMOTE_ACCESS |
| l07_hi_police_verification | hi | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 3.9s |  |
| s08_hinglish_otp_request | hinglish | scam | scam | 86 | low_risk | scam | 3 | 0 | 4.3s | CREDENTIAL_REQUEST,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l08_hinglish_appointment | hinglish | legit | low_risk | 7 | low_risk | low_risk | 1 | 0 | 2.7s | URGENCY_PRESSURE |
| s09_hinglish_loan_app | hinglish | scam | scam | 88 | low_risk | scam | 2 | 0 | 7.3s | PAYMENT_TO_UNOFFICIAL,URGENCY_PRESSURE |
| l09_hinglish_bank_kyc_advisory | hinglish | legit | suspicious | 36 | suspicious | low_risk | 3 | 0 | 4.8s | **MISS** AUTHORITY_IMPERSONATION,CREDENTIAL_REQUEST,KYC_ACCOUNT_BLOCK |
| s10_ta_lottery | ta | scam | scam | 95 | suspicious | scam | 3 | 0 | 5.9s | PAYMENT_TO_UNOFFICIAL,PRIZE_REFUND_LURE,UNOFFICIAL_CONTACT |
| l10_ta_school_notice | ta | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.5s |  |
| s11_ta_digital_arrest | ta | scam | scam | 100 | suspicious | scam | 4 | 0 | 7.1s | AUTHORITY_IMPERSONATION,DIGITAL_ARREST,KYC_ACCOUNT_BLOCK,SECRECY_ISOLATION |
| l11_ta_electricity_bill | ta | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.9s |  |
| s12_te_electricity_cut | te | scam | suspicious | 59 | low_risk | suspicious | 3 | 0 | 22.6s | KYC_ACCOUNT_BLOCK,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l12_te_govt_scheme | te | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.8s |  |
| s13_te_cashback_link | te | scam | low_risk | 26 | low_risk | low_risk | 2 | 0 | 56.0s | **MISS** degraded PRIZE_REFUND_LURE,URGENCY_PRESSURE |
| l13_te_credit_alert | te | legit | low_risk | 26 | suspicious | low_risk | 1 | 0 | 4.2s | CREDENTIAL_REQUEST |
| s14_bn_sim_kyc | bn | scam | scam | 99 | suspicious | scam | 4 | 0 | 6.8s | CREDENTIAL_REQUEST,KYC_ACCOUNT_BLOCK,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l14_bn_property_tax | bn | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 3.5s |  |
| s15_bn_task_job | bn | scam | suspicious | 55 | low_risk | suspicious | 2 | 0 | 23.9s | JOB_INVESTMENT_LURE |
| l15_bn_delivery | bn | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 1.7s |  |
| s16_mr_courier | mr | scam | scam | 95 | low_risk | scam | 4 | 0 | 24.2s | AUTHORITY_IMPERSONATION,PARCEL_CONTRABAND,PAYMENT_TO_UNOFFICIAL,SECRECY_ISOLATION |
| l16_mr_lok_adalat | mr | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.7s |  |
| s17_kn_investment | kn | scam | scam | 78 | low_risk | scam | 3 | 0 | 40.6s | JOB_INVESTMENT_LURE,SUSPICIOUS_LINK |
| l17_kn_water_bill | kn | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 23.0s |  |
| s18_ml_fake_customer_care | ml | scam | scam | 97 | suspicious | scam | 2 | 0 | 39.5s | AUTHORITY_IMPERSONATION,CREDENTIAL_REQUEST |
| l18_ml_appointment | ml | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 3.5s |  |
| s19_gu_lottery | gu | scam | suspicious | 50 | low_risk | suspicious | 1 | 1 | 29.9s | PRIZE_REFUND_LURE |
| l19_gu_gst_reminder | gu | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 4.3s |  |
| s20_pa_relative_impersonation | pa | scam | scam | 92 | low_risk | scam | 3 | 0 | 6.9s | PAYMENT_TO_UNOFFICIAL,SECRECY_ISOLATION,URGENCY_PRESSURE |
| l20_pa_school_ptm | pa | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 27.0s |  |

## Rejected AI claims (not found in the source text)

- `s04_en_investment` JOB_INVESTMENT_LURE: Deposit a minimum of Rs 25,000 in our institutional trading app and get a guaran
- `s19_gu_lottery` PAYMENT_TO_UNOFFICIAL: 
