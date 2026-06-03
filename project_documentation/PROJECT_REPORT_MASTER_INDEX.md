# IIAP OM — Master Report Index (100-Page Documentation Set)

## How to Read This Documentation

This is the **complete documentation package** for the IIAP OM platform. Together, the files below contain **narrative chapters**, **diagrams**, **flowcharts**, **URL encyclopedias**, **per-function logic**, and **operational runbooks**—designed to print as approximately **100 pages** (PDF/DOCX).

---

## Document Files (Read in Order)

| # | File | Content | Approx. pages* |
|---|------|---------|----------------|
| 1 | [PROJECT_REPORT_MASTER_PART1.md](./PROJECT_REPORT_MASTER_PART1.md) | Chapters I–V: Intro, Core, Accounts, PM Core, Tasks | ~35 |
| 2 | [PROJECT_REPORT_MASTER_PART2.md](./PROJECT_REPORT_MASTER_PART2.md) | Chapters VI–XIV: Bugs, QA, KB, Files, Finance, Calendar, Notifications, Chat, Telescope | ~35 |
| 3 | [PROJECT_REPORT_MASTER_PART3.md](./PROJECT_REPORT_MASTER_PART3.md) | Chapters XV–XXI: Inventory, Media, Architecture, Security, Testing, Glossary | ~30 |
| 4 | [PROJECT_REPORT.md](./PROJECT_REPORT.md) | Structured reference (v2.0): URLs, forms, templates, model tables | ~45 |
| 5 | [PROJECT_REPORT_CODE_ENCYCLOPEDIA.md](./PROJECT_REPORT_CODE_ENCYCLOPEDIA.md) | Per-file pseudocode, signals, WebSocket protocol, quirks | ~25 |
| 6 | **[COMPLETE_FEATURE_CATALOG.md](./COMPLETE_FEATURE_CATALOG.md)** | **390 features** — every mini feature with ID, URL, access | ~55 |

\*At 11pt, ~45 lines/page — **combined set ≈ 120–140 printed pages**.

## Feature Catalog Quick Stats

- **390** numbered features (F-001 through F-390)
- Includes: login themes, Kanban counters, PDF annotations, dual-delete, Gemini AI, trash filters, inventory Excel bulk, telescope seed, template tags, and 29 “hidden” system mini-features (Part S)

---

## Quick Links by Topic

| Topic | Primary chapter |
|-------|-----------------|
| Login & roles | Part 1, Chapter III |
| Projects & releases | Part 1, Chapters IV–V |
| Test-gated tasks | Part 1, Chapter V; Part 2, Chapter VII |
| Files & versioning | Part 2, Chapter IX |
| Real-time chat | Part 2, Chapter XIII |
| Inventory stock formula | Part 3, Chapter XV |
| Security checklist | Part 3, Chapter XVIII |
| All URL routes | PROJECT_REPORT.md §7 |
| Function-level logic | CODE_ENCYCLOPEDIA |

---

## Generate Single PDF (All Parts)

```bash
cd "/media/Data/Saran Projects/IIA Management/project_documentation"

# Option A: PDF (requires texlive-xetex)
pandoc PROJECT_REPORT_MASTER_PART1.md \
      PROJECT_REPORT_MASTER_PART2.md \
      PROJECT_REPORT_MASTER_PART3.md \
      PROJECT_REPORT.md \
      PROJECT_REPORT_CODE_ENCYCLOPEDIA.md \
      COMPLETE_FEATURE_CATALOG.md \
      -o IIAP_PM_Complete_Report.pdf \
      --pdf-engine=xelatex \
      -V geometry:margin=1in \
      -V fontsize=11pt \
      --toc --toc-depth=3 \
      --metadata title="IIAP OM Master Technical Report"

# Option B: Word (no LaTeX required)
pandoc PROJECT_REPORT_MASTER_PART1.md \
      PROJECT_REPORT_MASTER_PART2.md \
      PROJECT_REPORT_MASTER_PART3.md \
      PROJECT_REPORT.md \
      PROJECT_REPORT_CODE_ENCYCLOPEDIA.md \
      COMPLETE_FEATURE_CATALOG.md \
      -o IIAP_PM_Complete_Report.docx \
      --toc --toc-depth=3
```

---

## Chapter Map (All 21 Chapters)

| Ch. | Title | File |
|-----|-------|------|
| I | Introduction & Executive Narrative | Part 1 |
| II | Core Platform | Part 1 |
| III | Accounts & Identity | Part 1 |
| IV | Project Management Core | Part 1 |
| V | Task Execution | Part 1 |
| VI | Bug Tracking | Part 2 |
| VII | Test Case Management | Part 2 |
| VIII | Knowledge Base | Part 2 |
| IX | File & Document Management | Part 2 |
| X | Finance | Part 2 |
| XI | Calendar & Events | Part 2 |
| XII | Notifications | Part 2 |
| XIII | Real-Time Chat | Part 2 |
| XIV | Telescope Operations | Part 2 |
| XV | Inventory & Supply Chain | Part 3 |
| XVI | Media & Static Assets | Part 3 |
| XVII | System Architecture & Integration | Part 3 |
| XVIII | Security, Compliance & Operations | Part 3 |
| XIX | Testing & Quality Assurance | Part 3 |
| XX | Glossary & Acronyms | Part 3 |
| XXI | Appendices | Part 3 |

---

*IIAP OM Master Documentation — Version 3.0 — May 2026*
