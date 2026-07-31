# Security Policy

## Supported Versions

Security updates are provided for the latest release and the latest commit on
`main`.

| Version | Supported |
|---------|-----------|
| main (latest) | ✅ |
| latest release | ✅ |
| older releases | ❌ |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

To report a vulnerability, email the maintainer at
`RAJA-432 <[your-contact-email]>` with the subject
`[hiil security] <short description>`.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (or a minimal proof of concept).
- Affected versions and components.
- Any suggested fix, if you have one.

You should receive a response within **5 business days**. We will acknowledge
the report, investigate, and keep you informed as we prepare a fix.

## Disclosure Policy

- We ask that you allow us time to address and release a fix before public
  disclosure.
- Once a fix is released, we will credit the reporter (unless they prefer to
  remain anonymous).

## General Security Notes

- Never commit secrets, API keys, or credentials. `.env` is gitignored.
- API keys are set via `hiil key set <provider> <key>` or the `MODEL_API_KEY`
  env var — not plaintext in `config.yaml`.
- The `web_fetch` tool is SSRF-protected against private networks.
- Workspace file tools (`read_text_resource`, `read_dir`, `glob`, `grep`) are
  path-traversal guarded.
