# Kavach evaluation report

- Run: 2026-09-27T17:08:58+05:30 | model: `sarvam-105b` | dataset: `dataset.jsonl`
- Cases: 40 (40 ok, 0 errors) | concurrency 4 | wall time 139s
- Dataset is synthetic and hand-written; see eval/README.md. Small n: treat differences of one or two cases as noise.

## Lenient: positive = verdict in {scam, suspicious}

| System | Acc | Precision | Recall | F1 | FPR | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|---|---|
| Rules only (independent) | 62.5% | 85.7% | 30.0% | 44.4% | 5.0% | 6 | 1 | 19 | 14 |
| Rules residual (in fused) | 50.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | 20 | 20 |
| AI only (verified claims) | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 20 | 0 | 20 | 0 |
| Fused (product) | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 20 | 0 | 20 | 0 |

## Strict: positive = verdict == scam

| System | Acc | Precision | Recall | F1 | FPR | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|---|---|
| Rules only (independent) | 52.5% | 100.0% | 5.0% | 9.5% | 0.0% | 1 | 0 | 20 | 19 |
| Rules residual (in fused) | 50.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | 20 | 20 |
| AI only (verified claims) | 85.0% | 100.0% | 70.0% | 82.4% | 0.0% | 14 | 0 | 20 | 6 |
| Fused (product) | 85.0% | 100.0% | 70.0% | 82.4% | 0.0% | 14 | 0 | 20 | 6 |

## Evidence grounding

| AI claims | Verified | Rejected (quote not in source) | Verification rate | Cases with rejections | Corroborated findings | Degraded (LLM down) |
|---|---|---|---|---|---|---|
| 63 | 61 | 2 | 96.8% | 1 | 29 | 0 |

## Latency (per case, end-to-end analyse)

| p50 | p95 | max | mean |
|---|---|---|---|
| 5.7s | 41.4s | 51.7s | 12.9s |

## Per-language accuracy (lenient)

| Language | n | Rules | AI | Fused |
|---|---|---|---|---|
| bn | 4 | 75.0% | 100.0% | 100.0% |
| en | 8 | 62.5% | 100.0% | 100.0% |
| gu | 2 | 50.0% | 100.0% | 100.0% |
| hi | 6 | 66.7% | 100.0% | 100.0% |
| hinglish | 4 | 50.0% | 100.0% | 100.0% |
| kn | 2 | 50.0% | 100.0% | 100.0% |
| ml | 2 | 100.0% | 100.0% | 100.0% |
| mr | 2 | 50.0% | 100.0% | 100.0% |
| pa | 2 | 50.0% | 100.0% | 100.0% |
| ta | 4 | 100.0% | 100.0% | 100.0% |
| te | 4 | 25.0% | 100.0% | 100.0% |

## Per-category accuracy (fused, lenient)

