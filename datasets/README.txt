TREASURY AI — TEST DATASETS
===========================
7 datasets, each a different reconciliation scenario.
Each folder has invoices.csv and bank_statement.csv.
Upload the matching pair into the Treasury AI workspace.

01_clean_books      Mostly matched, one minor FX variance. Calm baseline.
02_fraud_alert      Duplicate invoice + unknown merchant + missing reference.
03_fx_variances     Every invoice partial — cross-border currency spread.
04_unpaid_invoices  Several invoices with no matching payment (unpaid).
05_enterprise_batch Large 10-invoice batch, mixed outcomes. Big demo.
06_small_business   Small, simple, mostly clean. Quick demo.
07_high_risk_audit  Heaviest risk — duplicates, abnormal amount, offshore wire.

TIP for demos: 02 and 07 show off fraud detection best.
01 or 06 are good for a calm "happy path" walkthrough.
