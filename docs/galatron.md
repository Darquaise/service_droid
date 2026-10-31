# Galatron

Paths in this document are relative to `backend/` unless they start with `backend/` or name a root file.

## Galatron data model

Every attempt is its own row in **`galatron_attempt`** (`member_id`, `occurred_at`, `won`); a win is simply an
attempt with `won`. There is no counter table and no separate history table: the per-member total is a `COUNT`,
the cooldown stamp a `MAX`, the bearer the newest `won` row. In memory this is `classes/galatron.py:GalatronLog`,
which keeps the per-member total and last-attempt stamp alongside the list so the cooldown check stays O(1).

`Guild.galatron_record_attempt(member, won)` is the single write path — it is called **after** the roll (and
after the role was actually handed out on a win), so an attempt that could not be completed doesn't burn the
member's cooldown.

Cooldown and chance are timelines, not scalars: **`galatron_cooldown`** / **`galatron_chance`** hold one row per
period (`valid_from`, value), the newest one is in force, and the oldest also covers everything before it
(`classes/generics.py:SettingTimeline`, exposed as `Guild.galatron_cooldown` / `.galatron_chance`).
`/galatron_stats_total` is what makes the chance timeline pay off: it groups the attempts by the chance that was
in force when they were made and convolves the per-group binomials (`cogs/galatron_commands.py:win_count_pmf` —
a Poisson binomial), instead of judging every attempt ever made by today's chance.
`Guild.ensure_galatron_timelines(joined_at)` runs for every guild at startup and gives a timeline its starting
point — the bot cannot have had a setting before it joined, so a missing timeline starts at the join and one
reaching further back is pulled forward to it (that is how the values carried over by migration `0004` get their
real start).

**History before this model** could not be reconstructed from the database (the old schema only had counters).
It was recovered by reading the production channel history — `backup/galatron_scan.py` collects and cross-checks
it, `backup/galatron_import.py` loads it in. Both are read-only towards Discord. They live under the gitignored
`backup/` (next to the JSON they produce in `backup/galatron_scan/`) rather than in `scripts/`, because they are
one-off tools carrying host/container names and the repo is public.

## Galatron message generation

`classes/galatron_text.py` owns every line the Galatron feature says; the cog only decides *when* to
speak. `cogs/galatron_commands.py:TextGenerator` is gone.

- **Registers.** `Register` (SURVEY / SHROUD / COURT) is the voice the Galatron speaks in. It holds
  for a whole **reign** and is persisted as `guild.galatron_register` (`Guild.galatron_register`;
  migration `0005` and the column's `server_default` roll a random one per guild). **Every** slot of an
  attempt (title, scene, aftermath, the public one-liner) and every message outside it (wrong
  channel, cooldown, already owner, `/locate_galatron`, empty leaderboard/stats) is taken from it, so a
  dig-site report can't end on a Senate punchline. This is the coherence guarantee; keep it when adding
  pools. Only the permission errors (`SUSPENDED`, `TRANSFER_FAILED`) are register-free on purpose.
- **Reroll on win.** `Guild.galatron_record_attempt` rolls a new register on every win via
  `next_register` (weighted: the outgoing register keeps `KEEP_REGISTER_WEIGHT` = 20 %, the other two
  get 40 % each). The cog reads the register **before** recording, so the win itself is still told in
  the outgoing voice.
- **Contested vs. open.** With a bearer in place an attempt is a claim against them (`{old}` is their
  mention), without one it is an excavation. Pool keys are `{register}/{win|fail}/{contested|open}`,
  and all twelve combinations must exist in both `SCENES` and `AFTERMATH` — `{old}` may only appear in
  `contested` pools.
- **`Pool.pick`** avoids its own recent picks per guild (`Pool._recent`, in-memory only), so the same
  line doesn't come up twice in a row.
- **One generator.** Every roll in the module (register, line, context chance) goes through
  `galatron_text.rng`, so a test can `rng.seed(...)` and get reproducible messages.
- **Contexts.** `build_context` derives an `AttemptContext` from `GalatronLog` and must be called
  **before** `galatron_record_attempt`, while the log still holds only past attempts (hence
  `attempt_number = total_for + 1`). `CONTEXT_RULES` carries a `priority` and a `chance` per case:
  `chance` is how often a case is mentioned *when it applies*, so frequent situations (you held it
  before, N attempts against the current bearer) stay quiet most of the time. At most one context line
  is appended per message.
- **No embeds on anything carrying a mention** — a mention inside an embed stays unresolved for viewers
  who don't have that member cached. `/locate_galatron` and the attempt replies are plain text for that
  reason; `galatron_leaderboard` works around it differently (`PRIME_DELAY`: post the mentions as
  content first, then edit to embeds).
- **Artwork.** `cogs/galatron_commands.py:GALATRON_IMAGE` points at `backend/assets/galatron.png`
  (commissioned, human-made — do not replace it with a generated image), attached via `discord.File` on
  a win. `COPY backend/ ./` in the Dockerfile ships it. It is attached, not embedded, so it renders
  without an embed. That is why `/setting_add_galatron_channel` also checks **Attach Files**. If the
  permission is lost later, the win is still announced, just without the file, and the owner is notified.
