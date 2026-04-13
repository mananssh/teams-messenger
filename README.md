# teams-messenger

Meeting audio or MS Teams transcript → structured actions pipeline.

Accepts either a raw audio recording (transcribed locally with Whisper) or a Teams `.vtt` transcript file, analyses it with Google Gemini, and dispatches action items to Jira, GitHub, Email, and Teams — each gated behind a feature flag.

**All integrations are free-tier compatible.** No paid services required.

## Architecture

```
audio file (.mp3)              Teams transcript (.vtt)
  │                               │
  ▼                               ▼
┌──────────────────┐    ┌────────────────────┐
│  Whisper (local)  │    │  VTT Parser        │
│  + participants   │    │  (auto-extracts    │
│    .json registry │    │   speakers)        │
└────────┬─────────┘    └────────┬───────────┘
         │                       │
         └───────────┬───────────┘
                     │ transcript + participants
                     ▼
           ┌────────────────────┐
           │  Gemini LLM        │  ← structured output
           └────────┬───────────┘
                    │ MeetingAnalysis (validated)
                    ▼
           ┌────────────────────┐
           │  Dispatcher        │  ← feature-flag gated
           │  ├─ Jira tickets   │  (jira-python + Cloud free tier)
           │  ├─ GitHub issues  │  (httpx + free PAT)
           │  ├─ Email          │  (smtplib + Gmail SMTP)
           │  ├─ Teams chat     │  (MSAL + Graph API)
           │  └─ Manual review  │  (logged for human triage)
           └────────────────────┘
```

## Quick start

### 1. Clone & set up

```bash
git clone <repo-url> && cd teams-messenger
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Note:** Audio mode requires `ffmpeg` on your system.
> macOS: `brew install ffmpeg` · Ubuntu: `apt install ffmpeg`

### 2. Configure

```bash
cp .env.template .env
# Edit .env — set GEMINI_API_KEY at minimum
```

### 3. Run

**Transcript mode** (recommended — uses a Teams `.vtt` export):

```bash
python main.py transcript data/sample_transcript/sample.vtt
```

**Audio mode** (Whisper transcription + external participant list):

```bash
python main.py audio data/input_audio/sample.mp3 --participants data/participants.json
```

**Common options:**

```bash
--meeting-id "sprint-2026-04-13"   # custom ID (auto-generated if omitted)
--log-level DEBUG                   # verbose output
```

## Input modes

### Transcript mode (`transcript`)

Parses an MS Teams `.vtt` (WebVTT) file with speaker voice tags:

```
WEBVTT

00:00:00.000 --> 00:00:05.840
<v Graham Hosking>We need to discuss the Q4 roadmap.</v>
```

Participants are **auto-extracted** from the speaker tags — no separate file needed.

### Audio mode (`audio`)

Transcribes an audio file with OpenAI Whisper (runs locally). Since Whisper output is undiarized (no speaker labels), you must provide a participant registry in Microsoft Graph `attendanceRecords` format:

```bash
python main.py audio meeting.mp3 --participants participants.json
```

## Configuration

All config lives in `.env` (see `.env.template` for the full list).

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `WHISPER_MODEL` | `base` | Whisper model size (audio mode only) |
| `GEMINI_API_KEY` | — | **Required.** Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `GEMINI_TEMPERATURE` | `0.2` | LLM temperature |
| `PROMPT_PATH` | `prompts/system.txt` | System prompt file (relative to project root) |

### Feature flags

| Flag | Required credentials |
|---|---|
| `ENABLE_TEAMS=true` | `MS_CLIENT_ID`, `MS_TENANT_ID` |
| `ENABLE_EMAIL=true` | `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM` |
| `ENABLE_JIRA=true` | `JIRA_SERVER_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` |
| `ENABLE_GITHUB=true` | `GITHUB_TOKEN`, `GITHUB_REPO` |

---

## Integration setup guides

### Microsoft Teams (Graph API — free)

Teams messages are sent as 1:1 chats via the Microsoft Graph API using delegated (user) permissions.

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations → **New registration**
2. Name it (e.g. `teams-messenger`), set Redirect URI to `https://login.microsoftonline.com/common/oauth2/nativeclient`
3. Under **API permissions** → Add → Microsoft Graph → Delegated:
   - `Chat.ReadWrite`
   - `Chat.Create`
   - `User.Read`
   - `User.ReadBasic.All`
