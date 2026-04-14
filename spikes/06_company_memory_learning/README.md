# 06 Company Memory Learning

This spike learns a reusable company-specific memory pack from multiple years of paired Chinese / English annual reports.

Goals:

- avoid overfitting to a single report year
- learn reusable company-level title / navigation / term conventions
- summarize recurring page archetypes and layout priors
- feed the learned memory back into the translation pipeline without requiring a page-by-page teacher at runtime

Primary script:

- `build_company_memory.py`

Outputs:

- `company_memory.json`
- `mapping_debug.json`

