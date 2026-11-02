# Security policy

## Scope

SafeSight AI is a research prototype designed to run **locally**:
- The Streamlit server binds to `localhost`.
- There is no authentication.
- The SQLite database and evidence frames are stored unencrypted on disk.

**Do not expose it to a network** without adding authentication, TLS and access controls ([docs/deployment.md](docs/deployment.md)).

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub's private vulnerability reporting (**Security › Report a vulnerability**) on this repository, or contact the maintainer through [@nj-codes-24](https://github.com/nj-codes-24). Include:
- Steps to reproduce.
- The affected files.
- The impact.

We aim to acknowledge reports within 7 days.

## Data protection

Evidence frames can show identifiable people. If you run the system on real footage:
- Obtain the necessary consent.
- Set a retention period.
- Never commit `logs/`, databases or footage. They are git-ignored by default.

## Supported versions

Only the latest release receives fixes.