4. Grant admin consent if required by your org
5. Copy the **Application (client) ID** and **Directory (tenant) ID** into `.env`:

```env
MS_CLIENT_ID=your-client-id-here
MS_TENANT_ID=your-tenant-id-here
ENABLE_TEAMS=true
```

On first run, you'll be prompted to open a browser and enter a device code. After login, the token is cached locally (`.ms_token_cache.json`) and subsequent runs authenticate silently.

### Email (Gmail SMTP — free, 500/day)

Uses Python's built-in `smtplib` with STARTTLS. Works with Gmail, Outlook, or any SMTP provider.

**Gmail setup:**

1. Enable **2-Step Verification** on your Google Account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate an App Password (select "Mail" / "Other")
4. Add to `.env`:

```env
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=abcd-efgh-ijkl-mnop
EMAIL_FROM=your-email@gmail.com
ENABLE_EMAIL=true
```

**Other SMTP providers:** change `SMTP_HOST` and `SMTP_PORT` accordingly (e.g. Outlook: `smtp-mail.outlook.com:587`).

### Jira Cloud (free tier — up to 10 users)

1. Sign up at [atlassian.com](https://www.atlassian.com/software/jira/free) (free for up to 10 users)
2. Create a project and note the **project key** (e.g. `MEET`)
3. Generate an API token at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
4. Add to `.env`:

```env
JIRA_SERVER_URL=https://yoursite.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=MEET
ENABLE_JIRA=true
```

Issues are created as type "Task" with priority mapped from the LLM output (High/Medium/Low). If the assignee's email matches a Jira user, they are auto-assigned.

### GitHub Issues (free — unlimited)

1. Create a Personal Access Token at [github.com/settings/tokens](https://github.com/settings/tokens)
   - Classic token: select `repo` scope
   - Fine-grained token: select repository → Issues (Read and write)
2. Add to `.env`:

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=owner/repo
ENABLE_GITHUB=true
```

---

## Cost summary

| Integration | Service | Cost | Auth method |
|---|---|---|---|
| MS Teams | Graph API | Free (Azure AD app) | MSAL Device Code |
| Email | Gmail SMTP | Free (500/day) | App Password |
| Jira | Jira Cloud | Free (10 users) | API Token |
| GitHub | GitHub API | Free (unlimited) | PAT |

## Project structure

```
teams-messenger/
├── main.py                           # CLI entrypoint (subcommands: audio, transcript)
├── requirements.txt
├── .env.template
├── prompts/
│   └── system.txt                    # Externalized LLM system prompt
├── data/
│   ├── input_audio/sample.mp3        # Sample audio for audio mode
│   ├── sample_transcript/sample.vtt  # Sample VTT for transcript mode
│   └── participants.json             # Sample participant registry
└── app/
    ├── config.py                     # Pydantic Settings
    ├── models.py                     # Pydantic data models + action type labels
    ├── pipeline.py                   # Mode-agnostic pipeline orchestrator
    ├── auth/
    │   └── graph_auth.py             # MSAL Device Code Flow + Graph helpers
    ├── transcription/
    │   ├── whisper_service.py        # Local Whisper transcription
    │   └── vtt_parser.py            # MS Teams VTT parser
    ├── llm/
    │   ├── gemini_service.py         # Gemini API (structured output)
    │   └── prompt_template.py        # Prompt loader
    ├── parser/
    │   └── json_parser.py            # JSON fallback parser
    └── dispatcher/
        ├── dispatcher.py             # Routes by action_type
        ├── teams_service.py          # Graph API 1:1 chat messages
        ├── email_service.py          # smtplib + Gmail SMTP
        ├── jira_service.py           # jira-python + Cloud API
        └── github_service.py         # httpx + GitHub Issues API
```
