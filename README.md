# HCL Intern Nexus

HCL Intern Nexus is a Streamlit-based internship learning portal for students, mentors, and administrators. It combines learning plans, mentor communication, meetings, resource discovery, formula management, AI assistance, and performance reporting in one workspace.

## Features

### Student workspace

- Personalized student dashboard with internship progress and days remaining.
- AI-generated learning plans using Groq.
- Learning checklist and progress tracking.
- Private mentor chat for doubts, absence messages, and meeting problems.
- Notifications and mentor notices in a dedicated tab.
- Formula Vault with built-in formulas plus persistent custom formulas.
- Searchable learning resources with YouTube videos and educational articles.
- In-page selected-video playback using the official YouTube embed player.
- Saved resources and recently searched topics.
- Meeting joining, recording, automatic transcription, Roman-English Hindi normalization, and summaries.
- PDF upload and retrieval-augmented Helping Bot.

### Mentor workspace

- Student list and student-specific activity analytics.
- Seven-day activity chart, learning-plan count, and activity progress.
- Typed reports and handwritten PDF attachments for individual students.
- Weekly and monthly Groq performance reports.
- Downloadable PDF performance reports with report history.
- Meeting scheduling, 12-hour time selection, student email lookup, link editing, and in-page joining.
- Private one-to-one chat with assigned students.
- AI-assisted notice formatting, publishing, editing, and deletion.
- Mentor-curated YouTube and blog resources with add, edit, and delete controls.

### Administrator workspace

- User and role management.
- System-level dashboard statistics.
- Notice visibility and administration.
- Account deletion request handling.

## Architecture

```text
app.py
├── authentication.py
├── dashboards/
│   ├── student/
│   ├── mentor/
│   ├── admin/
│   └── shared_messages.py
├── ai/
│   ├── learning_agent.py
│   ├── mentor_agent.py
│   ├── newsletter_agent.py
│   ├── performance_agent.py
│   └── chains.py
└── database/
    ├── connection.py
    ├── users.py
    ├── learning.py
    ├── meetings.py
    ├── messages.py
    ├── resources.py
    └── reports.py
```

The application uses Streamlit for the interface, SQLite for persistence, Groq for AI tasks, LangChain runnables for workflow pipelines, and ReportLab for generated PDF reports.

## LangChain middleware

The performance-report workflow uses a middleware-traced LangChain `RunnableSequence`:

```text
Collect student signals
	↓
Analyze with Groq
	↓
Render PDF report
	↓
Save report history
```

Each step records its status, duration, and failure details. The Student Dashboard also traces notice loading and each major tab render.

## Requirements

- Python 3.11 or newer
- A Groq API key for AI features
- Network access for Groq and DuckDuckGo resource searches
- A Teams meeting link if embedded meetings are required

## Local setup

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/ayeshamehreentech/HCL_INTERN_NEXUS.git
cd HCL_INTERN_NEXUS
```

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file from this template. Never commit real credentials:

```env
GROQ_API_KEY=replace-with-your-groq-key
GROQ_MODEL=openai/gpt-oss-120b
WEATHERMAP_API_KEY=replace-with-your-weather-key
TEAMS_MEETING_LINK=https://example.com/meeting-link
INTERNSHIP_TITLE=Gen AI Internship
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=replace-with-a-strong-password
MENTOR_EMAIL=mentor@example.com
```

Start the application:

```powershell
streamlit run app.py
```

Then open the local URL shown by Streamlit, normally `http://localhost:8501`.

## Resource search

The Resources tab does not require a YouTube API key. It uses server-side DuckDuckGo search to discover YouTube watch URLs and educational articles. YouTube videos are displayed through the official embedded player, and the selected video remains selected until the user chooses another one.

Mentors can add trusted resources directly from the Mentor Resources page. These curated resources are merged with search results for the matching topic.

## Data storage

SQLite tables are initialized automatically on application startup. The database stores:

- Users and roles
- Internship activity
- Meetings and transcripts
- Notices
- Learning plans and checklists
- Mentor/student private messages
- Mentor resources and student resource history
- Custom formulas
- Student reports and generated PDF data

Local database files are ignored by Git. Production deployments should use a managed database if data must persist across ephemeral cloud instances.

## Streamlit Community Cloud deployment

1. Push the project to GitHub.
2. Open [Streamlit Community Cloud](https://share.streamlit.io).
3. Select `ayeshamehreentech/HCL_INTERN_NEXUS`.
4. Choose branch `main`.
5. Set the main file to `app.py`.
6. Add the environment values from the `.env` template in the deployment secrets configuration.
7. Deploy the application.

Do not upload `.env`, SQLite databases, virtual environments, or API keys to GitHub. Rotate any credential that has been exposed in chat, screenshots, logs, or commits.

## Validation

Useful local checks:

```powershell
python -m py_compile app.py
python -m py_compile dashboards\student\dashboard.py dashboards\mentor\dashboard.py
```

The application initializes its SQLite schema automatically, so a fresh environment can start without a separate migration command.

## License

Add the project's chosen license before distributing the application publicly.

## YouTube learning resources

The Student **Resources** tab is a focused in-app learning flow:

1. Search a topic. DuckDuckGo is used first to discover regular YouTube tutorials; Shorts are excluded.
2. Results are shown in a horizontal carousel. Selecting **Play in app** keeps the YouTube player inside HCL Intern Nexus.
3. Students can save a lesson, record a resume position, mark it complete, and continue with suggested lessons.
4. Mentor-published YouTube resources appear under **Mentor Suggested**.
5. A playlist URL or ID can be loaded directly into the same learning carousel.

### Streamlit secrets

Add this in Streamlit Cloud **Settings → Secrets** to enable playlist metadata (video titles, channels, and thumbnails):

```toml
YOUTUBE_API_KEY = "your-youtube-data-api-key"
```

Never commit API keys to the repository. The `google-api-python-client` dependency is included in `requirements.txt`.

## SQLite compatibility

The app accepts both the current user schema and an older SQLite schema that uses a `password` field instead of `password_hash`. Existing user records remain readable after deployment.
