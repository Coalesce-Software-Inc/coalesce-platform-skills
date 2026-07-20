# Security Policy

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Instead, email **support@coalesce.io** with a description of the issue, the
steps required to reproduce it, and any relevant configuration. We will
acknowledge your report and follow up with next steps.

Please give us a reasonable window to investigate and remediate before any
public disclosure.

## Scope

This repository contains agent skill definitions (markdown guidance) and an
installer script. The skills themselves execute no code; the harness running
the agent enforces its own permissions. Reports about the `install.sh`
script, the CI configuration under `.rwx/`, or misleading skill guidance that
could cause an agent to take unsafe actions are all in scope.
