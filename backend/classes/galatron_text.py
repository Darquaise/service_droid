from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar, Iterable, TYPE_CHECKING

from . import clock

if TYPE_CHECKING:
    import discord
    from .galatron import GalatronLog


class Register(StrEnum):
    """The voice the Galatron speaks in. It holds for a whole reign and is rerolled on every
    win, so a dig-site report never ends on a Senate punchline."""

    SURVEY = "survey"
    SHROUD = "shroud"
    COURT = "court"


rng = random.Random()
"""Every roll in this module goes through this generator, so a test can seed it."""

KEEP_REGISTER_WEIGHT = 0.2
"""Chance that a win keeps the outgoing register. The other two split the rest evenly."""


def next_register(current: Register) -> Register:
    others = (1 - KEEP_REGISTER_WEIGHT) / (len(Register) - 1)
    weights = [KEEP_REGISTER_WEIGHT if r == current else others for r in Register]
    return rng.choices(list(Register), weights=weights)[0]


class Pool:
    """A list of interchangeable lines that avoids repeating its own recent picks."""

    __slots__ = "key", "entries"

    _recent: ClassVar[dict[tuple[int, str], deque[int]]] = {}

    def __init__(self, key: str, entries: list[str]):
        self.key = key
        self.entries = entries

    @property
    def _memory(self) -> int:
        return max(1, min(len(self.entries) // 2, 8))

    def pick(self, guild_id: int) -> str:
        if len(self.entries) == 1:
            return self.entries[0]

        seen = self._recent.setdefault((guild_id, self.key), deque(maxlen=self._memory))
        # _memory never exceeds half the pool, so there is always something left to choose from.
        choices = [i for i in range(len(self.entries)) if i not in seen]
        index = rng.choice(choices)
        seen.append(index)
        return self.entries[index]


def _pools(prefix: str, mapping: dict[str, list[str]]) -> dict[str, Pool]:
    return {key: Pool(f"{prefix}.{key}", entries) for key, entries in mapping.items()}


# --------------------------------------------------------------------------------------
# Scenes: what happened during the attempt. "{old}" is the current bearer's mention.
# --------------------------------------------------------------------------------------

SCENES: dict[str, Pool] = _pools("scene", {
    # ---- failed attempt, nobody holds it: you are digging ----
    "survey/fail/open": [
        "The vault opens on schedule and yields exactly what the survey predicted: ceramic shards, a corroded lockbox and four crates of minor artifacts.",
        "Your xeno-archaeologists spend eleven days cataloguing the chamber before conceding that it was a granary. A very old, very well defended granary.",
        "Deep scans flag a density anomaly at forty metres. It resolves into a burial cyst: sealed, empty, and picked clean long before your species had writing.",
        "The dig team reaches the sealed level and finds the seal already broken. Whatever this Reliquary held, someone collected it an epoch ago.",
        "Ground survey lights up beautifully. The excavation recovers a ceremonial mask, two hundred tonnes of inert alloy and the distinct impression of having arrived late.",
        "The site is genuine, the stratigraphy undisturbed, and the chamber at the bottom of it contains a single desiccated seed pod.",
        "Three months of core sampling produce a report your science director summarises in one word and then apologises for.",
        "The Curators sell you a survey lead at a generous discount. You understand why once the shaft is open.",
        "Your team recovers eleven intact tablets. Translation takes a year and reveals a dispute over grain allocation.",
        "The excavation is textbook, the chamber is textbook, and the contents are regrettably also textbook.",
        "A collapsed access ramp costs you two months. Behind it is a second collapsed access ramp.",
        "The survey drones map nine kilometres of corridor without finding a single door that was closed on purpose.",
    ],
    "shroud/fail/open": [
        "Your psionic corps reports a pressure behind the eyes for the length of the excavation. The instruments log nothing at all, and the two accounts are filed separately.",
        "A seer on your staff writes a set of coordinates in her sleep. They resolve to a star that burned out before your homeworld had a crust.",
        "The dig crew refuses the night shift six days running and will not say why. The chamber, when it is finally opened, is empty.",
        "Four hundred people dream the same shape on the same night. By morning it has the consistency of a rumour, and the survey has found nothing.",
        "Your mediums agree that the object is close. They have been agreeing this for some time now.",
        "The Shroud is loud that week. Loud has never been the same as helpful.",
        "An acolyte insists the chamber was warm when they opened it. The thermal log disagrees, and the report records both without comment.",
        "The trance is held correctly, by the right people, at the right hour. It returns static and a headache.",
    ],
    "court/fail/open": [
        "Your envoy secures the excavation rights, the survey permit and the salvage claim. The Reliquary turns out to have been catalogued and emptied by the Curators two centuries ago.",
        "The Senate approves your petition to survey the site by a single vote. The site produces nothing, and the vote costs rather more than the dig did.",
        "You outbid four empires for the lead. In hindsight, all four of them had priced it correctly.",
        "A resolution granting your empire first claim on unrecovered relics passes comfortably. There is, as yet, nothing to claim.",
        "Your delegation spends an entire session establishing precedent for a discovery that does not occur.",
        "The dig permit is granted, revoked, restored on appeal and granted again. The chamber under all that paper is empty.",
    ],

    # ---- failed attempt, someone holds it: you are reaching for theirs ----
    "survey/fail/contested": [
        "Your archaeotech division proposes a second Galatron on theoretical grounds. Eighteen months of excavation suggest the theory needs work.",
        "You commission a discreet survey of {old}'s holdings. The survey team returns with excellent photographs and nothing else.",
        "The dig is a pretext and everyone knows it, including {old}'s customs authority, who turn your ships around at the border.",
        "Your specialists reconstruct the object's resonance from archived scans and go looking for its twin. The galaxy declines to provide one.",
        "You buy every Reliquary lead the Curators are willing to sell. They are happy to sell, and quietly certain of the outcome.",
        "The salvage claim is filed, contested and struck down before your ships have finished fuelling.",
        "Your people get as far as the outer vault schematics. {old}'s people updated those schematics last year.",
    ],
    "shroud/fail/contested": [
        "Your mediums reach for the object and report {old} already standing in the way. The transcripts are consistent, but transcripts are not evidence.",
        "The corps attempts a locating trance and returns with {old}'s star, which everyone in the room already knew.",
        "A seer wakes shouting {old}'s name and cannot explain it. It is either significant or it has been a very long week.",
        "Your acolytes fast for nine days to petition the Shroud about the cube. The Shroud, as ever, is under no obligation.",
        "Something is reached for. Something declines. The corps writes it up in the passive voice.",
    ],
    "court/fail/contested": [
        "You table a resolution requiring that the cube's custody be reviewed. {old} votes against it with a great deal of diplomatic weight.",
        "Your envoys pursue the Take Galatron casus belli through every committee available to them. Committees are where such things go.",
        "The casus belli is valid, the fleet is ready, and the Senate schedules the hearing for after the recess.",
        "You offer {old} eight thousand alloys, a border concession and a defensive pact. The offer is read into the record and declined.",
        "Three empires join your motion against {old}. Three is not enough, and everybody counted beforehand.",
        "Your delegation argues custody law for six hours. {old}'s delegation lets them, then votes.",
    ],

    # ---- successful attempt, nobody held it ----
    "survey/win/open": [
        "The manifest comes back with one line your quartermaster refuses to sign for: OBJECT, CUBIC, MASS ANOMALOUS.",
        "At sixty metres the drills stop, not because they fail but because the operators do. The chamber below is intact.",
        "The chamber is smaller than the survey promised and contains exactly one thing, resting where it was left.",
        "Your team opens the Reliquary expecting the usual crates. The usual crates are there, arranged very carefully around something else.",
        "The site was flagged low-probability and dug on a junior researcher's insistence. She is going to be difficult to manage from now on.",
    ],
    "shroud/win/open": [
        "Every psionic on the expedition wakes at the same moment and none of them can say why. By the time the shaft is clear they are simply standing around it.",
        "The seer who gave you the coordinates asks to be present, then asks to be excused, and afterwards will not discuss it.",
        "For nine days your mediums say nothing at all. On the tenth, one of them gives a bearing.",
    ],
    "court/win/open": [
        "Your delegation registers the recovery before the science vessel has finished docking.",
        "The claim goes uncontested, because nobody believed there was anything left to contest.",
        "You spent a decade of influence establishing first claim on unrecovered relics. This is the session in which that stops looking foolish.",
    ],

    # ---- successful attempt, taken from someone ----
    "survey/win/contested": [
        "Your specialists find the seam in {old}'s custody arrangements that {old}'s specialists had assured them did not exist.",
        "The salvage claim against {old} is filed, and for once the paperwork moves faster than the fleet.",
        "It takes eleven minutes at the vault, and four years of preparation before those eleven minutes.",
        "{old}'s garrison is competent, well paid, and watching the correct corridor.",
    ],
    "shroud/win/contested": [
        "Your corps reaches for the cube where {old} keeps it, and this time there is nothing standing in the way.",
        "A locating trance gives your fleet {old}'s vault, the shift rotation, and a window of eleven minutes.",
    ],
    "court/win/contested": [
        "The Take Galatron wargoal is declared, prosecuted and settled while {old}'s allies are still consulting.",
        "{old} loses the vote, then the appeal, then the cube, in that order and within the same session.",
        "You spend influence, favours and a century of goodwill on it. {old}'s coalition lasts four days.",
    ],
})


# --------------------------------------------------------------------------------------
# Aftermath: how the galaxy reacts. Same register, same contested-ness as the scene.
# --------------------------------------------------------------------------------------

AFTERMATH: dict[str, Pool] = _pools("aftermath", {
    "survey/fail/open": [
        "The find is logged, crated and filed. The Galatron is not among it.",
        "The site is backfilled and the permit released. Somewhere, it is still out there.",
        "Your science director files the report under partial success and declines to elaborate.",
        "The crates go to the archive. The archive has a great many crates.",
        "The survey drones are recalled and pointed at the next candidate system.",
        "Another Reliquary is crossed off a list that does not appear to be getting shorter.",
        "The manifest is signed. Nothing on it pulsates with indescribable power.",
        "The expedition comes in under budget, which is the only remarkable thing about it.",
    ],
    "shroud/fail/open": [
        "The corps stands down. Whatever brushed past them is on no manifest anywhere.",
        "The visions are transcribed, sealed and shelved with all the others.",
        "Your seers sleep badly and find nothing, which is the usual arrangement.",
        "Nothing is recovered. Several people remain certain that something was missed.",
        "The expedition ends. The dreams take rather longer to.",
    ],
    "court/fail/open": [
        "The claim stands, elegantly, over nothing at all.",
        "Your diplomatic weight is unchanged, which is the polite way of putting it.",
        "The Senate moves to the next item. Eventually, so do you.",
        "Influence spent, precedent gained, cube unlocated.",
    ],

    "survey/fail/contested": [
        "{old} keeps it. The crates you brought home are labelled and forgotten.",
        "The cube stays where it is, in {old}'s custody, behind a considerable quantity of alloy.",
        "{old}'s ministry issues no statement. It does not need to.",
        "Your claim is entered into the record beneath everyone else's. {old} remains the holder.",
        "The archive gains a folder. {old} loses nothing.",
    ],
    "shroud/fail/contested": [
        "{old} sleeps undisturbed, so far as anyone is able to determine.",
        "The trance ends. {old} still holds it, and now knows that someone was looking.",
        "Nothing crosses over. {old} keeps the cube and you keep the transcripts.",
    ],
    "court/fail/contested": [
        "{old} keeps the cube, and the weight that comes with it.",
        "The motion fails. {old}'s envoys are gracious about it, which is worse.",
        "{old}'s diplomatic weight settles the matter before the vote is even called.",
        "The record shows your attempt. The record shows a great many attempts.",
    ],

    "survey/win/open": [
        "It pulsates with a power the report cannot describe, and that report is written by people who are paid to describe things.",
        "Every sensor aboard begins disagreeing with every other sensor. The cube is aboard.",
        "The recovery is logged and immediately reclassified above your science director's clearance.",
        "The crates go to the archive. The cube does not.",
    ],
    "shroud/win/open": [
        "It pulsates. Your corps declines to specify with what.",
        "The dreams stop that night, across the whole fleet, at the same hour.",
        "Nobody aboard will call it coincidence, and nobody will write down what they think it is instead.",
    ],
    "court/win/open": [
        "Your diplomatic weight doubles before the recovery report reaches the Senate floor.",
        "By the time the recovery is read aloud, three empires have quietly withdrawn their envoys.",
        "The galaxy now has a reason to go to war with you, and the galaxy is aware of it.",
    ],

    "survey/win/contested": [
        "The cube changes hands. {old}'s ministry has not yet drafted a statement.",
        "{old} is left with an empty pedestal and a very long inquiry ahead of them.",
        "Custody transfers. {old} will hear about it from the Senate before hearing it from their own staff.",
    ],
    "shroud/win/contested": [
        "{old} is said to have woken at the exact moment. The transcripts are not evidence, but they are consistent.",
        "The cube is yours. {old}'s seers, if they keep any, were looking elsewhere.",
    ],
    "court/win/contested": [
        "The cube transfers into your custody, and so does every casus belli that comes with it.",
        "{old}'s weight in the Senate halves overnight. Yours does the opposite.",
        "{old} concedes formally and briefly. Everyone present understands what has changed.",
    ],
})


TITLES: dict[str, Pool] = _pools("title", {
    "survey/fail": [
        "Excavation Report",
        "Site Report: Negative",
        "Nothing Recovered",
        "Survey Concluded",
        "Dig Closed",
    ],
    "shroud/fail": [
        "Nothing Answers",
        "Silence in the Shroud",
        "Unattributed Reading",
        "The Trance Returns Empty",
    ],
    "court/fail": [
        "Motion Denied",
        "Claim Dismissed",
        "The Record Notes Your Attempt",
        "Session Adjourned",
    ],
    "survey/win": [
        "Recovery Confirmed",
        "Object Recovered",
        "Manifest: One Line Amended",
        "The Chamber Was Not Empty",
    ],
    "shroud/win": [
        "The Dreams Stop",
        "It Pulsates",
        "The Corps Falls Silent",
    ],
    "court/win": [
        "Custody Transferred",
        "The Weight Shifts",
        "Claim Upheld",
    ],
})


SHORT_FAIL: dict[str, Pool] = _pools("short.fail", {
    "survey": [
        "The site yields nothing.",
        "Another empty vault.",
        "Nothing on the manifest.",
        "The chamber was empty.",
        "The survey comes back negative.",
        "The dig ends, and the cube is elsewhere.",
        "Filed under: unsuccessful.",
    ],
    "shroud": [
        "The Shroud stays quiet.",
        "Nothing answers.",
        "The trance returns empty.",
        "No bearing, no cube.",
        "Whatever brushed past, it was not the cube.",
        "The corps stands down.",
    ],
    "court": [
        "The claim is denied.",
        "The motion fails.",
        "The Senate moves on.",
        "Denied, and entered into the record.",
        "The vote goes the other way.",
        "No claim, no cube, no comment.",
    ],
})


# --------------------------------------------------------------------------------------
# Special cases
# --------------------------------------------------------------------------------------

CONTEXTS: dict[str, Pool] = _pools("context", {
    "first_bearer": [
        "No one in this server has ever held it before you.",
        "The chronicle starts here, with your name at the top of it.",
        "There is no previous holder to take it from. There never has been.",
    ],
    "first_win": [
        "This is the first time it has ever been in your hands.",
        "After everything, it is finally yours for the first time.",
        "Your first tenure begins here.",
    ],
    "record_reign": [
        "{old} held it for {duration}, the longest tenure this server has recorded.",
        "You have ended the longest reign in the chronicle: {duration}.",
        "{duration} of uninterrupted custody, and you are the one who ended it.",
    ],
    "revenge": [
        "It was {old} who took it from you last time.",
        "{old} took it from you once. That is now settled.",
        "The last person to take it out of your hands was {old}.",
    ],
    "blitz": [
        "{old} had held it for {duration}.",
        "{old} held it for {duration}, barely long enough to log it.",
        "{duration} of custody, and that is all {old} gets.",
    ],
    "dynasty": [
        "{old} had held it for {duration}.",
        "{duration} of {old}'s custody ends here.",
        "It had been {old}'s for {duration}.",
    ],
    "siege": [
        "{count} attempts have broken against {old} since they took it.",
        "{old} has turned away {count} attempts. Not this one.",
        "You are one of {count} who have reached for it during {old}'s tenure.",
    ],
    "milestone": [
        "That was your {ordinal} attempt.",
        "Attempt number {count}, for the record.",
        "The chronicle counts {count} attempts from you now.",
    ],
    "first_attempt": [
        "Your first attempt on record.",
        "The chronicle has opened a page for you.",
        "That was the first time you have ever reached for it.",
    ],
    "returning": [
        "Your first attempt in {duration}.",
        "It has been {duration} since you last tried.",
        "You have not reached for it in {duration}.",
    ],
    "personal_dry": [
        "{count} attempts since you last held it.",
        "It has been {duration} since it was last yours.",
        "You last held it {duration} ago.",
    ],
    "never_won": [
        "{count} attempts, and it has never once been yours.",
        "{count} attempts on record. None of them successful.",
        "Still nothing to show for {count} attempts.",
    ],
})


@dataclass(frozen=True, slots=True)
class ContextRule:
    """``chance`` is how often the case is actually mentioned when it applies. Common
    situations stay quiet most of the time so they don't turn into a catchphrase."""

    key: str
    priority: int
    chance: float


CONTEXT_RULES: tuple[ContextRule, ...] = (
    ContextRule("first_bearer", 100, 1.0),
    ContextRule("first_win", 95, 1.0),
    ContextRule("record_reign", 90, 1.0),
    ContextRule("revenge", 80, 0.7),
    ContextRule("blitz", 70, 0.8),
    ContextRule("dynasty", 65, 0.6),
    ContextRule("first_attempt", 60, 1.0),
    ContextRule("milestone", 55, 0.9),
    ContextRule("returning", 50, 0.6),
    ContextRule("never_won", 40, 0.3),
    ContextRule("personal_dry", 35, 0.3),
    ContextRule("siege", 20, 0.25),
)

BLITZ_UNDER = timedelta(hours=1)
DYNASTY_OVER = timedelta(days=7)
RETURNING_AFTER = timedelta(days=30)
NEVER_WON_FROM = 15
PERSONAL_DRY_FROM = 25
SIEGE_FROM = 5
MILESTONES = (10, 25, 50, 100, 250, 500, 1000)


@dataclass(slots=True)
class AttemptContext:
    """Everything the texts may know about an attempt, computed from the log *before*
    the attempt itself is recorded."""

    attempt_number: int
    member_wins: int
    old_owner: "discord.Member | None"
    reign: timedelta | None
    reign_is_record: bool
    attempts_this_reign: int
    took_it_from_me_last: bool
    since_own_win: timedelta | None
    attempts_since_own_win: int
    since_last_attempt: timedelta | None
    server_has_history: bool

    @property
    def contested(self) -> bool:
        return self.old_owner is not None

    @property
    def has_ever_won(self) -> bool:
        return self.member_wins > 0

    @property
    def old_mention(self) -> str:
        return self.old_owner.mention if self.old_owner else ""


def build_context(log: "GalatronLog", member_id: int, now: datetime | None = None) -> AttemptContext:
    now = now or clock.now_utc()
    attempts = log.attempts
    wins = log.wins

    last_win = wins[-1] if wins else None
    reign = now - last_win.occurred_at if last_win else None

    longest_reign = timedelta()
    for i, win in enumerate(wins):
        end = wins[i + 1].occurred_at if i + 1 < len(wins) else now
        longest_reign = max(longest_reign, end - win.occurred_at)

    attempts_this_reign = sum(
        1 for a in attempts if last_win is None or a.occurred_at > last_win.occurred_at
    )

    own_wins = [w for w in wins if w.member_id == member_id]
    own_last_win = own_wins[-1] if own_wins else None

    took_it_from_me_last = False
    if own_last_win is not None and last_win is not None:
        after = [w for w in wins if w.occurred_at > own_last_win.occurred_at]
        took_it_from_me_last = bool(after) and after[0].member_id == last_win.member_id

    attempts_since_own_win = 0
    if own_last_win is not None:
        attempts_since_own_win = sum(
            1 for a in attempts
            if a.member_id == member_id and a.occurred_at > own_last_win.occurred_at
        )

    last_attempt = log.last_attempt_at(member_id)

    return AttemptContext(
        attempt_number=log.total_for(member_id) + 1,
        member_wins=len(own_wins),
        old_owner=log.get_current_owner(),
        reign=reign,
        reign_is_record=reign is not None and reign >= longest_reign,
        attempts_this_reign=attempts_this_reign,
        took_it_from_me_last=took_it_from_me_last,
        since_own_win=now - own_last_win.occurred_at if own_last_win else None,
        attempts_since_own_win=attempts_since_own_win,
        since_last_attempt=now - last_attempt if last_attempt else None,
        server_has_history=bool(wins),
    )


def _applicable(ctx: AttemptContext, won: bool) -> dict[str, dict[str, object]]:
    """Context key -> the values its lines may interpolate, for every case that fits."""
    out: dict[str, dict[str, object]] = {}
    old = ctx.old_mention

    if won and not ctx.server_has_history:
        out["first_bearer"] = {}
    if won and not ctx.has_ever_won and ctx.server_has_history:
        out["first_win"] = {}

    if won and ctx.old_owner and ctx.reign is not None:
        if ctx.reign_is_record and ctx.reign >= DYNASTY_OVER:
            out["record_reign"] = {"old": old, "duration": _duration(ctx.reign)}
        elif ctx.reign < BLITZ_UNDER:
            out["blitz"] = {"old": old, "duration": _duration(ctx.reign)}
        elif ctx.reign > DYNASTY_OVER:
            out["dynasty"] = {"old": old, "duration": _duration(ctx.reign)}
        if ctx.took_it_from_me_last:
            out["revenge"] = {"old": old}

    if ctx.attempt_number == 1:
        out["first_attempt"] = {}
    elif ctx.attempt_number in MILESTONES:
        out["milestone"] = {"count": ctx.attempt_number, "ordinal": _ordinal(ctx.attempt_number)}

    if ctx.since_last_attempt is not None and ctx.since_last_attempt > RETURNING_AFTER:
        out["returning"] = {"duration": _duration(ctx.since_last_attempt)}

    if not won:
        if not ctx.has_ever_won and ctx.attempt_number >= NEVER_WON_FROM:
            out["never_won"] = {"count": ctx.attempt_number}
        elif ctx.attempts_since_own_win >= PERSONAL_DRY_FROM and ctx.since_own_win is not None:
            out["personal_dry"] = {
                "count": ctx.attempts_since_own_win,
                "duration": _duration(ctx.since_own_win),
            }
        if ctx.old_owner and ctx.attempts_this_reign >= SIEGE_FROM:
            out["siege"] = {"old": old, "count": ctx.attempts_this_reign}

    return out


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


DURATION_UNITS = (("day", 86_400), ("hour", 3_600), ("minute", 60), ("second", 1))


def _duration(td: timedelta) -> str:
    """The largest unit and the one below it ("9 days and 4 hours"), cut off rather than rounded."""
    remaining = int(td.total_seconds())
    for i, (_, size) in enumerate(DURATION_UNITS):
        if remaining >= size:
            break
    else:
        return "a matter of seconds"

    parts = []
    for name, size in DURATION_UNITS[i:i + 2]:
        amount, remaining = divmod(remaining, size)
        if amount:
            parts.append(f"{amount} {name}{'' if amount == 1 else 's'}")
    return " and ".join(parts)


def _pick_context(ctx: AttemptContext, won: bool, guild_id: int) -> str | None:
    available = _applicable(ctx, won)
    rolled = [
        rule for rule in CONTEXT_RULES
        if rule.key in available and rng.random() < rule.chance
    ]
    if not rolled:
        return None

    rule = max(rolled, key=lambda r: r.priority)
    return CONTEXTS[rule.key].pick(guild_id).format(**available[rule.key])


@dataclass(frozen=True, slots=True)
class ComposedAttempt:
    body: str
    """Title, scene, aftermath and at most one special-case line."""
    short: str
    """The one-liner for the channel when the attempt failed."""


def compose_attempt(ctx: AttemptContext, won: bool, guild_id: int, register: Register) -> ComposedAttempt:
    """One attempt's write-up. Every slot, the public one-liner included, comes from the
    reign's register, so nothing can clash."""
    contested = "contested" if ctx.contested else "open"
    outcome = "win" if won else "fail"

    key = f"{register}/{outcome}/{contested}"
    title = TITLES[f"{register}/{outcome}"].pick(guild_id)
    scene = SCENES[key].pick(guild_id).format(old=ctx.old_mention)
    aftermath = AFTERMATH[key].pick(guild_id).format(old=ctx.old_mention)

    body = f"**{title}**\n{scene} {aftermath}"

    extra = _pick_context(ctx, won, guild_id)
    if extra:
        body += f"\n{extra}"

    return ComposedAttempt(body=body, short=SHORT_FAIL[register].pick(guild_id))


# --------------------------------------------------------------------------------------
# Everything outside the attempt itself, told in the reign's register as well
# --------------------------------------------------------------------------------------

WRONG_CHANNEL: dict[str, Pool] = _pools("wrong_channel", {
    "survey": [
        "There is no dig site here. Take it to the channel cleared for the hunt.",
        "Your survey teams are not licensed to operate in this channel. Use the designated one.",
        "Nothing is buried here. Try the channel the hunt actually runs in.",
    ],
    "shroud": [
        "The Shroud is too thin here to hear anything. Reach for it in the Galatron channel.",
        "Your mediums refuse to sit in this channel. The trance is held in the designated one.",
        "Nothing answers from here. It only listens in the Galatron channel.",
    ],
    "court": [
        "The Senate does not recognise claims filed in this channel.",
        "Wrong jurisdiction. The hunt happens in the Galatron channel.",
        "This chamber has no standing. File your claim in the designated channel.",
    ],
})

COOLDOWN: dict[str, Pool] = _pools("cooldown", {
    "survey": [
        "Your survey teams are still writing up the last expedition. The next one launches <t:{ts}:R>.",
        "Your corps needs to sleep off the last attempt. Try again <t:{ts}:R>.",
        "One expedition at a time. The next window opens <t:{ts}:R>.",
        "Your archaeologists are still in the field. They report back <t:{ts}:R>.",
    ],
    "shroud": [
        "Your mediums are still recovering from the last trance. They sit again <t:{ts}:R>.",
        "The Shroud does not answer the same voice twice in quick succession. Try again <t:{ts}:R>.",
        "The corps has been ordered to rest. The next trance is scheduled <t:{ts}:R>.",
    ],
    "court": [
        "The Senate will not hear you twice in one session. Come back <t:{ts}:R>.",
        "The permits have not cleared yet. You may file again <t:{ts}:R>.",
        "Your petition is still in committee. It returns to the floor <t:{ts}:R>.",
    ],
})

ALREADY_OWNER: dict[str, Pool] = _pools("already_owner", {
    "survey": [
        "You already hold it. There is exactly one, and it is on your pedestal.",
        "It is already in your custody. Going looking for it would be a poor use of the fleet.",
        "Your own vault already contains it. Perhaps guard it instead.",
    ],
    "shroud": [
        "Your mediums can feel it from here. It is in your vault, and it is pulsating.",
        "The dreams stopped when it came to you. Reaching for it again will not start them.",
        "The Shroud points straight back at you. You have it.",
    ],
    "court": [
        "You have it. That is rather the point of having it.",
        "The Senate already records you as its holder. A second claim would be dismissed as frivolous.",
        "Custody is already yours. There is nothing left to petition for.",
    ],
})

SUSPENDED = Pool("suspended", [
    "The excavation is suspended. The server admins have been notified to fix my permissions, try again once it's sorted.",
])

TRANSFER_FAILED = Pool("transfer_failed", [
    "The transfer of custody failed because I couldn't hand out the role. The server admins have been notified.",
])

STATUS_TITLE: dict[str, Pool] = _pools("status_title", {
    "survey": [
        "Artifact Location Report",
        "Where It Is",
        "Site Inventory",
    ],
    "shroud": [
        "What the Corps Can Feel",
        "Psionic Bearing",
        "Where the Shroud Points",
    ],
    "court": [
        "Current Custody of the Galatron",
        "Chain of Custody",
        "Holder of Record",
    ],
})

STATUS_BOUND: dict[str, Pool] = _pools("status_bound", {
    "survey": [
        "The cube is in {user}'s custody, and every empire in range knows it.",
        "Last recovered by {user}. It has not been seen outside their vault since.",
        "Inventory check: one Galatron, held by {user}.",
    ],
    "shroud": [
        "The corps' bearing points at {user}. It has not moved.",
        "Every medium on staff dreams of {user}'s vault and wakes up uneasy.",
        "It pulsates somewhere in {user}'s territory. The Shroud is sure of it.",
    ],
    "court": [
        "Current holder of record: {user}. The casus belli stands for everyone else.",
        "{user} holds it, along with the diplomatic weight and the target that comes with it.",
        "Custody rests with {user}. The Senate's arithmetic reflects it.",
    ],
})

STATUS_UNBOUND: dict[str, Pool] = _pools("status_unbound", {
    "survey": [
        "Nobody holds it. It is out there, in a chamber nobody has opened yet.",
        "The last confirmed sighting is not recent enough to be useful. It is still buried somewhere.",
        "No vault in range reports it. The dig goes on.",
    ],
    "shroud": [
        "Unclaimed. Somewhere it is sitting in the dark, pulsating with indescribable power.",
        "The corps feels it everywhere and nowhere. Nobody holds it.",
        "No bearing. Whatever it is waiting for, it is not anyone yet.",
    ],
    "court": [
        "Custody: none. The pedestal is empty and the galaxy is quietly relieved.",
        "No holder of record. The Senate's seat for it stands empty.",
        "Unclaimed, and every delegation in the chamber is aware of it.",
    ],
})

NO_LEADERBOARD: dict[str, Pool] = _pools("no_leaderboard", {
    "survey": [
        "The chronicle is empty. Nobody has held it long enough to be written down.",
        "No recoveries on file. The page is blank.",
    ],
    "shroud": [
        "The corps has nothing to remember yet. Nobody has held it.",
        "No name echoes in the Shroud. Not yet.",
    ],
    "court": [
        "No tenures on file. The page is blank.",
        "The record of custody is empty. Somebody has to be first.",
    ],
})

NO_ATTEMPTS: dict[str, Pool] = _pools("no_attempts", {
    "survey": [
        "Not a single dig on record. The hunt has not begun.",
        "The chronicle shows no attempts at all.",
    ],
    "shroud": [
        "Nobody has reached for it here. The Shroud is undisturbed.",
        "Not one trance on record.",
    ],
    "court": [
        "Not a single claim on record.",
        "Nobody has ever filed for it here.",
    ],
})


def wrong_channel(guild_id: int, register: Register) -> str:
    return WRONG_CHANNEL[register].pick(guild_id)


def cooldown(guild_id: int, register: Register, next_allowed_ts: int) -> str:
    return COOLDOWN[register].pick(guild_id).format(ts=next_allowed_ts)


def already_owner(guild_id: int, register: Register) -> str:
    return ALREADY_OWNER[register].pick(guild_id)


def suspended(guild_id: int) -> str:
    return SUSPENDED.pick(guild_id)


def transfer_failed(guild_id: int) -> str:
    return TRANSFER_FAILED.pick(guild_id)


def status_title(guild_id: int, register: Register) -> str:
    return STATUS_TITLE[register].pick(guild_id)


def status(guild_id: int, register: Register, holder: "discord.Member | None") -> str:
    if holder is None:
        return STATUS_UNBOUND[register].pick(guild_id)
    return STATUS_BOUND[register].pick(guild_id).format(user=holder.mention)


def no_leaderboard_entries(guild_id: int, register: Register) -> str:
    return NO_LEADERBOARD[register].pick(guild_id)


def no_attempts_yet(guild_id: int, register: Register) -> str:
    return NO_ATTEMPTS[register].pick(guild_id)


def all_pools() -> Iterable[Pool]:
    """Every pool in the module, for structural checks over the whole text set."""
    for mapping in (
        SCENES, AFTERMATH, TITLES, CONTEXTS, SHORT_FAIL, WRONG_CHANNEL, COOLDOWN, ALREADY_OWNER,
        STATUS_TITLE, STATUS_BOUND, STATUS_UNBOUND, NO_LEADERBOARD, NO_ATTEMPTS,
    ):
        yield from mapping.values()
    yield from (SUSPENDED, TRANSFER_FAILED)
