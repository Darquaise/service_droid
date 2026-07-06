*Disclaimer: all specific terms are capitalized on purpose, I am not stoopid*

# Service Droid

A Discord bot built on py-cord. Originally created for Stellaris YouTuber [Ep3o](https://www.youtube.com/@Ep3o), now covers LFG, the Galatron community game, and scheduled Trivia.

## Setup

**Requirements:** Docker (with Compose), a Discord bot token, and a reachable **PostgreSQL** database.

1. Clone the repo.
2. Copy `.env.example` to `.env` and fill in the values:
   ```
   DISCORD_TOKEN=<your bot token>
   DEBUG=false
   COMMAND_PREFIX=!
   OWNER_IDS=<comma-separated user IDs>
   DEBUG_GUILD_IDS=<comma-separated guild IDs for dev-only slash commands>
   COMPOSE_PROJECT_NAME=service-droid
   DATABASE_URL=postgresql+psycopg://user:password@postgres:5432/service_droid
   ```
3. Start it:
   ```bash
   docker compose up -d --build
   ```
On start, the container sets up the database automatically, then launches the bot.
It restarts itself on exit, so `/restart` and crashes both recover on their own.
Follow the log with `docker compose logs -f bot`.

**Updating:** `git pull && docker compose up -d --build`.
On the maintained server this is automatic — pushing to `main` (prod) or `dev` triggers a GitHub Actions deploy.

## Commands

### LFG

| Command                              | Description                                                                                  |
|--------------------------------------|----------------------------------------------------------------------------------------------|
| `/lfg [message]` or `!lfg [message]` | Post an LFG ping in a configured LFG channel. Requires a Host Role with a non-zero cooldown. |
| `/reset_cooldown [member]`           | Admin: reset cooldowns (one member or all).                                                  |
| `/commands_lfg`                      | List all LFG-related slash commands (clickable mentions).                                    |

**Setup (Admin):**

| Command                                              | Description                                                                                                |
|------------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| `/setting_add_lfg {channel} {role}`                  | Make a channel an LFG channel / add a role to be mentioned.                                                |
| `/setting_remove_lfg {channel}`                      | Remove an LFG channel.                                                                                     |
| `/setting_set_host {role} {time_unit} {time_amount}` | Set a Host Role and its cooldown. Cooldown 0 disables LFG for members whose highest Host Role is this one. |
| `/setting_remove_host {role}`                        | Remove a Host Role.                                                                                        |
| `/current_settings_lfg`                              | Show current LFG setup.                                                                                    |

### Galatron

A community claim-the-artifact game: members roll for a server-wide role, with cooldowns and chance configurable per guild.

| Command                                   | Description                                                        |
|-------------------------------------------|--------------------------------------------------------------------|
| `/attempt_galatron` / `/galatron_attempt` | Roll for the Galatron.                                             |
| `/locate_galatron` / `/galatron_locate`   | Show the current bearer.                                           |
| `/galatron_leaderboard`                   | All-time top bearers (by total bearing duration).                  |
| `/galatron_stats`                         | Paginated per-member stats (tries, successes, time held).          |
| `/galatron_stats_total`                   | Aggregate stats incl. cumulative and exact binomial probabilities. |
| `/commands_galatron`                      | List all Galatron-related slash commands (clickable mentions).     |

**Setup (Admin):**

| Command                                                    | Description                                                |
|------------------------------------------------------------|------------------------------------------------------------|
| `/setting_add_galatron_channel {channel}`                  | Add a channel where the Galatron can be claimed.           |
| `/setting_remove_galatron_channel {channel}`               | Remove a Galatron channel.                                 |
| `/setting_set_galatron_role {role}`                        | Set the role granted to the current bearer.                |
| `/setting_set_galatron_cooldown {time_unit} {time_amount}` | Per-member cooldown between attempts.                      |
| `/setting_set_galatron_chance {chance}`                    | Success chance (as percentage).                            |
| `/current_settings_galatron`                               | Show current Galatron setup.                               |
| `/galatron_reset`                                          | Wipe all Galatron history, last-used, and total-uses data. |

### Trivia

Per-channel scheduled trivia using cron expressions. Each channel binds to a named question list.

**Question wordings.** A trivia question consists of one title, one answer, an optional answer context — and a list of *wordings*. Each wording is an alternative phrasing of the same question; when the question fires, one wording is picked at random. Initial questions are created with a single wording via `/setting_trivia_add`; further wordings are added later with `/setting_trivia_add_variation`. To edit a question, delete it and create it anew.

**Scheduling.** Cron expressions are evaluated in **UTC**. A schedule like `0 20 * * *` posts daily at 20:00 UTC, not at the server's local time. Use a UTC offset converter to translate from your wall-clock time.

**Lists (Admin):**
| Command | Description |
|---|---|
| `/setting_trivia_list` | Show all lists with question counts. |
| `/setting_trivia_list_add {name}` | Create an empty list. |
| `/setting_trivia_list_remove` | Delete a list (must not be referenced by any channel). |
| `/setting_trivia_list_show` | Browse questions of a list (paginated). |
| `/setting_trivia_add {title} {question} {answer} [answer_context]` | Add a question to a list (with one initial wording). |
| `/setting_trivia_add_variation {trivia_id} {wording}` | Append another wording to an existing question. |
| `/setting_trivia_remove {trivia_id}` | Remove a question by ID. |

**Channel bindings (Admin):**

| Command                                                                      | Description                                                                                                                   |
|------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `/setting_trivia_set_channel {channel} {schedule} {response} [mode] [order]` | Bind a channel to a list. `schedule` is a 5-field cron expression (UTC), `response` is seconds before the answer is revealed. |
| `/setting_trivia_reset_channel {channel}`                                    | Unbind a channel.                                                                                                             |
| `/setting_trivia_show_mappings`                                              | Show all channel→list bindings + next-fire times.                                                                             |
| `/setting_trivia_update_schedule {channel} {schedule}`                       | Change a channel's cron schedule.                                                                                             |
| `/setting_trivia_update_response {channel} {response}`                       | Change a channel's response time.                                                                                             |
| `/commands_trivia`                                                           | List all trivia-related slash commands (clickable mentions).                                                                  |

### Minecraft status

Mirrors a Minecraft server's live status in a voice channel's name.
The bot pings the server directly and renames the channel to one of:

- `🟢 Online: {count}` — server reachable, `{count}` players online
- `🟠 Restarting` — server was online but stopped responding recently
- `🔴 Offline` — server not reachable

Discord rate-limits channel renames to **2 per 10 minutes per channel**, so the
name updates roughly every 5–6 minutes (and only when the status actually changed).
A restart that finishes within ~11 minutes shows as `Restarting`; longer outages flip to `Offline`.
The bot needs the **Manage Channels** permission on the voice channel.

**Commands (Admin):**

| Command                                              | Description                                                                                                  |
|------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `/setting_minecraft_set_channel {channel} {address}` | Mirror a server's status in a voice channel's name. `address` is the server address (`host` or `host:port`). |
| `/setting_minecraft_remove_channel {channel}`        | Stop updating a channel (the current name is kept).                                                          |
| `/setting_minecraft_show_mappings`                   | Show all channel→server mappings.                                                                            |
| `/commands_minecraft`                                | List all Minecraft-related slash commands (clickable mentions).                                              |

### Dev (owner only, visible only on `DEBUG_GUILD_IDS`)

| Command                 | Description                                                  |
|-------------------------|--------------------------------------------------------------|
| `/status`               | Heartbeat ping.                                              |
| `/log [lines_per_page]` | Paginated terminal log viewer.                               |
| `/list_guilds`          | List all servers the bot is in, with its permissions/roles.  |
| `/reload [guild_id]`    | Reload a server's config from the database.                  |
| `/shutdown`             | Stop the bot (no restart).                                   |
| `/restart`              | Restart the bot.                                             |
| `/update_git`           | Run `git pull` in the repo (unused on the container deploy). |