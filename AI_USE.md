# AI Use Disclosure
## SceneForge AI — IncuBrix SEA PS3

This document discloses all AI assistant usage, model services, and AI-generated or
AI-assisted code contributions to this project, as required by the assessment brief.

> **Last Updated**: Phase 1
> **To be updated**: After each phase as AI assistance is used.

---

## 1. AI Assistants Used

| Tool | Provider | Role |
|---|---|---|
| Kiro IDE (AI assistant) | Amazon / AWS | Initial architecture design, base code generation, Phase 1-5 planning |
| Google Antigravity (Pair Programming Assistant) | Google DeepMind | Phase 6-7 genuine Pixabay retrieval, dark-themed studio frontend, OpenAPI 3.1, hard-case fixes, test expansion to 500 tests |

---

## 2. What Was AI-Generated

### Phase 1 (Planning)

The following documents were drafted with AI assistance and reviewed by the author:

| Document | AI contribution | Human review |
|---|---|---|
| `docs/requirements_traceability.md` | Full initial draft, structure, requirement extraction from prompt | Reviewed for accuracy; gaps identified and registered |
| `docs/architecture.md` | Full initial draft of module design, data structures, DB schema, security design | Reviewed against assessment requirements; validated for consistency |
| `docs/implementation_plan.md` | Full initial draft of phase plan, task lists, risk register | Reviewed and adjusted for realistic scope |
| `README.md` | Full initial draft | Reviewed for accuracy; placeholders identified |
| `REPORT.md` | Full initial draft skeleton | Reviewed; content sections to be filled with real data |
| `SOURCES.md` | Full initial draft | Reviewed; licence notes verified |
| `AI_USE.md` | This document | Reviewed |

### Phases 2–7

> _To be completed as each phase is implemented._

For each phase, this section will record:
- Which files were AI-generated, AI-assisted, or written entirely by the author.
- Which AI-generated code was reviewed, tested, and modified.
- Which tests were written by the author independently.

---

## 3. What Was Reviewed and Changed

All AI-generated documents and code in this project were reviewed by the author before
being committed. The review process includes:

1. Reading every generated file and checking it against the assessment requirements.
2. Identifying gaps, inaccuracies, and missing edge cases.
3. Correcting or extending generated content where needed.
4. Running all generated tests to verify they actually pass.
5. Registering honest failures rather than suppressing them.

Generated code that was not understood by the author was not accepted without modification.

---

## 4. What Was Tested

All AI-generated code is subject to the same test requirements as author-written code:

- Unit tests must pass without external API keys.
- Integration tests must pass against Dockerised services.
- Hard-case tests must produce honest results (failures preserved, not hidden).
- No test result is fabricated or suppressed.

---

## 5. AI-Generated Media and Assets

No AI-generated images, audio, or video are included in the test fixtures or repository.
All test fixtures are either:
- Synthetically generated using FFmpeg command-line tools (silence, tones, cards).
- Short original text scripts written specifically for this project.

If AI-generated media is used in a demo run (e.g. via a generative image provider), it
will be recorded in `rights.json` with `asset_type: "generated"` and the model/provider
provenance noted.

---

## 6. AI-Generated Data and Statistics

No AI-generated statistics, testimonials, benchmarks, or performance numbers are claimed
in this project. All metrics reported in `metrics.json`, `REPORT.md`, and the traceability
matrix reflect actual measured values from real test runs.

Where a metric cannot be measured, it is reported as unavailable with a reason — never
fabricated.

---

## 7. Limitations of AI Assistance

- AI-generated architecture documents reflect the prompt requirements and general best
  practices but may not anticipate all runtime constraints specific to the assessment
  environment.
- AI-generated test cases cover the scenarios described in the prompt; additional edge
  cases discovered during implementation are added by the author.
- AI assistance does not substitute for the author's engineering judgement on security,
  licence compatibility, or correctness of media rights claims.