| Category | n | Fused acc |
|---|---|---|
| legit:appointment_reminder | 2 | 100.0% |
| legit:bank_credit_alert | 1 | 100.0% |
| legit:bank_debit_alert | 1 | 100.0% |
| legit:bank_kyc_advisory | 1 | 100.0% |
| legit:court_notice | 1 | 100.0% |
| legit:delivery_notification | 2 | 100.0% |
| legit:govt_scheme | 1 | 100.0% |
| legit:municipal_notice | 1 | 100.0% |
| legit:otp_delivery | 2 | 100.0% |
| legit:police_verification | 1 | 100.0% |
| legit:school_notice | 2 | 100.0% |
| legit:tax_reminder | 2 | 100.0% |
| legit:utility_bill | 3 | 100.0% |
| scam:cashback_link | 1 | 100.0% |
| scam:courier_drugs | 2 | 100.0% |
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
| s01_en_digital_arrest | en | scam | scam | 100 | scam | scam | 6 | 0 | 9.5s | AUTHORITY_IMPERSONATION,DIGITAL_ARREST,PAYMENT_TO_UNOFFICIAL,SECRECY_ISOLATION,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l01_en_bank_debit | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 51.7s |  |
| s02_en_courier_drugs | en | scam | scam | 95 | low_risk | scam | 4 | 0 | 8.0s | AUTHORITY_IMPERSONATION,PARCEL_CONTRABAND,SECRECY_ISOLATION,URGENCY_PRESSURE |
| l02_en_otp_delivery | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 26.5s |  |
| s03_en_task_job | en | scam | scam | 84 | low_risk | scam | 5 | 0 | 8.4s | JOB_INVESTMENT_LURE,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l03_en_delivery | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 41.4s |  |
| s04_en_investment | en | scam | scam | 85 | low_risk | scam | 3 | 0 | 46.6s | JOB_INVESTMENT_LURE,SUSPICIOUS_LINK,URGENCY_PRESSURE |
| l04_en_itr_reminder | en | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 5.0s |  |
| s05_hi_fake_kyc | hi | scam | scam | 84 | low_risk | scam | 4 | 0 | 29.4s | KYC_ACCOUNT_BLOCK,SUSPICIOUS_LINK,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l05_hi_electricity_bill | hi | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.7s |  |
| s06_hi_electricity_cut | hi | scam | scam | 81 | low_risk | scam | 3 | 0 | 7.6s | AUTHORITY_IMPERSONATION,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l06_hi_otp_delivery | hi | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 23.1s |  |
| s07_hi_anydesk_refund | hi | scam | scam | 99 | suspicious | scam | 3 | 0 | 8.0s | AUTHORITY_IMPERSONATION,PAYMENT_TO_UNOFFICIAL,REMOTE_ACCESS |
| l07_hi_police_verification | hi | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 5.3s |  |
| s08_hinglish_otp_request | hinglish | scam | scam | 86 | low_risk | scam | 3 | 0 | 25.9s | CREDENTIAL_REQUEST,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l08_hinglish_appointment | hinglish | legit | low_risk | 7 | low_risk | low_risk | 1 | 0 | 2.8s | URGENCY_PRESSURE |
| s09_hinglish_loan_app | hinglish | scam | suspicious | 64 | low_risk | suspicious | 3 | 0 | 23.7s | JOB_INVESTMENT_LURE,PAYMENT_TO_UNOFFICIAL,URGENCY_PRESSURE |
| l09_hinglish_bank_kyc_advisory | hinglish | legit | low_risk | 14 | low_risk | low_risk | 2 | 0 | 1.3s | AUTHORITY_IMPERSONATION,KYC_ACCOUNT_BLOCK |
| s10_ta_lottery | ta | scam | suspicious | 66 | suspicious | suspicious | 2 | 0 | 29.8s | PAYMENT_TO_UNOFFICIAL,PRIZE_REFUND_LURE |
| l10_ta_school_notice | ta | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.6s |  |
| s11_ta_digital_arrest | ta | scam | scam | 100 | suspicious | scam | 5 | 0 | 8.2s | AUTHORITY_IMPERSONATION,DIGITAL_ARREST,SECRECY_ISOLATION,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l11_ta_electricity_bill | ta | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 3.6s |  |
| s12_te_electricity_cut | te | scam | suspicious | 69 | low_risk | suspicious | 3 | 0 | 5.7s | AUTHORITY_IMPERSONATION,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l12_te_govt_scheme | te | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.2s |  |
| s13_te_cashback_link | te | scam | scam | 98 | low_risk | scam | 4 | 0 | 8.8s | CREDENTIAL_REQUEST,PRIZE_REFUND_LURE,SUSPICIOUS_LINK,URGENCY_PRESSURE |
| l13_te_credit_alert | te | legit | low_risk | 26 | suspicious | low_risk | 1 | 0 | 2.9s | CREDENTIAL_REQUEST |
| s14_bn_sim_kyc | bn | scam | scam | 99 | suspicious | scam | 4 | 0 | 5.6s | CREDENTIAL_REQUEST,KYC_ACCOUNT_BLOCK,UNOFFICIAL_CONTACT,URGENCY_PRESSURE |
| l14_bn_property_tax | bn | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 3.1s |  |
| s15_bn_task_job | bn | scam | suspicious | 55 | low_risk | suspicious | 2 | 0 | 5.5s | JOB_INVESTMENT_LURE |
| l15_bn_delivery | bn | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 1.4s |  |
| s16_mr_courier | mr | scam | suspicious | 46 | low_risk | suspicious | 2 | 2 | 26.1s | PARCEL_CONTRABAND,SECRECY_ISOLATION |
| l16_mr_lok_adalat | mr | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.6s |  |
| s17_kn_investment | kn | scam | scam | 82 | low_risk | scam | 4 | 0 | 37.7s | JOB_INVESTMENT_LURE,OTHER_RED_FLAG,SUSPICIOUS_LINK |
| l17_kn_water_bill | kn | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 3.9s |  |
| s18_ml_fake_customer_care | ml | scam | scam | 98 | suspicious | scam | 3 | 0 | 5.7s | AUTHORITY_IMPERSONATION,CREDENTIAL_REQUEST,URGENCY_PRESSURE |
| l18_ml_appointment | ml | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.4s |  |
| s19_gu_lottery | gu | scam | scam | 90 | low_risk | scam | 3 | 0 | 6.1s | PAYMENT_TO_UNOFFICIAL,PRIZE_REFUND_LURE,UNOFFICIAL_CONTACT |
| l19_gu_gst_reminder | gu | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.2s |  |
| s20_pa_relative_impersonation | pa | scam | suspicious | 60 | low_risk | suspicious | 2 | 0 | 20.7s | SECRECY_ISOLATION,URGENCY_PRESSURE |
| l20_pa_school_ptm | pa | legit | low_risk | 0 | low_risk | low_risk | 0 | 0 | 2.1s |  |

## Rejected AI claims (not found in the source text)

- `s16_mr_courier` PARCEL_CONTRABAND: त्म्च्य नावान पाश स पाऱ्ះ ា 	ext{ड्रग्स} 	ext{आणि बनावट पासपोर्ट सापडले आहेत}
- `s16_mr_courier` PAYMENT_TO_UNOFFICIAL: ext{₹85, ००० सुरक्षित खात्यात जमा करा}
