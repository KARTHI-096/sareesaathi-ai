# SareeSaathi AI — WhatsApp Sales Assistant MVP

A Streamlit web prototype for an AI-powered conversational sales assistant aimed at local saree vendors.

## Current MVP features

- Customer and vendor role selector
- Chat interface for natural-language product and business questions
- Optional OpenAI API integration
- Safe rule-based demo mode when no API key is configured
- SQLite product catalog and order database
- Product selection, address collection, and demo order booking
- Vendor inventory editing and recent order dashboard
- Explicitly **no real payment processing** and **no WhatsApp integration yet**

## Run locally on Windows

1. Install Python 3.11 or 3.12 if you do not already have a compatible version.
2. Extract this project folder.
3. Open Command Prompt or PowerShell in the folder.
4. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

5. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

6. Start the app:

   ```powershell
   streamlit run app.py
   ```

7. Open the local URL Streamlit prints, usually `http://localhost:8501`.

The app runs in demo mode without an API key.

## Enable OpenAI-powered chat

Create an API key in your OpenAI developer account. API usage may incur charges and is separate from a ChatGPT subscription.

For local testing, set the environment variable in PowerShell (do not commit or share it):

```powershell
$env:OPENAI_API_KEY="your-key-here"
streamlit run app.py
```

Optional model override:

```powershell
$env:OPENAI_MODEL="gpt-4o-mini"
```

Never put your API key in `app.py`, GitHub, screenshots, or public chat messages.

## Deploy to Streamlit Community Cloud

1. Create a new **public GitHub repository**, e.g. `sareesaathi-ai`.
2. Upload `app.py`, `requirements.txt`, `packages.txt`, `.gitignore`, and `README.md` to the repository root. Do not upload `.env`, API keys, or the generated database.
3. Visit https://share.streamlit.io/ and sign in with GitHub.
4. Choose **Create app**, select your repository, branch, and `app.py`.
5. Deploy. Streamlit will provide a public `*.streamlit.app` URL.
6. To enable AI, open the app's **Settings / Secrets** section and add:

   ```toml
   OPENAI_API_KEY = "your-key-here"
   OPENAI_MODEL = "gpt-4o-mini"
   ```

7. Save secrets and reboot/redeploy the app.

### Important database note

The included SQLite database is suitable for a local demo. On free cloud hosting, the local filesystem may be ephemeral and the app may restart with a fresh database. For a persistent, multi-user production app, move data to a managed database such as Supabase/Postgres and add authentication/authorization before storing real customer data.

## Demo checklist

- Try Customer chat: “Show me silk sarees under ₹5,000.”
- Switch to Vendor chat: “How many demo orders are there?”
- Browse the catalog.
- Create a test order using fictional contact details.
- Switch to Vendor and update a product's stock or price.
- Review the order in the Vendor dashboard.

## Roadmap to real WhatsApp commerce

1. Connect WhatsApp Business Platform / Cloud API via a secure backend webhook.
2. Add role verification based on registered vendor and customer phone numbers.
3. Use structured tool/function calls with strict validation for database operations.
4. Add order confirmation before committing orders.
5. Integrate a payment provider in test mode first; never collect UPI PINs, OTPs, or card secrets in chat.
6. Add consent, privacy policy, audit logs, rate limits, and persistent database backups.
7. Test Tamil/English and mixed-language conversations with real users before launch.

This MVP is a portfolio prototype, not a production-ready commerce platform.
