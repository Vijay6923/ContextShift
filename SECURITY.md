# Security Policy

## Supported Versions

ContextShift is pre-1.0 (currently `0.x`). Until a `1.0` release, only
the latest published release receives security fixes.

| Version | Supported |
| --- | --- |
| Latest `0.x` | :white_check_mark: |
| Older `0.x` | :x: |

## Reporting a Vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

**Preferred: GitHub private vulnerability reporting.** Once enabled
for this repository (Settings → Security → "Private vulnerability
reporting"), use the *"Report a vulnerability"* button under the
[Security tab](https://github.com/Vijay6923/ContextShift/security) —
this opens a private advisory only the maintainer can see, with no
public disclosure until a fix is ready. This is the primary,
recommended path; if you're reading this before it's been enabled,
open a regular issue asking the maintainer to enable it, without
describing the vulnerability itself.

**Fallback, if private reporting isn't available yet:** open a GitHub
issue titled only "Security contact needed" (no vulnerability details
in the issue itself) addressed to [@Vijay6923](https://github.com/Vijay6923),
requesting a private channel to report through.

Whichever path you use, include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce it (a minimal code sample is ideal).
- The version of `contextshift` affected.

You should receive an acknowledgment within a few days. If the report
is confirmed, a fix will be prepared and a new version released; you'll
be credited in the release notes unless you'd prefer otherwise.

## Scope

`contextshift/` (the library) has no network transport of its own
except within `contextshift/llm/`, `contextshift/vision/`, and the
optional `AnthropicTokenizer` — all of which call a third-party API
using a key the caller supplies. Nothing in the library reads
environment variables, writes to disk, or executes untrusted input.

[`examples/flask-chat/`](examples/flask-chat/) is a demonstration
application, not a production deployment — see its own
[README](examples/flask-chat/README.md) for the environment variables
it expects. Report a vulnerability specific to that example the same
way described above; it will be triaged as demonstration code rather
than library code, but real reports are still welcome.
