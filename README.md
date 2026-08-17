# JobPilot AI

JobPilot AI is a personal, agentic job-search and job-application assistant. This
first project step provides the modular Python foundation and Streamlit navigation;
The project now includes persistent candidate profiles and CV storage through
Supabase. Other AI workflows and application features remain intentionally deferred.

## Pages

- Dashboard
- My Profile
- CV & Extra Information
- Job Preferences
- Find Jobs
- Analyze Job
- Application Assistant
- Interview Preparation
- My Applications

## Architecture

```text
jobpilot-ai/
├── app.py                 # Streamlit entry point
├── pages/                 # Page-level UI renderers
├── components/            # Shared UI and navigation components
├── agents/                # Future LangGraph workflows
├── services/              # Future business logic and external integrations
├── models/                # Future Pydantic domain models
├── database/              # Future Supabase persistence layer
├── utils/                 # Configuration and shared helpers
├── prompts/               # Future versioned prompt templates
├── tests/                 # Automated tests
├── requirements.txt
└── .env.example
```

The UI layer calls services, services use domain models and repositories, and agents
coordinate services. Database and provider-specific code should not be imported
directly by page modules. This keeps the UI replaceable and makes non-UI behavior
straightforward to test.

## Persistent candidate profile

The **My Profile** page is a polished, read-only portfolio built from CV and manual
candidate data. All changes live in **CV & Extra Information**, where uploading or
replacing a CV explicitly runs this workflow:

```text
PDF bytes -> PyMuPDF text -> structured extractor -> private Storage -> profile row
```

The stored CV is never downloaded or reparsed during application startup. When
`GEMINI_API_KEY` is configured, Gemini 3.5 Flash-Lite produces schema-constrained
JSON that is validated with Pydantic before persistence. Provider failures fall back
to the conservative local extractor with a visible warning. Extracted fields can be
reviewed, corrected, and saved from the same editing workspace.

Apply [database/migrations/001_candidate_profile.sql](database/migrations/001_candidate_profile.sql)
using the instructions in [database/README.md](database/README.md) before using the
page.

## Candidate context and deterministic matching

Run `database/migrations/002_extra_information_preferences.sql` to enable the
**CV & Extra Information** and **Job Preferences** pages. These pages persist editable
JSONB data and feed `build_normalized_candidate_profile`, which combines CV data,
manual context, and preferences into one agent-ready CandidateProfile subclass.

The **Analyze Job** page uses Gemini structured output to create a validated
`JobProfile`, displays it for review, and then runs a separate deterministic matcher.
The fixed score weights are 40% required skills, 15% preferred skills, 20% relevant
experience, 10% education, 5% languages, 5% responsibility similarity, and 5%
preferences. SentenceTransformers supports semantic comparison, but no LLM can set
or alter the percentage.

## Public job discovery

The **Find Jobs** page executes the nine LinkedIn-focused searches defined in
`config/job_searches.json`: six for Germany and three for Egypt, all restricted to the
past 24 hours. Tavily searches LinkedIn's public index; JobPilot does not log in to or
directly scrape LinkedIn. Each result must independently prove that it is in the
configured country and was posted no more than 24 hours ago; ambiguous locations and
unknown dates are rejected. Every eligible result is displayed with no relevance,
match-score, preference, or semantic filtering. Jobs are deduplicated by LinkedIn job
ID, falling back to company + title + location, ordered newest first, and displayed in
separate country tabs. Identical collections are cached for 30 minutes to conserve
free-tier credits.

Set `TAVILY_API_KEY` in `.env` to enable discovery. To use the **Save** action, run
`database/migrations/003_saved_jobs.sql` in the Supabase SQL Editor.

## LangGraph workflow

`agents/job_application_graph.py` defines a serializable `JobAgentState` and nodes for
profile loading, job analysis, deterministic matching, company research, application
writing, factual criticism, and interview preparation. A score below the configured
threshold ends early. Accepted jobs continue through a bounded writer/critic loop,
with optional interview routing. Deterministic profile and scoring work remains normal
Python; injectable provider boundaries handle optional AI work. Every executed node is
recorded in `execution_log` and logged to the local terminal at INFO level.

## Local setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add credentials only when a feature needs
   them. The current placeholder application starts without any API keys.

4. Run the application:

   ```powershell
   streamlit run app.py
   ```

5. Run the tests:

   ```powershell
   pytest
   ```

## Cost boundary

The planned stack uses open-source Python packages and services that offer free
tiers. Future integrations should enforce usage limits and keep paid features
opt-in so normal personal use does not create charges. Free-tier limits and terms
can change, so verify each provider's current terms before enabling an integration.

## Secrets

Local credentials belong in `.env`, which is ignored by Git. `.env.example` lists
the expected variable names without values. Never put credentials in source files.
