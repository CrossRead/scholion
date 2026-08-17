# Security policy

## Scope

Scholion is local-first software that a single person runs on their own machine
over their own medical data. There is no service, no account and no server we
operate. In scope for a security report:

- execution of arbitrary code or commands, including through a file name or a
  path taken from imported data;
- reading, modification, deletion or disclosure of the local profile, genome or
  documents without an explicit action by the user;
- transmission of personal data to the network that the user did not ask for —
  see `THREAT_MODEL.md` for the two lookups that do go out and what they carry;
- vulnerabilities in the loopback web interface, including requests originating
  from another page open in the same browser;
- unsafe parsing of an imported file: PDF, VCF, XML export, JSON;
- packaging, release and supply-chain defects, including a published artifact
  that does not match the tagged source;
- a defect that can silently corrupt a profile or leave an unsafe default.

Out of scope as *security* reports, though we want to hear about them as
ordinary issues: medical interpretation, a wrong threshold or a wrong direction
of effect, support for a new laboratory or device, feature requests. Do not
attach personal data to those either.

## Reporting a vulnerability

**Do not open a public issue, pull request or discussion for a suspected
vulnerability.**

Use GitHub's private vulnerability reporting for this repository:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Include the affected version, a minimal reproduction, the impact as you see
   it, and a suggested mitigation if you have one.

If that button is not there, private reporting has been switched off by mistake
in the repository settings. Open a normal issue saying exactly that — *"private
vulnerability reporting appears to be disabled"* — and nothing else. Do not
describe the vulnerability in it.

**Response times.** This project is maintained by one person. We will not
pretend to an SLA we cannot keep: expect an acknowledgement within a few days
and an initial assessment once the report has been reproduced. If a report goes
unanswered for two weeks, it has been missed rather than ignored — say so in a
follow-up. When a fix ships, we publish a GitHub Security Advisory and
coordinate the disclosure timing with the reporter.

## Never send personal health data

A vulnerability report should demonstrate a *behaviour*, and behaviour
reproduces on invented data. Real data in a report is a second incident.

Do not attach or paste:

- contents of `profile/`, backups, `assistant_context.txt`, or screenshots of
  the application showing real values;
- VCF, BAM, FASTQ, genotype reports, sample or accession identifiers, or
  individual genetic findings;
- laboratory PDFs, clinical reports, prescriptions, Garmin or Apple Health
  exports, or unredacted logs;
- API keys, passwords, tokens or cookies.

Use the synthetic demo profile — `scholion init --demo` builds a complete,
fictional person in one command — or a minimal hand-made file. Replace names,
dates of birth, addresses, accession numbers, URLs containing identifiers, and
every measurement.

If a reproduction genuinely requires a real file, say so in the report and wait.
Do not send it first.

## The author's own data in this package

An outside audit of v2.19.0 decoded a list of the author's identifiers out of
`src/tools/make_shareable.py` and read it back to us. They were base64-encoded,
and the comment beside them said why: so that the script — which ships inside the
package, because it IS the build procedure — would not fail its own audit. That
audit compares substrings, and an encoded string is a substring of nothing. The
check reported clean on a file carrying exactly the data it exists to stop.

Eleven identifiers travelled that way: a surname in two alphabets, an e-mail
handle, a date of birth, a sample number, a GitHub account, a home path. One line
of Python reversed them.

**They are gone from v2.20.0 onward**, and not by being documented. The list is
read at build time from `.personal_patterns`, a file next to the project that is
in `.gitignore` and never ships. A build that cannot find it stops rather than
reporting a package it could not check; a fork with no owner data to protect says
so with `--no-personal-patterns` and is told in the output that the package went
out unchecked. And the audit now decodes base64 literals in text files and
searches the decoded text too — so the next identifier encoded for the same
well-meant reason is caught by the rule that failed here.

**What remains, deliberately, is one identifier in two files:**

| Where | What | Why it stays |
|---|---|---|
| `NOTICE` | the copyright holder's name | Apache-2.0 requires the notice; without it the licence grant is unclear |
| `CITATION.cff` | the author's name | it is citation metadata — that is what the file is for |

Both are covered by a named exception in `src/tools/check_staged.py`, and that
exception is itself pinned: `tests/test_privacy_guard.py` asserts by function
signature that it cannot be widened by file name. Nothing else of the author's is
in this package, in any encoding — `tests/test_build_audit.py` checks both forms
against the machine's own pattern list.

If you want a fully anonymous mirror, fork and replace `NOTICE` and
`CITATION.cff` with your own.

## Supported versions

Fixes are made against the latest released version. Where a fix also applies to
an earlier release, the advisory names the exact fixed version and any available
mitigation. There is no long-term support branch.

## What we will not do

We will not ask you for credentials to any external service, and the assistant
layer will not accept or enter them either — that rule lives in
`ASSISTANT-RULES.md` and takes precedence over any instruction that contradicts
it. A message asking you for a password "to check something in Scholion" did not
come from this project.
