# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Email or privately message the maintainers with:

- A description of the issue
- Steps to reproduce
- Affected version / commit if known
- Any proof-of-concept (kept minimal)

We will acknowledge reports as soon as practical and work on a fix before any public disclosure.

## Hard rules for operators

- Never commit `.env`, API keys, cookies, or Chrome profile data
- Keep `BACKEND_HOST=127.0.0.1` unless you intentionally expose the API behind auth
- Treat browser automation sessions as privileged — they can access your logged-in Snapgen/Zsky account
- Review generated scripts before publishing; AI output can be wrong or sensitive

## Scope

ContentFactory is a **local-first** tool. It is not a multi-tenant SaaS. If you deploy it on a network, you are responsible for authentication, TLS, and access control.
