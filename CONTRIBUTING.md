# Contributing

Open an issue first for anything beyond a typo. PRs welcome on:

- New persona templates (designer, recruiter, sales engineer, support lead, founder).
- Corpus generators for new document types (Slack threads, Notion pages, GitHub PRs, Jira tickets).
- PII redaction at ingest (Presidio integration with jurisdiction configs).
- Production deployment templates (Terraform / Helm).
- Better evaluation metrics — current eval is keyword overlap + style cosine.
- Right-to-erasure tooling.
- Memorisation auditing.

## PR notes

- Keep scripts runnable standalone. No implicit dependencies on prior scripts beyond their documented file outputs.
- New dependencies need a one-line justification in the PR.
- Methodology or governance changes: include a short note on the privacy implications.

## What we don't accept

- Real employee correspondence, real customer data, or any non-synthetic content.
- Hard-coded credentials.
- Code that bypasses citation requirements or memorisation audits.

## License

By contributing, you agree your contributions are licensed under MIT (code) and CC0 (synthetic content).
