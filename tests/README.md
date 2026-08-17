# Tests

```bash
./run_tests.sh
```

Standard library, no dependencies. A run takes about 20 seconds.

The tests work on a synthetic profile in `tests/fixtures/profile` — invented
values, chosen so that the checks fire. They neither read nor modify the user's
own profile: `SCHOLION_PROFILE_DIR` is overridden unconditionally, and commands
that write are exercised against a copy of the fixture in a temporary
directory.

| File | About |
|---|---|
| `test_parity.py` | everything the web can do, the command line can do too |
| `test_cli_smoke.py` | every command answers; on an empty profile as well |
| `test_safety_rules.py` | no interval → no flag; PhenoAge only on a complete panel; sex does not affect the formula |
| `test_math.py` | the n-of-1 sensitivity boundary, the permutation test, accounting for protocol violations |
| `test_compat.py` | the public contract has not narrowed |
| `test_privacy_guard.py` | the exception for the copyright line — and for it alone |
| `test_licensing.py` | the legal files are in place, the paths are real, the verbatim notices have not been lost |
| `test_demo_profile.py` | the demo works on every reading command and is signed as synthetic |
| `test_skill_editions.py` | personal data does not leak into the shared edition of the skill |

Details, and what to do when something fails — `docs/TESTS-AND-COMPATIBILITY.md`.
