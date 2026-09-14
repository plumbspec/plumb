---
kind: reference
role: [programmer, operator]
summary: The support record's shape, versioned — what a filer writes and a support service reads.
---

# The record contract

**Version 5.** A client may emit v3 until its schema bump lands; a support service accepts both.

The support record is the durable artifact of the support channel: what `plumb support file`
writes to disk, what transmission carries, what a support service stores and a reader holds years
later. This document is the schema: a support service builds against it, and neither end may assume
anything the other cannot read here.

## Versioning rules

- Every record is **stamped at write** with the schema that produced it (`version`), so a reader tells shapes apart by the stamp and never by which fields happen to be present.
- A record with **no `version` field is v0 by definition** — not "probably current", which is the guess a version exists to remove.
- Migration is a **ladder, and it lives on the filer only**: one step per bump, keyed by the version it upgrades *from*; a record climbs before it is sent and is written back at the top. The support service never migrate-reads — the same migration in two repositories comes apart, which is the drift this document exists to end. What the support service owes is refusing by name what it cannot read.
- A support service **accepts what it names and refuses the rest by name**: `/spec` lists its versions and every `426` carries them beside what actually arrived. A refused filing queues on the filer's side and retries; nothing is lost to a refusal.
- **There is no record-version header** (deferred at ratification): no record change has yet moved without the wire moving too, and a second version axis is a second negotiation and a second way to contradict. The header enters the contract with the first change that moves the record and not the wire — and until then, the only version header on the wire is `Plumb-Support-Version`, and sending anything else's number in a version header is the confusion that prompted this document.

## The ladder, v0 → v5

| step | what changed | migration |
|---|---|---|
| v0 → v1 | `layer` became `depth` | rename; same meaning, same values |
| v1 → v2 | `kind` arrived; `observer` · `invocation` · `diagnostic` arrived; `implication` stopped being universal | kind defaults to `friction` (it is all there was to file); the three support facts backfill as `unknown` — they applied and were not recorded, which is not the same fact as not applying |
| v2 → v3 | `filed_by` arrived — which account filed this, resolved from the credential and never read from the payload | backfills as `unknown`: every v2 record *was* filed by somebody, and only the two-value `source` survives; the filer applied and was lost, which cannot be backfilled |
| v3 → v4 | the **intake** fields arrived: `attempting` · `instead` · `recurrence` | backfill with the uncaptured marker — those records came from clients where the fields applied and nothing wrote them down |
| v4 → v5 | `tool_version` arrived — the tool's own version, read out of the artifact and never typed | backfill with the uncaptured marker; a filer may also send it **withheld**, which stays apart from uncaptured — declining to say is a different fact from predating the field |

## Fields

**Required, every kind:** `id` · `observed_at` · `source` · `kind` · `observation`

**Required per kind:** `implication` — of `friction` only, and **absent or JSON null on every
other kind**: absent and null make the same claim, and both are honest, because a
marker speaks about a field that could have carried something and implication does not apply
away from friction. A marker or the bare word there is refused. On friction: missing is
refused, real text is required.

**Intake** — asked of the person, held apart from the conditional list because that one
describes the machine and the run: `attempting` (one line of free text) · `instead`
(`carried-on · worked-around · stopped · abandoned · unknown`) · `recurrence` (`first-time ·
happens-often · unknown`). They apply to every kind. A fact never sent is stored as the
uncaptured marker; the same word sent deliberately is stored as a value — *they told me
unknown* and *they told me nothing* stay different facts.

**Conditional** (a record says why one is absent rather than omitting it):
`project` · `commit` · `location` · `excerpt` · `story` · `depth` · `condition_code` ·
`board_status` · `observer` · `invocation` · `diagnostic`

**Reported, never established:** `tool_version` is what the filer's
artifact said of itself. The support service can refuse a malformed version and never an untrue
one, so an answer grounded on it states the release was *reported* by the client. A case with
no release grounds only with that caveat and names the doc set it used; absence is the
uncaptured marker, never *current* — treating it as current would ground answers for the newest
release against the population most likely to be on an old one.

**Stamped by the support service, never read from the payload:** `filed_by` — `n/a` until a support service
stamps it, because a record on the filer's own disk has not been filed to anybody yet.

**Free:** `tags`, a tuple of strings.

## The wire shape — a marker is never sent

On the wire, **absence produces the marker at the
support service**, each field defaulting to the absence that is true of it — an omitted excerpt is
*withheld*, an unasked intake question is *uncaptured*. A marker word sent as text is stored as
an **answer**, asserting a reply the filer never gave. So the wire body omits every
marker-valued field and every never-asked intake question; what travels is what somebody
actually supplied — `unknown` answered deliberately included, which is why the client's intake
defaults are a sentinel and not the marker word. The disk shape keeps every field, markers and
all: the record outlives the wire.

## Absence is three different facts

| marker | meaning | what a reader does |
|---|---|---|
| `n/a` | the field does not apply to this record | nothing — this is an answer |
| `unknown` | it applied, and was not captured | diagnose — more can be learned |
| `withheld` | it applied, was captured, and the filer chose not to send it | ask permission — their human's, not more diagnosis |

Collapsing any two of these is how a support service invents facts. `withheld` is first-class: the
channel crosses a confidentiality boundary, and *I may not tell you* routes differently from
*I do not know*.

## Kinds

`friction` · `question` · `idea` · `report`. The default is `friction`, because a record written
before the field existed is one. Only friction claims an implication.

## What each side owes

- **The filer** stamps every record, announces the version on the wire, and queues on refusal.
- **The support service** names its accepted versions in `/spec` and in every `426`, and refuses by name what it cannot read. It migrates nothing.
- **Whoever migrates** — the filer — backfills only with absence markers, never a substantive default, because a migrated record indistinguishable from a measured one is a fabrication.
- **Both** treat this document as the only statement of the shape. A second copy in either repository is the drift this contract exists to end.
