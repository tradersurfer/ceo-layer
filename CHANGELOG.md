# Changelog

## 0.3.0
- NEW `ceo_verify` tool: the Verify step of Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log now exists in code. A call that started is not a call that completed.
- Secret scanning covers nested keys AND values (JWTs, `sb_secret_`, `sk-`, GitHub, AWS, Slack, private-key blocks). Errors name the path, never the value.
- `ceo_assign` is validated: required fields, ISO `YYYY-MM-DD` due date, known seat (Hermes = COO).
- Retry rule is now code (`next_action`): one retry, never blind on state-changing tools.
- Type 1 now covers security, people, regulatory, reputation, and outside-authority, matching the docs.
- Plan no longer gates every call by default (Type 1 stops, Type 2 proceeds) and only adds the Q4 checklist for Q4 / year-end goals.
- JSON-string arguments are parsed instead of rejected.
- Tests (34) and a deterministic demo script added.
