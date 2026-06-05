# Setup Guide

One-time setup. Takes about 10 minutes.

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
5. Save that token

**Get your personal chat ID:**
1. Search for **@userinfobot** on Telegram
2. Send it any message — it replies with your Chat ID (a number like `123456789`)
3. Save that number

---

## Step 3 — Add secrets to GitHub

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The token from BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID from @userinfobot |

That's it. No storage accounts, no API keys, nothing else.

---

## Step 4 — Start the bot

1. Open Telegram and find your bot by its username
2. Press **Start** (or send `/start`)
3. The bot will respond within 5 minutes

---

## Step 5 — Test the digest (optional)

To send a test digest immediately without waiting for the schedule:

1. Go to your GitHub repo → **Actions** tab
2. Click **Send Digest** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Check Telegram in a few seconds

---

## How it works

| What | When |
|---|---|
| Digest sent | Sun, Mon, Tue, Wed, Sat at 20:00 Israel time |
| Bot checks for your commands | Every 5 minutes |
| Archive created | When you send `/archive` (takes a few minutes) |

Archive download links are hosted on [transfer.sh](https://transfer.sh) — no account needed, links expire automatically after 48 hours.

---

## Commands

Send these to your bot in Telegram:

| Command | What it does |
|---|---|
| `/latest` | Most recent episode from each podcast |
| `/status` | Active podcast count + current digest window |
| `/archive` | Download all episodes from the last digest (each podcast uses its own default format) |
| `/archive audio` | Same but force MP3 for everything |
| `/archive video` | Same but force video for everything |
| `/add <name> <url> [audio\|video]` | Add a new podcast |
| `/help` | Show this list |

**Adding a podcast example:**
```
/add הפודקאסט החדש https://youtube.com/playlist?list=PLxxxxxx audio
```

---

## Troubleshooting

**Bot not responding?**
- Check **Actions** tab in GitHub → look for failed `Bot Polling` runs
- Make sure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set correctly in Secrets
- The bot only responds to your chat ID — it ignores everyone else

**Digest not sending?**
- Check **Actions** tab → **Send Digest** run logs
- Trigger it manually from the Actions tab to test

**Archive failing?**
- Check **Actions** tab → **Create Archive** run logs
- Large video archives can take 30–60 minutes — this is normal
