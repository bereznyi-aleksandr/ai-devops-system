# BEM-931 v3.5 execution manifest

Status: materialized

Roadmap implemented:
- RM-01..RM-04: foundation registries, passports, elements, rule versioning
- RM-05: role prompts and element prompt profiles
- RM-06: vertical links and inheritance/escalation model
- RM-07: curator-mediated horizontal exchange registry
- RM-08..RM-10: operator notification canon, error-to-rule cycle, initiator return path
- RM-11: legacy runtime inventory/archive status
- RM-12: full minimal governance loop validator

Validation:
```bash
python3 governance/validators/bem931_rm12_validate.py
```

Canonical runtime: `.github/workflows/codex-local.yml`.