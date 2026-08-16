# JobPilot AI

JobPilot AI is a personal, agentic job-search and job-application assistant. This
first project step provides the modular Python foundation and Streamlit navigation;
AI workflows, integrations, persistence, and application features are intentionally
not implemented yet.

## Pages

- Dashboard
- My Profile
- Extra Information
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
