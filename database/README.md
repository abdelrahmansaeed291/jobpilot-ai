# Supabase setup

1. Create a free Supabase project.
2. Open **SQL Editor** in the Supabase dashboard.
3. Paste and run `migrations/001_candidate_profile.sql` once.
4. Paste and run `migrations/002_extra_information_preferences.sql` once.
5. Paste and run `migrations/003_saved_jobs.sql` once.
6. In **Project Settings > API**, copy the project URL and service-role key into
   the local `jobpilot-ai/.env` file:

   ```dotenv
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   ```

7. Restart Streamlit after changing `.env`.

The service-role key is appropriate here only because JobPilot AI is a personal,
server-side Streamlit application. It bypasses Row Level Security and must never be
committed, printed, placed in browser code, or shared. The migration intentionally
creates no public policies. Add Supabase Auth and user-scoped RLS policies before
making a deployed application available to other users.

The application uses the fixed profile ID
`00000000-0000-0000-0000-000000000001`. Uploading another CV replaces the object
at the same private Storage path and updates this row.
