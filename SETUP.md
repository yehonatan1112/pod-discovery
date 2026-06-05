# Setup Guide

One-time setup. Takes about 20 minutes.

---

## Step 1 — Create a GitHub repository

1. Go to https://github.com/new
2. Name it something like `podcast-bot`
3. Set visibility to **Public** (required for free unlimited Actions minutes)
4. Click **Create repository**
5. Upload everything in this folder to the repo (drag-and-drop works in the GitHub UI, or use `git push`)

---

## Step 2 — Create a Telegram Bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts — give it a name and username (e.g. `MyPodcastBot`)
4. BotFather will give you a **token** that looks like `123456789:ABCdef...`
5. Save that token — you'll need it in Step 4

**Get your personal chat ID:**
1. Search for **@userinfobot** on Telegram
2. Send it any message — it replies with your Chat ID (a number like `123456789`)
3. Save that number

---

## Step 3 — Set up Cloudflare R2 (for archive downloads)

1. Go to https://dash.cloudflare.com → **R2 Object Storage**
2. Click **Create bucket**, name it `podcast-archives` (or anything)
3. Open the bucket → **Settings** → **Public access** → enable **Allow Access**
4. Note your **Public bucket URL** (looks like `https://pub-xxxx.r2.dev`)

**Create API credentials:**
1. In R2, click **Manage R2 API Tokens** → **Create API Token**
2. Give it **Object Read & Write** permission for your bucket
3. Save the **Access Key ID** and **Secret Access Key**

**Find your endpoint URL:**
- Format: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
- Your Account ID is in the Cloudflare dashboard URL or under **R2 → Overview**

---

## Step 4 — Add secrets to GitHub

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets one by one:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The token from BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID from @userinfobot |
| `R2_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID` | From Step 3 |
| `R2_SECRET_ACCESS_KEY` | From Step 3 |
| `R2_BUCKET` | `podcast-archives` (or whatever you named it) |
| `R2_PUBLIC_URL` | `https://pub-xxxx.r2.dev` from Step 3 |

---

## Step 5 — Start the bot

1. Open your Telegram app
2. Search for your bot by its username
3. Press **Start** (or send `/start`)
4. The bot will respond within 5 minutes (that's how often it polls)

---

## Step 6 — Test the digest (optional)

To send a test digest immediately without waiting for the schedule:

1. Go to your GitHub repo → **Actions** tab
2. Click **Send Digest** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Check Telegram in a few seconds

---

## How it works (summary)

| What | When | How |
|---|---|---|
| Digest | Sun–Wed + Sat at 20:00 IL | GitHub Actions cron |
| Bot polls for your commands | Every 5 minutes | GitHub Actions cron |
| Archive creation | When you send `/archive` | GitHub Actions workflow_dispatch |

**Commands you can send to the bot:**
- `/latest` — most recent episode from each podcast
- `/status` — system status
- `/archive` — download all episodes from last digest (per-podcast format defaults)
- `/archive audio` — force MP3 for everything
- `/archive video` — force video for everything
- `/add <name> <url> [audio|video]` — add a new podcast

**Adding a podcast example:**
```
/add הפודקאסט החדש https://youtube.com/playlist?list=PLxxxxxx audio
```

---

## Archive setup (cleanup)

Archives are stored in R2. You should set a lifecycle rule to auto-delete them after a few days:

1. In R2, open your bucket → **Settings** → **Object lifecycle rules**
2. Add a rule: delete objects with prefix `archives/` after **3 days**

This keeps storage costs at zero.

---

## Troubleshooting

**Bot not responding?**
- Check the **Actions** tab in GitHub — look for failed `Bot Polling` runs
- Make sure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets are set correctly

**Digest not sending?**
- Check the **Actions** tab → **Send Digest** run logs
- Make sure the playlist URLs in `podcasts.yaml` are correct

**Archive failing?**
- Check the **Actions** tab → **Create Archive** run logs
- R2 credentials are the most common issue — double-check the endpoint URL format

**Wrong episodes in digest?**
- The digest shows episodes published within the time window, based on YouTube's upload date
- If a podcast uploads late (e.g. publishes Friday but shows Tuesday's date), it may appear in a different digest
