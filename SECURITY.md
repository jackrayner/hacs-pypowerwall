# Security Policy

`hacs-pypowerwall` is a small, solo-maintained hobby project. This policy is deliberately lightweight — there's no security team, no SLA, and no bug bounty, just one maintainer doing their best.

## Reporting a vulnerability

Please report security issues privately using GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability): go to this repo's **Security** tab and click **Report a vulnerability**. This is the preferred and only channel for reports — there's no monitored security email address for this project, so please don't send one.

You should get a response within a few days, but given this is a one-person project in spare time, there's no guaranteed turnaround.

## Supported versions

Only the latest release gets security fixes. There are no LTS branches and no backports — if a fix ships, it ships in the next release, and upgrading is the only way to get it.

## Scope

In scope: vulnerabilities in this repo's own code, i.e. the Home Assistant integration under `custom_components/pypowerwall/`.

Out of scope: the [`pypowerwall`](https://github.com/jasonacox/pypowerwall) PyPI package this integration depends on for actually talking to a Tesla Powerwall gateway. That's a separate project with its own maintainer — vulnerabilities in how it communicates with the gateway or Tesla's cloud should be reported there, not here.
