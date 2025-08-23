## Wire ServiceNow to Your App — Quick Guide
# 1) Get a Personal Developer Instance (PDI)

Sign up at the ServiceNow Developer site and Request Instance.

Your instance URL looks like: https://dev331856.service-now.com.

# 2) Create an Integration User

In your PDI: All → User Administration → Users → New.

Create user:

User ID: api.user

Active: ✅

Click Set Password and save a strong password.

Tip: If you want API-only access, you can check Web service access only.

# 3) Grant Permissions

Open api.user → Roles tab → Edit.

Add role itil → Save.

# 4) Sanity Test Inside ServiceNow (No App)

Open REST API Explorer (All → REST API Explorer).

Table API → Create a record (POST) → tableName: incident.

Request Body:

{ "short_description": "ping from API via REST Explorer" }


Auth as current admin (Send as me) or Basic with api.user.

Click Send → expect 201 Created and an INC number.

# 5) Direct Test From PowerShell (No App)
# Use the exact password you set for api.user
$sec  = ConvertTo-SecureString '<YOUR_PASSWORD>' -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential('api.user', $sec)

Invoke-RestMethod -Method Post `
  -Uri "https://dev331856.service-now.com/api/now/table/incident" `
  -Credential $cred `
  -Headers @{ Accept="application/json"; "Content-Type"="application/json" } `
  -Body '{"short_description":"ping from PS basic auth"}'


Expect: 201 Created with result.number like INC00….

# 6) Configure Your App (Environment)

.env

# --- ServiceNow ---
SN_INSTANCE=https://dev331856.service-now.com
SN_AUTH_MODE=basic
SN_USERNAME=api.user
SN_PASSWORD="<YOUR_EXACT_PASSWORD>"   # QUOTE if it has #, ;, spaces, { }

# --- (for later, Teams local test) ---
TEAMS_WEBHOOK_SECRET=local-test-secret-001

# --- App base (optional) ---
YAP_API_URL=http://localhost:8000


Make sure your app loads .env (e.g., python-dotenv: load_dotenv()).

# 7) Start the API With the Env Loaded
uvicorn app.main:app --reload --port 8000


(If you prefer, export the variables in the same shell instead of using .env and then start uvicorn in that shell.)

# 8) App-Level Test (Create Incident via Your API)
$body = @{
  short_description = "Test ticket from YAP local"
  description       = "Outlook crashes opening shared mailbox"
  urgency           = "high"
  impact            = "medium"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/integrations/servicenow/incident `
  -ContentType 'application/json' `
  -Body $body


Expect: JSON with number (e.g., INC0010003), sys_id, and a link.

Troubleshooting (Pocket Guide)

401 Unauthorized (from SN)

Wrong password or app not using new env.

Fix:

Reset password for api.user (User → Set Password).

Ensure Active ✅, Locked out ❌.

In .env, quote passwords with special chars (#, ;, spaces, {}).

Restart uvicorn in the same shell as your env.

403 Forbidden (from SN)

Missing role. Add itil to api.user.

App still sees old env

Restart uvicorn.

Optional debug route:

@app.get("/__sn_debug")
def sn_debug():
    import os
    return {
        "SN_INSTANCE": os.getenv("SN_INSTANCE"),
        "SN_AUTH_MODE": os.getenv("SN_AUTH_MODE"),
        "SN_USERNAME": os.getenv("SN_USERNAME"),
        "has_password": bool(os.getenv("SN_PASSWORD")),
    }


Visit http://localhost:8000/__sn_debug.

Webhook self-call timeout (only when you add Teams)

Running one worker and calling your own endpoint can deadlock.

Fix: run uvicorn app.main:app --port 8000 --workers 2 or call your ServiceNow function directly instead of HTTP self-call.