# Security policy

Please do not open a public issue for a security problem.

Report it privately through GitHub: open the **Security** tab of this repository and choose
**Report a vulnerability** (GitHub private security advisories). Include the affected version,
the steps to reproduce and the impact you observed. You should get a first answer within a week.

This tool handles API keys. It reads them from environment variables only, never writes them to
disk, to the database, to `latest.json` or to the report, and sends each key only to the provider
that issued it.
