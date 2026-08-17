# Security Policy

## Supported versions

Only the current `main` branch receives security fixes. There is no long-term support branch.

## Reporting a vulnerability

Report privately by email to <miharisoadavidfils@gmail.com>. Please do not open a public issue, and do not disclose the report in a pull request or a discussion.

Include what an attacker can do, the steps to reproduce it, the affected file or route, and the impact you expect. A proof of concept helps.

You will get an acknowledgement within a week, and a decision on whether the report is accepted, with a proposed fix or a mitigation, within two weeks.

## Scope

In scope:

- Authentication, tokens and session handling
- Authorization between users, for example anything that lets a user read or modify another user's conversations
- Injection, for example SQL injection
- Exposure of secrets, credentials or personal data
- Denial of service through the API

Out of scope:

- Findings that need physical access to the machine
- Automated scanner output with no working proof
- Denial of service through a free third-party provider, which is limited by design and reported as a quota issue
- Missing rate limiting that is already tracked as a roadmap item, unless the impact is clearly beyond what the roadmap plans for

## Handling

Vulnerabilities are fixed in a private branch, reviewed, and merged with a short advisory in the commit history. Nothing is published before a fix is available.
