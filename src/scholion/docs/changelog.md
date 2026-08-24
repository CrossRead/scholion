# Changelog

Semantic versions with the date in the heading: `v0.2.0 — 20.08.2026`. The number
is the unique key of an entry, the date is informative: a working day may produce
several versions or none. Rules for choosing a number — `docs/VERSIONING.md`.

**The numbering starts here.** This journal opens at the first public release. The
development that produced it ran under its own numbering, up to `2.24.0`, and that
numbering was retired at publication: it measured how much had been built, and a
version number is meant to promise something else — that a person holding the
previous version knows what moving to this one does to their data and their
commands. Nobody outside had run any of those versions, so there was nothing to
promise. They are kept privately, in `CHANGELOG.pre-0.1.0.md`, and their tags live
in a namespace of their own (`pre-0.1.0/v2.24.0`), so that if the published
numbering ever reaches `2.24.0` it is a different tag on a different commit and
cannot be mistaken for one of them.

**How to read it.** The main sections of an entry are not the file list but three
curated ones: **what this changes in the conclusions**, **what is retracted**,
**what needs recomputing**. The file list at the bottom is generated from git
(`python3 src/tools/release_notes.py`). A **series break** is marked separately —
a change to `src/scholion/knowledge/` that alters the result on unchanged input.
Values from before and after such a change cannot go on the same chart without a
note.

**Who it is for.** Somebody who has never seen this repository and wants to know
what this version does. That decides what an entry contains: **new capabilities,
fixed defects, and what either of those means for data already stored.** It also
decides what an entry does NOT contain — the path a change took, which attempt
came first, what was learned along the way, whose machine anything ran on, and
who wrote it. Those are worth recording and belong elsewhere; in a release entry
they crowd out the two questions a reader actually has: what can I do now that I
could not, and what was wrong that is now right.

**What is not here.** Personal data and one person's findings: no genotypes, no
lab values, no dates of anyone's tests. This journal records what changed in the
**system**, not what was found in somebody.

---

<!-- NEW ENTRIES GO HERE -->

## v0.4.5 — 24.08.2026

<!-- This entry is open. While 0.4.5 is unpublished, further work is added here
     rather than under a new number. Refresh the date in the heading before
     publishing, and delete this note. -->

### What was wrong

**A check that travels with the package disagreed with itself between Python
versions.** The tool that measures how much of the code the test suite actually
runs asked the compiler whether a file has anything to execute. For a file with
no statements in it at all — the vendored package carries an empty `__init__.py`
— what compiles is an implicit return, and the line it is numbered at is 1 on
Python 3.10 and 0 on 3.11 and later. The tool ignores line 0.

So one empty file was measured on one interpreter and skipped on another, and
the recorded baseline, taken on a newer Python, failed the suite on 3.10 over a
module with no code in it. Anybody running the checks on the oldest Python this
package supports would have met it — the checks travel beside the package and
`scholion doc contributing` describes how to run them. The question is answered
from the source now: no statements, nothing to reach, the same answer
everywhere.

## v0.4.4 — 23.08.2026

This release is mostly about a medical record read from a file: what such a record
holds that is not a laboratory number, and how the product names the codes it could
not place. The rest is about statements being true — a number and the word after it,
the version the local server gives out about itself, what a connectivity check is
allowed to fetch, whether a download checked who answered it, and whether an index
still describes the genome it was built from.

### What you can do now

***The facts the application cannot derive can be given from the page at last.**
Sex, year of birth, height and which wearable answers are preconditions: without
them a dozen reference intervals are withheld rather than guessed, the age-banded
rows of a laboratory form cannot be read, and there is no body-mass index. There
is now a **Profile** tab, and it offers all four. The main wearable had no field
anywhere but the command line.

**The reference panel for percentiles is no longer a question.** It used to be
one: `--ancestry EUR|AFR|EAS|SAS|AMR`, a superpopulation code nobody knows about
themselves in those terms. What such a box collects is a guess, and a guess
stored where a measurement goes is indistinguishable from one afterwards — while
every polygenic percentile depends on it.

Your own genome answers it. Comparing a few hundred of your genotypes against
the five 1000 Genomes panels is a step of preparing a genome, and the result is
used from where that step writes it; the Profile tab shows which panel applies
and says whether it was measured from your DNA or set by hand. Until it has been
determined, percentiles go on naming the default panel they used. The
command-line flag remains as a deliberate override.

Saying there is no wearable is an answer of its own. Until now «I do not own one»
and «nobody asked» were one blank field, so anything listing what the profile
still needs asked a person with no watch about their watch for ever. Choose «No
wearable device» once, or `scholion profile --wearable none`, and it stops.

**What the profile is still missing is now part of what the data cannot answer.**
`scholion limits` already answered one question — what cannot be said here, and
what would close it — and a missing precondition is exactly that. Each one now
appears in that list with the sentence it prevents and the command that records
it, and disappears from it once answered. An assistant reading the list at the
start of a conversation therefore asks for what is actually absent, rather than
from a list somebody typed into an instruction and then had to keep in step.

*A body measurement in a bundle is now kept, not dropped.** This product has
always taken a weight — from the command line and from the page — and an import
that met one inside a medical record threw it away because it is not a
laboratory analyte. It goes to the metrics layer where it belongs, with the same
mark of whose measurement it is as everything else written today. Only where one
of this product's own metrics holds the same quantity IN THE SAME UNIT: nothing
here converts, so a weight in pounds is refused rather than joined to a series in
kilograms. `scholion import-fhir <file>` reports the two layers separately,
because one number for both would say nothing about either.

**Height can be set from the command line at last.** The page has always had the
field; the command had not, and the body-mass index needs it —
`scholion profile --height-cm 178`. A bundle that states a height still does not
apply it: a file may hold a relative or two people, and a height is one field of
the profile rather than a series, so it is reported for you to set yourself.

**A marker may now carry more than one LOINC code**, because a LOINC code is not
one per analyte: the same substance has a different code by material and by
method, and four of that bundle's unplaced observations were analytes this
dictionary knows under a code it does not — glucose in whole blood beside
glucose in plasma, LDL measured directly beside LDL calculated. Every additional
code has to state why the two are the same measurement, and none ships: whole
blood and plasma differ by about a tenth, so pairing them because the names
match would put a systematic error into a series. The mechanism is here; the
pairings wait for a source, and the refusal now prints the code, so each one can
be looked up.

**The suite now says how much of the code it runs, and will not quietly run
less.** A thousand green tests is not a measurement, and this project had been
reading it as one. The number, once taken, was 69.9% — with the module that
implements provenance for every answer at 12.8%, and the VCF reader used whenever
`pysam` is absent, which is most installations, at 35.4%. Nothing could have said
so, because nothing was counting.

`check_test_reach.py`, which travels with the package beside the other checking
tools, counts — on the standard library alone and
including the tests that run the command line in a real subprocess. It reports
per module, `--strict` fails when a module falls below the reach recorded for it,
and `--accept` records a new number deliberately. It is the last step of
`./run_tests.sh`; `SCHOLION_SKIP_REACH=1` skips it while editing.

No module is now under half. Seven that were — polygenic scoring, the provenance
audit, the study loader, the watch import, every route of the local web
interface, the online drug lookup and the VCF reader — carry tests for what they
actually decide: which polygenic model is allowed to speak for a trait, that a
score is not computed for an organ the person does not have, that a stored number
which no report holds is told apart from one that a second method explains, that
a rebuilt watch export cannot erase months it no longer mentions, that a
judgement written about a study survives the file being read again, and that an
empty answer from a database that was never reached is never printed as «nothing
was found».

Nothing about anyone's data changes, and no command behaves differently.

### What was wrong

***A form the interface never showed.** The page holding sex, year of birth and
height existed, worked, and was in no tab: it had never been reachable, in the
whole history of the file, so in practice those facts could only be set from the
command line — while the command's own help said the opposite. Every view the
page defines is now checked for a way in, because a view nobody can open fails no
test that calls its functions directly.

**A recorded age and a recorded sex could both show as «—».** The age was
computed from a year of birth alone, so a profile carrying a full birth date —
which is what the demonstration writes, and what an imported medical record
writes — reported no age at all while the file held one. And the page compared
the stored sex against `male`, while the file is allowed to say `m`; a sex
already given then showed as blank and was asked for again. Both are read
through the one function that knows the spellings.

**A value that cannot mean anything was stored rather than refused.** `--ancestry
EURO` went in, and every polygenic percentile afterwards was computed against a
reference population that does not exist — printed as an ordinary number, and
without the caveat about a default one, because a value was set. Nothing
downstream could tell. Populations, devices and spellings of a sex are now
checked on the way in, by the same lists in every face; an unrecognised value is
refused with what is accepted. A profile field a person did not touch is also no
longer rewritten by a save of a different one.

*«1 markers are printed without a reference range».** A number and the word
after it did not agree — on the screen that says what the data cannot support,
which is the screen this project argues from. The machinery for it existed and
was in use; twenty-three messages simply did not go through it, and in Russian,
where a noun after a number takes three different forms, the same lines read as
carelessness about everything else on them. All twenty-three are repaired, and
the rule that replaces them is mechanical: a message may not put a number
immediately in front of a word unless it carries all the forms of that word. The
page and the package now also agree on which form to choose, checked against
each other rather than each against its author.

**A body weight was reported as a laboratory code nobody knows.** Importing a
FHIR bundle, ten of the twenty-three observations it could not place were not
analytes at all — height, weight, body mass index, temperature, heart rate,
respiratory rate, oxygen saturation. Calling them «a code this build does not
know» sends the reader looking for a dictionary entry that should never exist.
They are named for what they are now, each with the code and, where one of this
product's own metrics holds the same quantity, with that named too — and where
it does not, the reason is written down rather than left as silence: a heart
rate at a visit is not the resting home pulse, and a body-mass-index percentile
against an age-and-sex reference is not the index this product keeps. Nothing is
written from them yet; what changed is that the list of what a bundle held is no
longer misleading. On the same bundle the count of «not in the dictionary» falls
from 23 to 13.

**An observation the dictionary could not place named only its label.** Importing
a FHIR bundle lists what it did not take and why; for a code the dictionary does
not know it printed «Calcium» — while the code, which is the thing an entry is
keyed by and the only way to look the analyte up, sat in the record one line
short of the screen. It is printed now: «Calcium (49765-1)».
`scholion import-fhir <file> --dry-run` shows the list without writing anything.

**A profile with no birth year stopped a whole batch of laboratory forms.**
Reference ranges on a form are often given by age band — one row for 40 to 49,
another for 50 and over — and choosing the row that applies needs the reader's age.
A profile without a birth year is an ordinary state, one the setup warns about and
proceeds from; the comparison was made anyway. `scholion ingest-labs` then failed
on the first form carrying such a row, and the run stopped there rather than
setting that one file aside and going on.

An age that is unknown is not the same claim as an age that fits. An age-banded row
is now neither confirmed nor excluded — the standing a row with no group label has
always had — and where a block offers several of them, the rule this product
already followed takes over: more than one row could apply, so none is taken and
the marker arrives with no reference corridor at all. That is the safe direction
rather than a gap: nothing without a corridor is ever called a deviation here.
Sex is a separate question and still filters rows when the age is unknown.

**The connectivity check accepted an address to fetch, and it should never have
accepted one.** The local server answers a page in your own browser, and any
other page open in that browser can ask it for something. The check that says
«is there internet from here» took the address to try as a parameter. The first
repair made it verify that address — https only, and only the handful of hosts
this product itself talks to — which closed the hole it was written for and left
the shape: a host that is allowed still accepts any path and any query, so an
address could still carry something outward, and a check over a string somebody
else composed is a race with whoever composes the string.

It no longer takes an address. It takes the NAME of a probe, and the address
behind that name is a constant in the source; a name that is not in the table is
refused and nothing is opened. `scholion serve` shows the result in the same
place as before, and the page asks for it the same way — only `?url=` is gone,
replaced by `?target=`, and no caller can name an address again.

**A reference download could stop checking who was answering, and said nothing
about it.** Two of the catalogues this project builds are fetched from public
reference databases: the collection of longevity variants, and the list of genome
positions those variants are read at. When the certificate check failed, both
downloads simply repeated the request without it. Whether a certificate was the
problem at all was decided by reading the wording of the error — so a message
that merely mentions SSL, such as a protocol mismatch or a proxy refusing the
connection, was enough — and nobody was asked for permission. The note written
beside it argued that the archive's own integrity check made this safe; it does
not. That check catches a damaged transfer, not a substituted one.

What could have come of it: a catalogue of variants, or a set of coordinates a
genome is then read at, supplied by somebody other than the database named on it,
and afterwards reported with exactly the confidence the real thing would carry.
Nothing on screen would have looked unusual, which is the whole difficulty with
this class of fault.

Both now refuse. Verification is skipped only when the person allows it out loud
(`SCHOLION_TLS_INSECURE=1`), only when the failure really was a certificate —
decided by the kind of failure, not by its wording — and every request made that
way prints a warning as it is made. This was already how the application's own
lookups behaved; it is now how everything behaves, and a check that reads the
whole source tree refuses any new place that goes back to deciding for itself.

**A genome rebuilt while the application was running could report a variant as
absent.** The reader that answers questions about a variant file without external
tools keeps that file's index in memory. It kept it under the file NAME alone, and
nothing ever discarded it — so a genome re-called and re-indexed while `scholion
serve` was left open went on being read through the previous index. The offsets in
it no longer describe the file, the read lands nowhere useful, and it comes back
with no rows.

No rows is the answer that matters. For a variant file produced the usual way, the
absence of a row at a position means «the same as the reference» — so a stale index
did not produce an error, and did not leave a gap. It produced an ordinary genotype,
stated with the ordinary confidence, at a position that may carry a finding.

The index is now remembered together with the modification time and size of the
index file, so a rebuilt genome is read afresh. Anyone who never rebuilds a genome
under a running interface was never affected, and a command-line run never was: it
starts a new process each time and had nothing to remember.

### What needs recomputing

Nothing, unless a warning about unverified certificates was seen while the
reference catalogues were being built. They are rebuilt by rerunning the build; the
data already in a profile is not affected, because those files are a shared public
reference and hold nobody's measurements.

## v0.4.3 — 22.08.2026

This release is about files that arrive wrapped, laboratory forms printed for an
American reader, and — the larger half — a report that stops claiming more than
the file it was given can support.

### What you can bring it now

**A consumer DNA test still inside whatever the provider wrapped it in.** A VCF
compressed with bzip2, a VCF inside the provider's zip, a VCF whose file name
carries URL-encoded brackets — all of them ordinary VCFs, and all of them now
read. A file is identified by its bytes before its name, so an export that
arrived zipped is no longer «an archive, not opened blind here»: looking inside
is the opposite of blind. None of these can be seeked into, but the catalogue is
fifty-four loci, so one cached pass over the file answers all of them — and the
same pass measures the call set exactly rather than by probe.
`scholion genome-status` names what it found.

**A genotype table from a chip, with the ceiling of the chip attached.** It is
read the same way, and a position nobody typed is reported as not read — never
as the reference.

**Three formats stay named and unread, each with its reason**, because a gap
left unexplained is indistinguishable from an oversight: a VCF that went through
a spreadsheet (its structure is gone rather than hidden — the honest answer is
the original export), a Complete Genomics `var` table (the vendor ships a
converter that is correct by construction, and a second implementation here
would be a worse one), and an archive of the FTDNA era keyed by internal SNP
numbers with no rsID anywhere in it.

**Laboratory forms printed for an American reader.** A LabCorp report prints its
dates as a table — the column headings on one line, the values on the next — and
a reader expecting the label and the date side by side finds neither. The
heading and the line under it are now read, and only while «collected» is the
leftmost date column; where that cannot be established, nothing is read rather
than the wrong column filed. A two-digit year is read. And a page carrying
`12/15/2008` has already said which order it prints in, because there is no
fifteenth month, so `12/10/2008` beside it is the tenth of December and not a
coin toss — the evidence is on the same page, in the same table, from the same
instrument. A page whose dates contradict each other is still refused, and so is
a lone ambiguous date with nothing on the page to settle it. Two weaker
witnesses are used only after the page and are named as what they are:
«Ordered Date», which some lipid panels print instead of a draw date, and the
file name, where a month spelled out is read and a numeric one is not.
`scholion ingest-labs` reports what each file gave.

**An exome or a panel whose header does not say which build it is in.** The
build decides whether the genomic layer may answer at all, and it was
established from the lengths of the chromosomes in the header, or — failing
that — from a variant lying past the end of chromosome 1, which only a GRCh37
file can have. A capture panel has neither: no contig lengths, and no rows out
at the telomere to probe with. Three providers stamp their own pipeline into the
header and build against one reference only, so that signature is now read as
well. Where a pipeline serves both builds, the provider's name alone settles
nothing and is not used on its own: DRAGEN counts only together with the
reference path in the same header. `scholion genome-status` prints which of the
four witnesses answered — a build inferred from who made the file is a weaker
claim than one measured off the file, and it no longer looks the same.

**A WHOOP export.** The zip that arrives by email — or the folder it was
unpacked into — is now read: recovery, day strain, resting heart rate, heart
rate variability, respiration, blood oxygen, skin temperature, sleep with its
stages, sleep debt, consistency and efficiency, and workouts.
`scholion ingest-wearable <folder-or-zip>` takes either device and says which
one it recognised; the Garmin command still does exactly what it did.

WHOOP does not publish the layout of that export, and a layout nobody published
is one that can change without telling anybody, so the column names are read
rather than assumed. Each header is looked up in a table that ships as data, and
a column that is not in the table is **listed by name** with nothing read from
it — an export carrying a column this has never seen says so instead of quietly
dropping a measurement.

**The reader can be named.** Three readers can put a genome through: two
external programs and the one that ships here. Until now whichever was installed
won, which means the same file on two machines was read two different ways with
nothing saying so. `SCHOLION_GENOME_ENGINE=tabixlite scholion genome-status`
pins it — useful for anybody comparing two runs, and the only way to see what
somebody with no external tools installed actually gets. A name that is not one
of the three, or a reader that is not installed, stops the genomic layer and
says which: falling back quietly would answer a different question from the one
asked.

**Two devices no longer become one line.** A Garmin and a WHOOP both report
resting heart rate, heart rate variability, respiration and sleep, and they do
not measure them the same way: different window, different algorithm, different
place on the body. A measurement is now stored together with the device that
made it. Where both measured the same thing both series are shown, neither is
averaged into the other, and no conclusion is drawn from either until the
question is answered — `scholion profile --wearable whoop` names the one that
speaks. For anybody with a single device nothing changes at all. A lifestyle
file written by an earlier version is brought to the new layout when it is read,
and the device it is filed under is taken from what that file says about itself:
a file naming no device is filed as unspecified rather than assigned one.

**Every number says which device measured it.** The strip above the lifestyle
section names the devices in the profile rather than the file they are kept in,
and each metric card carries `measured by …` under the value. Where two devices
report the same thing and none has been named to answer, the page says so at the
top of the section and on each affected card, and offers to settle it in one
click. A column the reader of a WHOOP export does not recognise is listed by
name after every import, and can be named once in
`profile/wearable_metrics.local.json` so the next import reads it — additions
merge per column and cannot delete what already works.

### What was wrong

**Your own measurement joined a fictional person's history without a word.**
The demonstration profile marks itself as invented, and the mark was on the
FILE. Adding a real value to it therefore worked: the point joined a series of
generated numbers, the file went on declaring itself synthetic — by then untrue
— and the overview counted the abnormalities of somebody half imaginary. Every
datum now records whose it is, and one profile holds one person. The first real
value written — by `scholion add-lab`, `scholion add-metric`, `scholion add-med`,
an import, or the same actions on the page — erases the demonstration and says
so, naming every file it removed. Nothing is lost by that: the demonstration is
generated from a fixed seed, so `scholion init --demo --dir <folder>` builds it
again exactly as it was, while a series mixing invented values with measured ones
could not be separated afterwards by anybody. Only data carrying the mark can be
erased, so an ordinary profile — which carries no mark at all — is never
touched.

**A published reference genome could be read under somebody else's laboratory
history.** A genome anybody may look at can be fetched to see the genomic layer
work, and it belongs to a real, consented, published person — not to the reader,
and not to the fictional one of the demonstration. Read beside either it produced
one case out of two people: this genotype, that history, a single report. The
fetched folder now says whose genome it is, and the genomic layer stays silent
while the two are in one profile, naming both sides and the folder to give it
instead. A genome folder that says nothing is still read as before: silence is
not a claim, and every genome anybody already has is unmarked.

**A chip stopped being a chip by arriving as a VCF.** ClinVar findings, the
secondary-findings list and polygenic scores can only be answered from a broad
call set, and the gate that closes them keyed on the CARRIER — a consumer array
file — rather than on what the input actually holds. A genotyping panel
distributed as a VCF (553 197 variants) and a table of chosen positions (48 838)
both went the other way and were told «this has not been annotated yet — run the
preparation», which is an invitation to do the exact thing the gate exists to
prevent. Breadth now decides: a chip, a genotype table, a panel, a low-pass
screen, a mostly-imputed file and half a call set all close those three paths,
whatever they arrived in. An input whose breadth could not be measured closes
them too — refusing a genome that could not be probed costs one command, and
opening a screen that was never measured costs a finding somebody may act on.

**An approximate date stopped looking approximate the moment it was stored.** A
form printing no draw date is read from two weaker witnesses — an «Ordered
Date», which some lipid panels print instead of one, and the file name. That
caveat was printed once, while importing, and afterwards the point sat in the
series indistinguishable from one dated by the draw itself. Every laboratory
point now records which of the three answered for it. Points stored before this
version say «not recorded» rather than claiming a form; `scholion limits` counts
them in one line instead of marking each, and re-running `scholion ingest-labs`
over the original forms fills them in.

**«A whole genome» was printed above files that were not one.** Every readable
VCF used to be described as «a whole genome — every base the sequencing reached,
so both single variants and polygenic scores are computable». Breadth is now
measured rather than assumed: observed variants per megabase through three fixed
intergenic windows, the composition of substitutions against insertions and
deletions, and whether the file carries reference blocks. The thresholds are
calibrated against measured files rather than chosen for roundness — a 30×
whole genome measures 1547–1616 variants per megabase, a genotyping chip shipped
as a VCF 147–452, a low-pass screen 17–81. Where the measurement cannot be made,
the report says so and promises nothing.

Two consequences carry the weight. The FILTER column is now read: a file whose
rows are almost entirely imputed used to have every one of them signed «called
from the VCF» — the output of an imputation model handed over as a measurement.
And a call set split by variant type now refuses a variant it cannot hold: a
file containing only insertions and deletions used to answer `TT (reference)`
for APOE, which is a statement about a person derived from a property of a file.

**`Genome connected. File: None`** — twice wrong in eight words, and it was what
every holder of a chip export saw, while the path to that export sat in the
machine-readable status all along. The status of an array now names the vendor,
the number of positions, the file itself and the ceiling of the chip.

**A refusal printed its own internal label instead of a sentence.** The
commonest question anybody asks of a chip came back as an unreadable string in
brackets. The missing lines are written in both languages, the head of a refusal
can no longer come back as a label, and every value able to reach it is now
walked. That walk immediately turned up one more: a call ambiguous by strand
fell through every branch and vanished, so two DPYD markers — the pair used to
dose chemotherapy — answered «cannot be read».

**«No genome found» on a file that was sitting right there.** Every refusal now
names the file by what is inside it and says what to do with it.

**An answer printed a position from the other build.** A GRCh37 file was read at
GRCh37 positions and printed the catalogue's GRCh38 number, sending the reader
to a base that is not the one that answered. Answer and refusal both name the
coordinate set they were read in.

**A page open in your browser on another site could ask your own Scholion
instance to make an outbound request, and get nothing back but learn whether it
succeeded.** Every route on this server that changes what is stored is already
refused when a foreign page calls it — that is what stops a tab on another site
from quietly editing a profile just because a browser can always reach
`127.0.0.1`. The one route that does not store anything but does make its own
request to the outside — the diagnostic check behind `scholion serve`'s
connection page — was not covered by that refusal, because it answers a plain
`GET` rather than a `POST`, and the check had only ever been wired to `POST`. It
is now refused the same way. Separately, the list of addresses that check is
allowed to reach was being read by scheme and host alone; an allowed address
that itself answered with a redirect was followed wherever it pointed. It no
longer is.

### What is retracted

Anything in this list was produced by an earlier version and should not be
relied on:

- any ClinVar finding, secondary-findings answer or polygenic score computed
  from an input that is not a broad call set — a chip delivered as a VCF, a
  table of chosen positions, a genotyping panel, a low-pass or mostly-imputed
  file, or half a call set;
- any description of an input as a whole genome, where the input was a chip
  export, a low-pass screen or a partial call set;
- any reference genotype returned from a call set that cannot hold that kind of
  variant — most visibly `TT (reference)` for APOE out of a file containing only
  insertions and deletions;
- any row signed «called from the VCF» that came from a file of imputed
  genotypes;
- any position printed against a build other than the one the file was read in.

### What needs recomputing

No stored value changes and the knowledge base is untouched, so series already
on a chart stay comparable. What changed is what can now be read, so:

```
scholion genome-status
scholion overview
```

and, for laboratory PDFs previously refused because no draw date could be found:

```
scholion ingest-labs <folder>
```

### Measured

On a fixed set of thirty-seven third-party inputs, kept unchanged between runs:

| | before | after |
|---|---|---|
| files read and answering | 19 | 24 |
| false «no genome found» | 8 | 0 |
| «a whole genome» claimed on an input that is not one | 7 | 0 |
| `File: None` on a chip export | 12 | 0 |
| internal labels in user-facing text | 6 | 0 |
| laboratory measurements extracted | 126 | 387 |


## v0.4.2 — 20.08.2026

The safety rules now travel with the tools, not only with the skill.

### What you can do now

**`sch_rules` — the rules this product is operated under, as a tool.** A model
that arrives through the skill is handed the instruction and the rules with it. A
model that arrives through the tool interface was handed a list of tools and
nothing else: it knew what it could call and nothing about what it must not say.
Every answer already ends in the one-line disclaimer, and a disclaimer is a
boundary, not an instruction. The rules are now a tool any host can call — 29
tools in total — and the Model Context Protocol handshake carries a digest of
them in the protocol's own `instructions` field, for the hosts that pass it on.
They are the same rules `scholion skill --rules` prints, through a second door.

**A version that is already published cannot be re-published changed.** The build
refuses instead of letting the registry skip the upload in silence: it reads what
actually travels out of the build configuration, compares it against what went
out last time, and stops with «bump the version» when the two differ. Where it
cannot reach the registry to ask, it says so and refuses rather than guessing —
the alternative is a tag pointing at code nobody can install.

### What needs recomputing

Nothing. No stored value changes and no answer changes.

## v0.4.1 — 20.08.2026

An assistant can now ask Scholion how to reach it, and what it must not say — and
gets an answer instead of inventing one.

### What you can do now

**`scholion doc connecting-an-agent`** — how to wire an assistant to this, for
every way in: the command line, the Model Context Protocol server, the Ouroboros
tools module and the Ouroboros Hub skill. It carries the configuration block an
MCP host expects, what to do when the executable is not on the host's `PATH`, how
to point the server at a profile or genome elsewhere on disk, and a two-line
exchange that tests the server by hand with no host at all.

**`scholion capabilities --json` carries an `access` block.** Every way in, the
protocol the server speaks, the number of tools behind it, and the environment
variables this build reads — scanned from its own source, so the list cannot
outlive the code that reads it. The first field is authentication, and it says
there is none.

**There is no account, key, token or credential for any surface of this
product**, and nothing to authenticate against: the analysis runs on the machine
that holds the data, and the Model Context Protocol server is a local process
spoken to over standard input and output — no port, no host, nothing on the other
end of the pipe but the program that started it. That was always true and was
written nowhere a program could read, so a program asked for a credential
instead. It is now the first thing the build answers, and the claim is checked
against the code rather than repeated.

### What was wrong

**The Ouroboros Hub skill described a build that no longer existed.** It declared
version 0.3.2 against 0.4, 23 tools against 28, and did not mention the Model
Context Protocol server at all — so a host that read only that file saw a
Scholion without it, and an assistant working from that description had no way to
reach a surface that was sitting there. The version and the tool count are now
written from the build rather than typed beside it, the same way the shipped
documents and the assistant rules already are.

**The model's instruction named the protocol and not the way to speak it.** It
listed `scholion mcp` and stopped. It now points at the connection guide.

**The local web page was not marked as being for a person.** `scholion serve`
opens a page on `127.0.0.1` for someone to read. It is listed among the ways in
and listed as human: an agent that finds an undescribed local page will try to
drive it, and a door that is not for you is a fact worth stating, like any other
refusal.

### What needs recomputing

Nothing. No stored value changes and no answer changes.

## v0.4.0 — 19.08.2026

This release is about the files people actually have. A consumer DNA test, a
genome in the older GRCh37 build, a hospital portal export, laboratory results as
a spreadsheet — all of them are now read, where most of them used to be answered
with «no genome found» or «nothing importable here».

The second half is what the answers say about themselves: how much of a gene was
actually read before «no findings» was printed, which sample in a multi-sample
file was used, and — where an answer cannot honestly be given — which of several
different reasons is the one that applies.

### What you can bring it now

**A consumer DNA test — 23andMe, AncestryDNA, MyHeritage, FamilyTreeDNA, Living
DNA.** This is the most common genetic file in the world and Scholion used to
answer «no genome» to all of it. It is now a first-class input, including when it
is still inside the `.zip` or `.gz` the provider sent. On a 23andMe v5 export, 46
of the 54 catalogue positions are present — APOE ε-status included, so the
headline genomic answers work without a sequenced genome. Every position answers
one of three things: read, attempted and not called, or not on this chip at all —
because «not on the chip» and «you do not carry it» are different sentences.
Six positions whose two strands are ambiguous are named separately instead of
being handed over with the rest, and the things a chip cannot support — ClinVar
screening, secondary findings, polygenic scores — are refused with the reason.

**A genome in the older GRCh37 build.** Most files people actually hold are
GRCh37: consumer chips, several sequencing providers, and most whole genomes more
than a few years old.
Scholion used to switch its genomic layer off on every one of them. All 54
catalogue positions now carry coordinates in both builds — each one taken from
two independent public sources that agreed — so a GRCh37 file is read at GRCh37
coordinates. Nothing is converted between builds: the offset is not constant even
inside one chromosome, so arithmetic would return a plausible position pointing at
the wrong base.

**Laboratory results from a health portal or an app.** `scholion import-fhir`
reads a FHIR R4 bundle — a patient-portal download, Apple Health clinical
records, an EHR export. Analytes are matched by their LOINC code rather than by
the name a hospital happened to print, and units go through the same gate as
everything else. The bundle names a patient; Scholion reports who it says and
does not act on it.

**Lab results as a spreadsheet.** CSV, TSV and plain text exports are read, not
just PDFs. In a table each row carries its own date, which is how these files
actually work — and which is why they used to import as one date for the whole
sheet, or not at all.

**American forms.** Dates written `03/14/2015` or `March 14, 2015` are read. When
a date is genuinely ambiguous — `07/12/2015` is either July 12th or December 7th
— it is refused by name rather than guessed at, because a mis-dated point silently
reorders a seven-year trend.

### What the answers tell you that they did not before

**«No secondary findings» now says how much was read.** The ACMG list of 84
actionable genes is only as good as the coverage underneath it, and that number
had been computed and printed elsewhere for months without reaching this
sentence. A negative over a gene read at 62 % is now qualified as one.

**Sex-specific thresholds.** «Three times the upper limit of normal» is published
as a pair of numbers, one for each sex. Scholion had stored only the product,
computed from the male bound — so a woman on a statin with ALT 110 or CK 520 got
nothing, in both cases in the dangerous direction. The rule is stored now and the
number computed from it. Where sex is not recorded, the more cautious bound is
used and said so.

**Star-allele diplotypes are used where they exist.** If a proper pharmacogenetic
call is in your profile — from PyPGx over a BAM, with copy number and phasing —
it now decides the phenotype, instead of the answer being reconstructed from
individual tag SNPs. `CYP2C19 *2/*17` means something a pair of SNPs cannot.

**Polygenic scores say what they cannot do**, and a percentile about an organ you
do not have is withheld and named rather than quietly printed. A low-confidence
ClinVar hit now carries how strongly it is reviewed — a single-submitter
«Pathogenic» and an expert-panel one are not the same claim.

**`scholion flag-rate`** answers a question the documentation had been describing
for a while: how often does this tool raise this flag at all? A rule that fires
on everybody is not information.

### What it now refuses to do

Four situations used to produce a confident answer where no answer was
available. Each is now a refusal that names the file and the reason.

**A file it cannot actually open is no longer «Genome connected».** A `.vcf.gz`
compressed with ordinary gzip rather than bgzip looks correct from the outside
and cannot be read at all. Every position in it came back «reference» — including
a heterozygous APOE ε4 carrier, reported as a non-carrier. The same applies to a
missing, truncated, or previously unsupported `.csi` index. Scholion now names
the file, prints the one command that fixes it, and answers nothing until it is.

**A folder holding several genomes.** It used to read whichever filename sorted
first. A genome split across `chr1.vcf.gz` … `chr22.vcf.gz` therefore answered
APOE — which is on chromosome 19 — out of chromosome 1, as «reference», while the
right file sat unopened beside it. A folder holding two people answered about
whoever came earlier in the alphabet. Both now list the files and ask
(`SCHOLION_GENOME_VCF`).

**A file holding several samples.** A trio or a family file puts several people
side by side, and the first column belongs to whoever the laboratory listed
first — possibly a relative. `SCHOLION_GENOME_SAMPLE` says which one is yours,
and until it does, nothing is read.

**A file whose reference build cannot be established.** A position looked up in
the wrong coordinate system comes back empty for exactly the same reason a
position with no variant does. That silence is no longer reported as «reference».

And when the folder holds a BAM, a CRAM, a FASTQ pair, a BCF, a gVCF or a
provider archive, each is named by what it is with the next step for that kind of
file — instead of the same «the full VCF is not connected» that eleven different
formats used to print at people whose file was lying right there.

### Also new

* **`scholion mcp`** — Scholion as a Model Context Protocol server over standard
  input and output, so any MCP-capable assistant can call the same tools the
  Ouroboros plugin exposes.
* **`SCHOLION_GENOME_VCF` and `SCHOLION_GENOME_SAMPLE`** — which file, and which
  sample inside it, is yours. `scholion genome-status --json` reports the sample
  name, how many samples the file holds, how many genome files were found, and
  the reason it is refusing when it refuses.
* **The numbers behind the flags are written down.** Four thresholds that no
  published guideline fixes — how large a change counts as movement, how close to
  a reference limit counts as near it, and two more — are now stated in the
  knowledge base with what would replace them and, more usefully, what they do
  not license anyone to conclude.

### A series break

Values computed before and after this version can differ on unchanged input, in
six places: sex-specific decision thresholds (ALT and CK on a statin),
star-allele diplotypes that were on disk and unread, the ClinVar
review-confidence note, polygenic traits withheld for sex, lab points imported
from tables and FHIR bundles that were previously skipped, and every genomic
answer from a GRCh37 file. Do not put values from either side of this line on one
chart without a note.

### What is retracted

* **Any earlier «no reportable findings» read as unqualified.** It never was: it
  was a statement about what had been read, and now it says so.
* **Any lab flag on ALT or CK for a woman, or for a person whose sex was not
  recorded.** The thresholds were male.
* **«This position is not on the array»** for a consumer export that had been
  opened and re-saved in a spreadsheet. The file parsed to zero rows, and our
  failure to read it was reported as a fact about the chip.
* **Any report that claimed a folder held nothing importable** when it held CSV,
  TSV or TXT: the search looked only for PDFs.
* **Any genomic answer out of a `.vcf.gz` that was not block-compressed**, or
  whose index was missing, truncated or `.csi`. It was not reference; it was
  unread.
* **Any genomic answer from a folder holding several genomes**, or from a
  multi-sample file where the sample was never named. Which person it was about
  was decided by sort order.
* **Any «reference» from a file whose build was never established.**

### What needs recomputing

* `scholion labs` and `scholion overview` — the sex-dependent thresholds.
* `scholion drug <name>` for CYP2D6, CYP2C19, CYP2C9, DPYD, TPMT, NUDT15,
  SLCO1B1 and the rest of the eighteen, if a star-allele table or a called
  diplotype is in the profile.
* `scholion acmg` — the report now carries coverage.
* `scholion prs` — sex-specific traits are withheld and the method caveats are
  printed.
* `scholion ingest-labs` on any folder holding non-PDF files, and on any American
  form.
* `scholion genome` and everything downstream of it, on a GRCh37 file, on a
  consumer array, on a multi-sample file, on a folder with several genomes, or on
  a file that was never actually readable.

### Measured

Twenty-eight input shapes — the zoo of formats real providers hand out — run
through the previous release and this one:

| | v0.3.4 | this release |
|---|---|---|
| **Confidently wrong answers** | **8** | **0** |
| False «no genome found» | 14 | 0 |
| Correct | 6 | 27 |
| Answers nothing, but still says «connected» | 0 | 1 |

The remaining one is a genome whose reference build cannot be determined from the
file: the first line still says «Genome connected» before it says the build is
unknown, though every position in it now refuses.

And on real files rather than invented ones — 31 sets of genomic and medical
records from the Personal Genome Project, whose participants publish their data
under open consent. No participant's data, findings or identifiers appear here or
anywhere else in this repository; these are counts of what the software did.

| | v0.3.4 | this release |
|---|---|---|
| **Confidently wrong answers** | 1 | **0** |
| Consumer arrays read | 3 | **9** |
| Genomes turned away over their reference build | 7 | **0** |
| False «no genome found» | 11 | 7 |
| **Laboratory results imported** | 0 | **61** |

The last row is the one that matters most: the laboratory side now fills up from
records it has never seen before, which is the precondition for everything this
tool does across layers. On one of those sets a lipid panel showed dyslipidaemia,
the tool concluded that statin therapy was likely, and named the one gene worth
testing **before** it starts. On another, a single raised rheumatoid factor
produced two suggested tests and a sentence saying why one result is not a
diagnosis.

### Thanks

* **Personal Genome Project (Harvard)** and its participants, whose open-consent
  data made it possible to test this on 27 real files from eleven providers
  without a single user. Almost everything in this release was found there. No
  participant's data, findings or identifiers are redistributed here in any form.
* **Synthea** (synthetichealth/synthea, Apache-2.0) for the synthetic FHIR bundle
  the import is tested against — a parser tested only on input written by whoever
  wrote the parser passes its own tests and fails on the world.
* **Genomi** (exon-research/genomi, Apache-2.0) for the input-format detector,
  vendored with a way to update it.

## v0.3.4 — 19.08.2026

The release for the person we are about to invite: someone with their own
medical files and no terminal habits. Four changes, assembled under one tag
(an earlier v0.3.4 tag existed locally and was never published; it was
re-cut onto this state — nobody could have installed the intermediate one).
No knowledge changes, no series break.

### The skill becomes a download, not a build step

The published page used to explain the «no terminal» path with a terminal
command — `python3 src/tools/make_skill_package.py` — which is the joke
telling itself. Now the page CARRIES the skill: `scholion-skill.md` (the
entry — one file to attach to a chat with Claude or ChatGPT and say «set
this up») and `scholion.skill` (the full bundle with the reference texts and
the safety rules) are generated by `make_shareable.py` at build time, from
the same sources every other step uses, so the page can never serve a stale
skill. Both presentation cards and the README's skill section now lead with
the download and keep the build-it-yourself route for people with the source
tree. What does not change: the model gets no access to the machine, the
profile never leaves it, and the safety rules take precedence over every
other instruction the model is given.

### A genome that cannot be read is named, not reported as missing

Found by walking the invited person's path. A plain `.vcf` — the shape
providers hand out routinely — was invisible to the reader, and the person
with their genome sitting in the folder was told «The full VCF is not
connected», word for word the message shown to someone with no genome at
all. A `.vcf.gz` compressed with ordinary gzip instead of bgzip was quieter
and worse: it looks right, is not, and the tools' own error explains nothing
to someone who never heard there were two gzips. Now `genome.unusable_nearby()`
names the file, names the reason, and prints the exact command that fixes it
— in the status, in `limits`, and in the genome guide, with the model's
instruction taught the same. One person, one folder, one command — instead
of a wall described as an empty room.

### The easiest way in moves to the top of the page

The download-and-attach path lived in the installation section — at the
bottom of a long page, where a person with no terminal habits arrives
already tired. Now it is the first thing after the title: one button
(download the skill file), one sentence (attach it to Claude or ChatGPT,
say «set this up»), one line of what never changes — the data stays on the
machine, the safety rules outrank everything. The full installation section
stays where it was, for the readers who want the whole inventory.

### The plugin gains its OuroborosHub form

The Hub's contract is skills/<slug>/ with SKILL.md frontmatter and a
plugin.py exposing register(api) against the frozen PluginAPI ABI — not the
classic tools-module this project has carried. `ouroboros_plugin/hub/scholion/`
now holds both files; plugin.py is an adapter over the pip package's own
`get_tools()`, so the Hub skill cannot drift from the product. Verified
against the host's own code: manifest parser, install_specs normalization,
23 tools inside the 24-character name limit, end-to-end answers on a demo
profile, and a clean catalog entry from the Hub's build_catalog.py.
Submission to the catalog is the owner's fork-and-PR; the reviewed source
lives here.

## v0.3.3 — 19.08.2026

The release where the project explains itself twice over: to a visitor, and
to a contributor. No knowledge changes, no series break; the analysis answers
exactly what v0.3.2 answered.

### The presentation catches up with the product, and gets a front door

`share/presentation.html` and `share/presentation.ru.html` are rebuilt
against the living 0.3.2 — checked by running the product, not by memory:
553 tests, 48 commands, the Assistant tab's self-audit at 39 files / 18,194
lines (read from `_audit_core()` directly, not off a screenshot), six
outbound hosts by name. All screenshots are fresh, a tenth was added (the
Guide tab), and the Russian edition carries REAL Russian screenshots for the
first time — the apologetic note about English ones is gone. An Installation
section now mirrors the README's four ways in, and says plainly that the
genome-preparation workshop lives in the source tree only. Two wordings were
corrected on the way: «not one external dependency» (pdfplumber is required)
and the locality card now names the translation services next to the
reference APIs, because the application's own self-report does.

The pages get an entry point: `share/index.html` redirects to the
presentation (with a manual fallback naming both languages) and
`share/.nojekyll` keeps GitHub Pages from mangling the folder. The publish
gate carries both into the built package's `docs/`, so
`crossread.github.io/scholion` starts answering at the root instead of 404.
The screenshot allowlist in `make_shareable.py` was replaced wholesale —
twenty hashes, ten per language — following the file's own precedent. One
accepted line joins the language baseline: the «Russian» link label on the
entry page is a language switch, which is the one place a language's own
name belongs.

### The conventions get a file, and the split gets a gate

`docs/DEVELOPMENT.md` — the architecture and the development rules, written
for an outside contributor to assemble a structured commit without reading
the tests first: the layer map, the engine-package rules, the four-face
tick, language and i18n discipline, the gate order, what a commit message
carries, and short checklists for the common additions. An early audit cited
a DEVELOPMENT.md that did not exist; the citation is now true.

`tests/test_engine_stays_split.py` holds the refactoring's shape the way the
four faces are held — as a red test, not a memory: the facade defines
nothing; domain imports stay acyclic at the top level (the one sanctioned
back edge is lazy inside a function, which is exactly what makes it
sanctioned); every module has a size budget recorded in the test, and
exceeding it is a same-commit decision — split, or raise the budget with a
reason about the capability; the facade may not shrink below the hundred
names the flat file exposed. Seven mutations were tried against the gate;
seven came back red.

## v0.3.2 — 18.08.2026

A refactoring release: not one answer changes on unchanged input. The full
suite, the compatibility snapshots, both language catalogues and every command
are byte-for-byte the same claims as v0.3.1 — that sameness IS the release
gate, recorded here as the thing that was checked rather than assumed.

### engine.py becomes a package of eight domain modules

The 2800-line flat file — five domains that had grown into one another for a
year — is now `engine/`: `_helpers`, `labs`, `pgx`, `genomics`, `goals`,
`lifestyle`, `sources`, `profile_view`, with `__init__.py` as a facade that
re-exports EVERY name, private ones included, at the address the tree has
always used. Six consumers (`__init__`, `cli`, `server`, `ouroboros_tools`,
`assistant`, `limits`) and the tests needed zero edits: five of the six always
called `engine.<name>(...)`, and the sixth's explicit imports resolve through
the facade identically. Two module names differ from the auditor's proposal
for a reason recorded in the plan: `genomics` (a `genome.py` already exists —
the VCF backend) and `sources` (a `provenance.py` already exists and means the
reverse check; `engine.provenance()` keeps its public name, only its file
changed).

The mechanical work was governed by a call-graph analysis the original audit
did not do, and the graph had teeth: two cycles (labs↔pgx and lifestyle↔pgx).
They were broken by MOVING two leaves into `_helpers` — `_active_names_by_class`
and `_brief_num` invoke nothing and belong to everyone — and by ONE deliberate
lazy import: `pgx._dose_context` reaches for `lifestyle._brief_life` inside
the function body, the same pattern the file already used for `drugsource`.
Everything else imports one way, top-level, two dots up for the package
neighbours exactly as the plan required.

The extraction tool refused to write a module with an unresolved name, and
that refusal caught three edges no analysis had listed: `DISCLAIMER` is called
by `goals` and `genomics` (the call-graph pass had skipped the two constant-
like functions), and `_OPS` — the comparison-operator table — is shared by
`_helpers._match_count` and `labs._eval_condition`. All three now live in
`_helpers`, imported by name where used. The audit's other prediction was
confirmed the hard way: `_WATCHLIST` sits in `profile_view`'s line range and
belongs to `lifestyle.second_opinion` — cutting by line ranges would have
shipped a NameError that only fires when somebody asks for a second opinion.

One collision existed and is now tested: `lifestyle` is both a submodule and a
function. The facade binds the function last, and a test-adjacent check
confirms `engine.lifestyle` stays callable even after a direct submodule
import.

### Removed: the monitoring list nobody calls

`_monitoring_for` returned monitoring hints for eight drug classes hard-coded
in the source, through sixteen `monitor.*` keys in both catalogues. The only
place needing such hints — `check_new_prescription` — has long read them from
`knowledge/drug_lab_monitoring.json` via `core.drug_lab_monitoring()`. The
code list lost that argument and stayed anyway; found by the refactoring
audit, deleted with its keys (catalogues stay identical: 1334 = 1334).

### What was checked, where

`run_tests.sh` end to end in the repository: 553 tests, 48 commands, 20
snapshots, docs and rules in sync, the language remainder unchanged at 352
(the seven accepted places that lived in `engine.py` moved to their new
addresses; the baseline records the move, not growth). And — because a check
that agrees only with the repository it was written in has now cost this
project five times — the artefact itself: a wheel built from this tree,
installed into a clean environment, imports the facade, resolves the private
names the tests use, and answers `scholion capabilities` and
`scholion second-opinion` from the installed package. All nine `engine/`
files travel in the wheel.

## v0.3.1 — 18.08.2026

_MINOR by the letter of `docs/VERSIONING.md`: `lab_markers.json` changes what a
value means on unchanged input — an HbA1c that used to be refused is now stored.
Nothing already stored moves; a refusal has no stored value to move._

_Backlog 36 and 41, and the answer to both was mostly «check before you build»._

### What this changes in the conclusions

**HbA1c in mmol/mol is read now instead of refused.** The IFCC scale and the
NGSP scale are related by the master equation `% = 0.09148 × mmol/mol + 2.152` —
affine, not proportional — and the gateway had one law: a multiplier per spelling.
Refusing was the honest answer while that was the only tool, and it was also a
refusal of the commonest unit on a European report. A person met «unknown unit»
about a unit that plainly exists, went looking for a typo, found none, and typed
the number bare — the outcome the refusal existed to prevent.

The gateway carries a second law: `convert_affine`, with the constants and the
NGSP citation beside them. 48 mmol/mol comes out as 6.5 %, which is what the
published table says, and the test checks the table rather than the arithmetic.

**The corridor travels with the value, by the same law.** A range printed in
mmol/mol beside a value converted to % is the mg/dL-glucose defect one level
down, and with an affine law a bound multiplied instead of transformed lands
somewhere else entirely. Both ends now go through the conversion, and a test
adds a value inside its own corridor and checks it is not flagged.

**Nothing converts on its own any more.** The arithmetic used to live in the
caller. That was safe with one law and dangerous with two: a caller reading only
`factor` would apply 1.0 to 48 mmol/mol and store 48 % — not an error, a
catastrophic diabetic reading, silently. `core.convert_to_canonical` is the one
place the law lives, both entry points go through it, and a test refuses any
module that multiplies by the gateway's factor itself. Verified by putting the
multiplication back and watching two tests go red.

**Lp(a) in mg/dL stays refused,** and that is what keeps the refusal path
honest. Mass and molar concentration there depend on the size of the person's
apo(a) isoform: no factor, no formula, and a second law is not a licence to
convert everything.

### What was already done, and is now closed by checking rather than by memory

**Task 41 — the test matrix — was already in the tree.** `tests.yml` runs
ubuntu × macOS against Python 3.10, 3.11, 3.12 and 3.13 with `fail-fast: false`,
plus a Linux job with `TMPDIR` behind a symlink (the macOS `/var` →
`/private/var` shape, reproduced where it is cheap), plus the package job. The
backlog line said «not started» as of 16.08 and was two days stale. It is closed
with what proves it: the file, the cells it declares, and a green run on GitHub.

**Task 36 was five-sevenths done and the entry knew it.** The five factor
conversions — free T4, free T3, TIBC, zinc, DHT — shipped earlier, each with its
molar mass written next to the constant. What remained were the two the entry
itself called hard, and they turned out to be one piece of work and one correct
refusal, which is the paragraph above.

### The frame: one capability, four faces, one tick

`contract.py` opens by naming three faces of one core and describes the defect it
was written after — «Second opinion», the summary and the health index living in
the web tabs alone for half a year, because a capability added quickly to one
face stays there. It closed the first two faces against each other and left the
others open, and both drifted.

There are four doors, not two, and they are not equal:

| | who walks through it | who notices it is shut |
|---|---|---|
| web interface | a person clicking | the person — a missing tab is visible |
| command line | a MODEL with a shell, first; a person typing, second | the person — the model works from what it was told exists |
| plugin tool list | a model deciding what it can call | **nobody** |
| the model's instruction | a model deciding what exists at all | **nobody** |

A person can see that something is absent and go looking. A model cannot see a
capability it was never shown: it answers from what it has instead of saying it
cannot, and that answer looks exactly like a good one. So the two model-facing
doors now carry the higher bar — an omission must be written down with a reason,
and the reason must be about the capability rather than about the week.

**Measured before the guard was written**, which is the only reason to trust that
it was needed: the plugin lacked nine capabilities (see above), and the shared
instruction named 40 commands of 47. Three of the seven absent were real —
`acmg`, `goal-suggest`, `lipid-genetics` — and two of the three had been added
that same week. Each of those two drifts had been found by somebody noticing
months later, not by a test.

`check_all_faces()` answers for all four at once, and `tests/test_all_faces_move_
together.py` prints them in one message. That is deliberate: the question an
author has after adding something is «what did I forget», and four separate red
runs answer it a quarter at a time — a run per face, a fix per run, and the
fourth found an hour later.

The fourth face is CHECKED and not generated. The command block in the
instruction carries curated invocations — `genome rs0000000`, `phenoage
--panels`, `tools --set NAME` — worth more to a reader than a line per bare
command, and a generator would flatten them. What must not happen is silent
absence, and that is what is now impossible.

A fifth check went in beside them, of a different kind: every phrase the
interface reaches for exists in **both** catalogues. A missing key does not
crash — the page prints `⟦web.some.key⟧` where a sentence should be, in front of
the reader and nowhere else, in only the language that lacks it, so it is
invisible to whoever wrote the other one.

**The guard's first catch was its author.** `init` was excused as «not named in
the instruction» and is named there; the excuse was wrong and the check said so
on the first run. Its second was a stale sentence in both instruction editions
telling a model that HbA1c in mmol/mol is refused — true until earlier the same
day, and exactly the sort of statement that outlives the thing it describes.

**The command line was misnamed in the first draft of this table.** It said «a
person typing, every script» — and the owner corrected it: the CLI's
completeness is noticed not only by a person but by the AI agent that works
with Scholion as a tool, and the CLI is for that agent first. A person can
browse `--help`; a model with a shell runs what its instruction names and
nothing else — the instruction is the discovery mechanism of the main surface.
That correction forced two things that were not in the plan.

The first is a second route to the truth: `scholion capabilities` (also
`--json`) — a manifest GENERATED from the command parser and the entry-point
map, listing every command, what it does, whether it writes, and which faces
carry it. The instruction now ends its command list with the rule «if this
list and the build disagree, believe the build». A curated instruction can go
stale — this release found it stale twice — so the model gets one door that
cannot: the build describing itself.

The second the new gate class found on its own first run
(`TestTheManifestCannotFallBehindTheBuild`): the claim «no tool handed to a
model writes», printed in the writes heading and asserted from a hand-written
list, had been false from the beginning — `sch_ingest_labs` is a tool and
writes `labs.json`. The earlier test happened not to contain the one command
that broke its premise: a check agreeing with its author, the same class that
has cost this project four times. The fix is a distinction, not a deletion:
WRITES splits into AUTHORS (creates values from nobody's document — `add-lab`,
`add-med`, `demo`… — never a model's tool) and TRANSCRIBES (moves the person's
own documents into the profile — `ingest-labs`, `ingest-garmin`… — a model may
hold these, because they invent nothing). The manifest marks every write with
its kind, the gate holds AUTHORS out of the tool list by name, and every
transcriber must be recorded as admitted or refused — silence is the one state
the contract no longer allows.

**And the manifest's own reader carried the disease it was built against.**
`instruction_text()` read the instruction at its source-repository address
alone, passed every test in the repository it was written in, and failed inside
the built package on the owner's publish run — the package does not carry
`share/`, it carries the identical copy beside the module. A check agreeing
with the single environment its author sat in: the same class, caught by the
publish gate doing exactly what it is for — nothing was committed or pushed to
the public repository. The function now knows both homes and says so when it
finds neither.

### The third face of the core had fallen behind, and nothing was watching it

`contract.py` opens by naming three faces of one core — the web interface, the
CLI and the Ouroboros plugin — and by describing the defect it was written after:
«Second opinion», the summary and the health index by body system lived only in
the web tabs for half a year, because a capability added quickly to one face
stays there. The map it enforces covered two faces of the three.

So the plugin drifted exactly the way the web had. Nine capabilities had a route
and a command and no tool: the overview, the second opinion, the radar, the
focus, the lifestyle brief, the ACMG scan, the two added this week — and
`limits`, which is the answer to «what can this data NOT tell you».

`limits` is the one that matters. The reader who needs it most is a language
model about to make a negative statement, and it was the one face that could not
ask for it. A missing tool is worse than a missing tab for a reason worth
stating: a person looking at a page can see that something is absent. A model
cannot see a capability it was never shown — it answers from what it has instead
of saying it cannot.

Fourteen tools became twenty-three, each checked by calling it. `PLUGIN` maps
command → tool and `NO_PLUGIN` records a reason for every command that has none,
and the bar there is deliberately higher than for the web. Every write command is
in that list marked «a write», with a test that keeps it so: the canon handed to
a model says it does not change the profile, and the absence of a write tool is
what makes that more than a promise.

### The seven small things the stranger's run left behind

None of them changes an answer; all seven were things a reader had to work
around.

**Labs listed twenty-seven markers alphabetically under a heading that said
«8 out of range of 27».** The eight the sentence was about were scattered among
the nineteen it was not, and counting them by eye was work the page could have
done. Out of range first, furthest outside its corridor leading, then a divider
and the rest in the order they had.

**Overview came to 11 400 px on a 390 px screen** — the goal board is most of
that, and the four numbers a reader opens the page for sat underneath it. The
board folds on a narrow screen and stays open on a wide one: 5 200 px now, one
tap instead of a minute of scrolling. Built with `<details>` rather than a
script, so it survives a half-loaded page and a screen reader already knows how
to announce it.

**Polygenic scores sat a centimetre below «Full genome (VCF): no data».** Both
true — a score is a stored result, computed once from a file that need not still
be attached — and read as a contradiction with no way to tell which half to
believe. The block now says when it was computed and that the file is not
attached now.

**The disclaimer was printed four times on one screen** and after the fourth it
reads as legal cover rather than as care. It was repeated for a real reason:
Overview is thousands of pixels tall and the header scrolled away. The header is
pinned now, which answers the reason instead of arguing with it, and the copy
inside the focus card is gone.

**«P94», a phenotype code and a confidence mark carried no explanation** where a
reader first meets them; the Guide has all three, a tab away. They now carry the
Guide's own wording as a tooltip — the Guide's, not a second text written beside
them, because two texts for one term drift and the one on the badge is the one
nobody maintains.

**A traceback in the middle of the release log.** `test_server_guard.py` provokes
a failure to prove the server does not leak a filesystem path into an HTTP
response; the server prints the details to the owner's console, which is the
other half of that design. Read as a crash three times in one day. Swallowed in
the test that causes it — and the test now also asserts the traceback still
reaches the console, because silencing it in the server would delete half the
guard.

**One tool description still described the owner's shelf** («from Garmin
wearables and smart scales») in text written for every profile.

### Also

`LICENSE-DATA` attributed the knowledge base to `https://scholion.dev`, which
does not exist. It points at the repository now. The edit arrived in the built
package rather than the source tree, where the next publication would have wiped
it without a word — the hazard the two-repository model carries, and worth
recording next to the fix.


#### Also, on the unit gateway

`tests/test_unit_gate_second_law.py`. Among its assertions: that the published
pairs do NOT share a ratio — which is the reason the second law has to exist at
all, stated as something that fails if it ever stops being true.

---

## v0.3.0 — 18.08.2026

_Tagged three times before it left the building. `v0.3.0` and `v0.3.1` were pushed
to GitHub and rejected by PyPI — see «the metadata line» below — so neither was
ever installable, and both tags were withdrawn rather than left standing as
versions nobody could get. What follows is everything those three tags contained,
under the number the release was always meant to carry. If you have a checkout
pinned to `v0.3.1`, it is gone; `v0.3.0` is the same code and more._

_MINOR, and a **series break** in two places. `test_rules.json` rewrote three
rules, so a suggestion list printed before this version and one printed after it
are not the same document even from an unchanged profile. `loci.json` and
`longevity_directions.json` gained PCSK9, so a genome that resolved nothing there
now resolves four positions. Separately, a profile carrying BOTH a laboratory
report and a VCF can answer differently at a position where the two disagree: the
reads win now, and the disagreement is printed._

_Written from a run of the product as a stranger: the package built by
`make_shareable.py`, installed with `pip install` into a clean machine, opened in
a browser as two people — one with the demo, one an hour after installing with
nothing loaded — and read by three reviewers with no knowledge of the project. The
findings are theirs; what follows is what was done about them._

### What this changes in the conclusions

**A new profile no longer says anything about the person who created it.** Every
file `scholion init` laid down carried data: one triglyceride measurement dated
2024-01, one prescription, a sex, a year of birth and a height. A minute after
installing — before loading anything — the first screen counted «0 red flags over
the last 12 months», the labs tab showed a value flagged «within range» with a
date on it, and the header counted a prescription. Both readers who met that state
said they would have repeated those numbers to a doctor. The templates now ship
empty, and each one says in `_meta.why_empty` that the emptiness is a decision.
`metrics.json` no longer assigns a sex, a birth year or a height: the panels that
need them refuse until they are filled in, which is the correct answer.

**The suggestion rules stopped asserting facts about the reader.** The CYP2C9
rule fires for anyone whose CYP2C9 is unread — that is, for everyone new — and its
reason read «Together with the **already known VKORC1**…». True of exactly one
profile, the one it was written on. The APOE rule justified a test with «a goal of
the project». Both rewritten. «Track 2», the project's internal name for the
FASTQ→VCF pipeline, left the three rules it appeared in: every reviewer stopped on
it, and a clinician read «The CYP2C9 genotype (\*2/\*3) — through Track 2» as the
patient's genotype rather than as a test being suggested.

**Direction stopped being read as severity.** The first screen split current
abnormalities into «red flags» (above a ceiling) and «under observation» (below a
floor), which made a ferritin of 13 against a floor of 20 the milder of the two —
while the same screen's focus card was about that ferritin. The block now shows
every current abnormality in one list; the two counts remain, labelled as the
directions they are, with a line saying how the four numbers relate.

**The pharmacogenetic section says how much of it is about you.** With no
genotypes on file the section is not empty — every watch-list drug comes back with
the general rule printed in place of a statement about the person — so it now
opens with «K of N could be judged from the genotypes on file», and each row shows
the phenotype LABEL (`ultrarapid metaboliser — ASSUMED, not every marker was
read`) instead of the machine code (`UM`, `normal_sensitivity`).

### What is retracted

**The command for installing the skill never worked for anybody but the owner, and
would have leaked his key if it had.** The «Assistant» tab built the path as
`REPO/src/skill/INSTRUCTION.owner.md`. `REPO` is the repository root only in a
source checkout — after `pip install` it is the parent of site-packages, naming
nothing — and `INSTRUCTION.owner.md` never ships, so every installed copy showed
«not found» and then printed a symlink command into empty space. In a checkout the
path did resolve, and it pointed at `src/skill/`, which holds the owner's 117 KB
clinical key: following it would have symlinked that key into `~/.claude/skills`
for a model to read. The entry now names the packaged skill directory, prints no
command when there is nothing to point at, and a test asserts that whatever
directory it names carries no `*.owner.*` file — the assertion that fails on the
owner's own machine, which the path-exists version did not.

**Four places sent the reader to scripts that are not in the package.**
`call_full_vcf.sh`, `annotate_clinvar.sh`, `acmg_sf_scan.py`,
`loci_sites_bed.py` — all of `src/ingest/`, none of it shipped. They now point at
`scholion doc preparing-the-genome`, which travels with the package.

**The version in the header was a changelog line frozen in 2026-07.** `server.py`
kept `VERSION = "2026-07-30 · radar dynamics + tab freshness"` by hand while the
package was 0.2.2. It reads the package version now, and a test ties the two
together.

### What needs recomputing

Nothing stored changes value. Suggestion lists and second-opinion sheets printed
before this version carry the retracted wording and should be reprinted if they
are still in circulation.

### Also

- The demo announces itself on every screen — an amber band saying it is a
  fictional person. Before, the only sign was «DEMO-0001» in the header, which
  reads like a laboratory accession number.
- «Guide» moved from tenth tab to second. It answers most of what a newcomer asks
  and was being handed over at the end of the journey.
- A print stylesheet: the navigation, the source chips, the language switch and
  the cross-tab links are stripped, and the sheet gains a header with fields for a
  name, a date of birth and a date — the first thing a general practitioner said
  was missing — and a footer saying where the numbers came from.
- Empty chart frames replaced by a line saying no series exists yet. Three framed
  rectangles with headings and nothing in them read as broken, not as empty.
- `scholion init` names the first useful command for whatever the person actually
  has, and says out loud that the four external programs listed after it are for
  the genome track alone.
- The owner's own goal left the product's vocabulary: the CLI help, the tool
  description, the chart legend («the optimum window 2021–2022») and the default
  heading («Goal — get back in shape») were one person's aim shown to everyone.
- `_goal_num` used a decimal comma regardless of language, so the English page
  showed «TSH 6,4» in the goal table above a card reading «6.42».
- «The internet is needed» on the drugs tab, three centimetres under a padlock
  reading «runs locally», now says what actually leaves: the drug name typed, and
  nothing else.
- Three new test files — `test_fresh_profile_is_empty.py`,
  `test_entrypoints_are_reachable.py`, `test_empty_state_honesty.py` — named after
  the failures rather than the functions.

### From the other branch, in the same release

**There is now an address.** `scholion.dev@proton.me`, in `README.md`,
`SECURITY.md`, `CITATION.cff`, `pyproject.toml` and the issue-template config —
with the instruction, in every one of them, to send no personal health data, and
a pointer to `scholion redact` for anyone who wants to send a file anyway. This
closes the last item of R1.1: until now a reader who found a defect, or wanted to
offer de-identified data for validation, had nowhere to write.

**A page for clinicians.** `docs/FOR-CLINICIANS.md` — what the program takes in,
what it will and will not claim, and where it refuses. It ships inside the
package like the other documents (`scholion doc for-clinicians`).

**`scholion limits` names the cell it is answering from.** Input class (whole
genome / exome / consumer array) × trait architecture (monogenic / oligogenic /
polygenic): the pipeline differs in each, and so does what may be claimed. A
percentile with no architecture beside it reads as a verdict; «no pathogenic
variant found» in a gene the file never covered reads as reassurance. Where a
polygenic number is on screen, a note on heritability goes with it.

**Fact, not cause.** Raised by a clinical geneticist reviewing the project on
17.08.2026 and the sharpest technical point in that review: «ferritin rose after
the course» is a fact, «the course raised ferritin» is a causal claim that a
series of two points cannot support. Rule 7 of the skill entry now says so to the
model, and `test_safety_rules.py` holds the message catalogue to it — the
catalogue is where a causal habit would start, because the model imitates the
wording it is given.

### Two capabilities, in the same release

**The goal is proposed now, not shipped.** Removing one person's targets from
`health_goals.json` left a hole where a goal used to be, and «write your own»
is not an answer for somebody who has just installed a program. `scholion
goal-suggest` reads what the person has actually measured and what the clinical
associations publish, and proposes a target for each marker there is enough to
propose one for. Three sources, and the whole design is in keeping them apart:

- **a guideline**, quoted with its citation — the strongest and the rarest;
- **the person's own best**, with the date and the number of readings behind it.
  Not a recommendation from anybody: a fact about them;
- **the wall of the laboratory corridor**, offered last, because «inside the
  range» is where most people already are and is not an aim.

A target already met is not offered as something to reach — it goes to a list of
its own, which is a different and true statement. A target written for people
with a condition (ADA's «under 7 %» is for somebody who HAS diabetes) is never
adopted on a condition nobody confirmed. And what was passed over is listed with
the reason, because five proposals with no account of the forty markers skipped
read as «these five are what matter».

`goal_targets.json` is new, and its hardest entries are the empty ones. The
Endocrine Society looked at 25(OH)D in 2024 and withdrew the target it had once
set; that refusal is recorded, quoted, and travels with anything else proposed
for that marker — otherwise the laboratory corridor quietly supplies the number
the society declined to write.

Nothing is written to the profile without `--write` or a press of «Save», and a
target the person set by hand is never replaced: it is the strongest source
there is, because it is theirs.

**The inherited side of the lipid profile (task 63).** PCSK9 carriage and Lp(a)
in one card on «Genome», because each is misread alone. A low LDL-C with a
loss-of-function variant behind it is a different fact from the same number
reached on a statin; and Lp(a) is invisible to the rest of a lipid panel — set
at birth, unmoved by what moves LDL-C, so a normal panel with a high Lp(a) is a
normal panel that has missed the finding.

Four PCSK9 positions entered `loci.json`, each coordinate read from the Ensembl
REST API rather than from memory — the one lost variant in this project's
history was lost to a coordinate written from memory. Two of them entered
`longevity_directions.json` with primary PMIDs (Cohen 2005, Cohen 2006); the
other two did not, and sit in `unresolved` saying why. The catalogue's own rule
asks for a primary source naming the favourable allele, and review-level sourcing
is not that.

Two limits are printed rather than implied. «Not a carrier» of C679X says almost
nothing outside populations of African descent, where the variant is close to
absent — so the caveat travels with the answer. And a polygenic score for Lp(a)
is an ESTIMATE: the level is driven mostly by the number of KIV-2 repeats inside
LPA, a copy-number variant short reads see poorly, which is what the catalogue's
«Moderate» mark on `PGS002101` has been saying in a place nobody looks. Where
Lp(a) has not been measured the card says so and asks for the test — once in a
lifetime, in nmol/L, and before a decision about therapy rather than after it.

One correction to the analysis this was built from: `rs28362286` is **C679X**,
not «near Y142X». Y142X is a different variant (`rs67608943`). The position
Ensembl returns, 1:55063542, is at the 3′ end of the gene and fits residue 679,
not 142.


**A laboratory's summary sheet no longer overrules your own reads (task 64).**
`core.genotype_status` returned the profile entry the moment it found one and
never reached the VCF. So `rs4988235`, `rs1801133` and `rs429358` came back as
`reported / profile / depth=None` — copied off an Evogen summary — while the
person's own aligned reads sat unread in a file on the same disk. `scholion
genome rs4988235` meanwhile DID read the VCF and answered «reference confirmed
by a call (0/0), coverage 32». Two routes to one fact, disagreeing, and nothing
in either saying so.

A genuine read now wins: it carries a depth, it can be re-examined, and it is
what the report was made from. But only a genuine one — `assumed_ref` means «the
reference, OR nothing was looked at there», and letting that overrule a
laboratory's positive finding would be this project's oldest defect wearing new
clothes. A disagreement is never resolved silently: both values travel in
`conflict`, and the CLI and the interface both print it, with the suggestion to
take it back to whoever issued the report. Agreement is printed too — two
independent routes to the same call is a stronger statement than either alone.

Why the seventeen known disagreements between that report and the reads never
tripped this: `genotype_status` answered `None` for every one of them, because
those rsIDs are not in the coordinate catalogue. The priority was never exercised
where it is dangerous, so the absence of an error there proved nothing — and the
tests build the collision by hand rather than waiting for one.


### What is retracted — the CI job that could not run where it was sent

**The job written to catch «a check that asks the artefact for something only the
repository has» was one.** `tests.yml` has a `package` job whose first step runs
`make_shareable.py` — the sanitiser, which builds the package FROM `share/`. But
`share/` does not ship: it is the folder the package is built out of, not part of
what is built. So on the public repository that step answered «Run this from the
ORIGINAL repository (there is no share/ folder with the templates)» and the build
went red on the first push after publication, six seconds in.

The author never saw it, because the author is in the source tree, where it
passes. That is the whole of the class: a check agreeing with the single
environment it was written in. It has now cost this project four times, and this
is the first time it cost a red badge on a public repository — the first thing a
stranger sees.

The two steps are conditional now, on the same predicate `tests/support.py`
already uses and calls `IN_SOURCE_REPO`: does `share/` exist. Where they are
skipped the job says so with a `::notice::`, because a green tick for having run
nothing is worse than a red one, and the matrix job above has in any case already
run the package's own suite on exactly the files a recipient gets.

#### Also

`tests/test_ci_runs_where_it_can.py` — a workflow step that runs a tool needing
the source tree must be conditional, and the condition must be the same question
Python asks. The check is textual, so it is narrow on purpose; its first version
read the workflow's own explanation of the guard as an unguarded call, which is
the failure mode of every textual check and is why it now drops comment lines
before looking. Verified by removing the guard and watching it go red.

### What is retracted — the metadata line that kept this release off PyPI

**Two releases reached GitHub and neither reached PyPI.** `v0.3.0` and `v0.3.1`
both died on the same line, added when the project got an address to write to:

    Contact = "mailto:scholion.dev@proton.me"

Every value under `[project.urls]` has to be a URL, and PyPI means it:
`400 'mailto:scholion.dev@proton.me' is not a valid url`. The index published
`0.2.2` and has been publishing it ever since; the tags on GitHub say otherwise.
Anyone who ran `pip install scholion` after 0.3.0 was tagged got 0.2.2 and had no
way to know.

**When it failed is the part worth keeping.** The build succeeded. `twine check`
printed PASSED on both artefacts — it validates the long description, not the URL
schemes. The signing, the attestations and the transparency-log entries all
completed. The refusal came from the index, in the last step of the last job,
after everything that could have caught it had said yes.

The address now lives in `authors`, which is the field the core-metadata
specification has for an e-mail and which PyPI accepts; the built wheel carries it
as `Author-email: CrossRead <scholion.dev@proton.me>`. `Contact` points at the
README's own contact section — the place that says what to write about and, more
importantly, what not to send.

#### Also

`tests/test_packaging_metadata.py` asks the questions the index asks, when the
suite runs rather than when the artefact is in flight: every `[project.urls]`
value begins with `http`, an address to write to still exists and is not a
`mailto:` in disguise, and the version still comes from the one file. Verified by
putting the `mailto:` back and watching it go red, and by dropping the address and
watching it go red for the other reason — the fix must not become «we removed the
contact», which is the task the address was added for.

It parses the file by hand instead of with `tomllib`. That library arrived in
Python 3.11; this project supports 3.10, and 3.10 is the interpreter the mistake
was authored on — so a test that skipped without a TOML reader would have skipped
on the one machine where it mattered and reported OK for checking nothing. This
project has been bitten by that shape four times.

---

## v0.2.2 — 17.08.2026

_PATCH, by the owner's judgement and against the first reading of this project's
own rule — which is why the rule was rewritten in the same breath rather than
quietly stepped over (`docs/VERSIONING.md`, «Accepting a new form of an input»).
Everything here is the road in: nothing already stored changes value, and no
answer already given reads differently. Five unit forms that used to be refused
are now accepted, and one command was added that draws no new kind of
conclusion._

### What this changes in the conclusions

**Five more of the units a US lab actually prints are accepted.** Free T4 in
ng/dL, free T3 in pg/mL, TIBC and zinc in µg/dL, DHT in ng/dL. The lab import is
transactional by design, so one unknown form used to drop a whole panel and leave
the person with an import that did nothing. Each factor is stored with the molar
mass it derives from, so a wrong one can be caught by reading rather than by
trusting whoever typed it, and `hba1c` (mmol/mol) and `lpa` (mg/dL) stay refused
on purpose — one relates by an affine formula rather than a multiplier, the other
depends on the person's apo(a) isoform.

**`scholion doc` prints the documents the output points at.** A `pip install`
gets `src/scholion` and nothing else, while the output sends the reader to README
nine times, to PREPARING-THE-GENOME four and to DATA-LAYOUT twice. Those files
were not on a PyPI user's disk, and with the repository private there was no
second place to read them: `limits` was advising people to open something they
could not reach. Seven documents now travel inside the package.

**The first screen works from an empty machine.** `scholion demo` writes into
`<data>/demo/profile` and `scholion overview` reads `<data>/profile`, so the
README's opening two commands produced an empty profile. The first line is now
`init --demo`. `demo` is unchanged and still right: building the profile away
from a real one is the correct default.

**A bare `scholion` answers instead of erroring,** and `init --demo` no longer
lists four external programs the demo does not use. After a real `init` the
offer stays — there the genome layer needs them.

**The skill loads a short entry instead of a thousand lines.** `SKILL.md` was
the whole instruction — around seventeen thousand tokens on every trigger before
the first useful word, and the one thing a newcomer needs, how to start, was not
in it. It is now a 5.5 KB entry plus `INSTRUCTION.md`, which the model opens when
the task calls for it, and `make_skill_package.py` builds the pair and its
references into a single `dist/scholion.skill`: for somebody whose only tool is a
language model, a folder is not a delivery and a file is.

**The local web interface got a design.** It is styled with Pico CSS, vendored
rather than fetched from a CDN: the interface binds to `127.0.0.1` and the claim
is that using it sends nothing anywhere, which a stylesheet loaded from somebody
else's server on every page would quietly make false. The bundled copy is now
recorded in `ATTRIBUTION.md` under a section that did not exist — the legal layer
covered tools the user installs and data redistributed here, but not code that
travels inside the package.

**A profile file now says which shape it is in.** Nothing to migrate yet; the
direction that matters is that a build refuses a file written by a newer one
rather than reading an unknown shape with rules that no longer apply. That
direction cannot be added later — by the time there is a version 2, the builds
that must refuse it are already installed.

### What is withdrawn

Nothing. Every previous result stands; what changed is what the system will now
accept as input and what it will now refuse.

### What needs recomputing

Nothing. A panel that failed to import because of one of those five units can be
imported again — it never wrote anything, so there is nothing to correct.

### Changes by file

**Knowledge — a break in the series**

- `src/scholion/knowledge/lab_markers.json` — five US unit forms, each with its derivation

**Web interface**

- `src/scholion/web/` — a design, styled with a vendored Pico CSS
- `ATTRIBUTION.md` — a section for code bundled in this repository

**Skill**

- `share/skill/` — the instruction splits into a short `SKILL.md` and `INSTRUCTION.md`
- `src/skill/INSTRUCTION.owner.md` — the owner's edition, renamed and still private
- `src/tools/make_skill_package.py` — the bundle as one file

**Engine and application**

- `src/scholion/cli.py` — `doc`; a bare call answers; no tool offer after a demo
- `src/scholion/core.py` — the profile schema layer: read, refuse, stamp
- `src/scholion/docs.py`, `src/scholion/docs/` — seven documents carried inside the package
- `src/scholion/contract.py`, `src/scholion/i18n/` — the new command and its wording
- `src/scholion/templates/profile/` — a version number, and the layout prose moved off that key

**Tools and build**

- `src/tools/sync_docs.py` — keeps the carried documents equal to their sources
- `src/tools/check_language.py` — copies are measured once, not twice

**CI**

- `.github/workflows/tests.yml` — ubuntu + macos × Python 3.10–3.13, a symlinked
  TMPDIR, and the package's own suite run inside the package


## v0.2.1 — 17.08.2026

_PATCH: nothing that ships behaves differently. `v0.2.0` could not be published —
its own test suite failed on a public runner, and the workflow runs that suite
before it publishes._

### What this changes in the conclusions

Nothing. This release exists because `v0.2.0` never reached anybody.

A test read `src/tools/check_push.py` — the private repository's pre-push hook,
which guards a history a recipient does not have and therefore does not ship.
Inside the package the file is absent, the test raised `FileNotFoundError`, the
suite went red and no version was published.

That is the third time in three days for the same shape: `.personal_patterns` in
v2.23.0, `share/` in v0.1.3, this one now. The first two were repaired by
guarding the one test that had failed — which is how a class survives being
fixed. The third is the one worth naming: `support.IN_SOURCE_REPO` already
existed, written for the second, and simply was not used.

So the repair is on the publication rather than on the test. `publish_share.sh`
now **runs the package's own suite inside the package**, before anything is
committed or pushed, and a red run stops the publication instead of announcing
it. `pyproject.toml` has stated that rule in prose since the sdist was defined —
«a green run at the author's end with a red one at the recipient's does not mean
verified, it means the state of the artefact is unknown» — and nothing enforced
it. The run leaves `__pycache__`, which the audit calls build junk, so the last
word belongs to a clean rebuild and a second audit.

A textual rule was tried first and abandoned, which is worth recording so nobody
tries it again: «a test module reading a repository-only path must name
IN_SOURCE_REPO» flagged `test_redact.py`, which correctly writes its own
`.personal_patterns` into a temporary directory, then missed the real defect, and
tightening it would have failed three modules that guard themselves differently
and correctly. A check wrong in both directions is worse than no check.

### What is withdrawn

Nothing. `v0.2.0` was tagged and pushed but never published — anyone who has it
has it from the repository, not from an index.

### What needs recomputing

Nothing.

### Changes by file

**Tools and build**

- `src/tools/publish_share.sh` — the artefact's own suite runs before the commit; a clean rebuild after it

**Tests**

- `tests/test_privacy_guard.py` — the push-gate test asks whether it is in the repository
- `tests/test_build_audit.py` — the publication is checked for running the suite it declares


## v0.2.0 — 17.08.2026

_Comparison base: v0.1.3 → HEAD. 13 files changed. **MINOR, not PATCH: this is a
break in the series** — `src/scholion/knowledge/` changed and the same input now
yields a different answer._

### What this changes in the conclusions

**The DPYD panel goes from two variants to seven.** The 2024 joint consensus of
AMP, ACMG, CPIC, CAP, DPWG, ESPT, PharmGKB and PharmVar names seven Tier 1 DPYD
alleles — the set a clinical panel is expected to carry. This one carried two:
`*2A` and `c.2846A>T`. Now it carries all seven: `*13`, HapB3 (both of its tags),
`c.557A>G`, `c.868A>G` and `c.2279C>T` are added, with their coordinates taken
one at a time from dbSNP and Ensembl rather than from anybody's memory. The gene
is on the minus strand, so the cDNA notation and the allele written in a VCF are
opposites; each was converted and checked.

A person who ran `drug capecitabine` before this release and was told the DPYD
markers looked normal was told that on the strength of two positions out of
seven. The same command now says «read 2 of 8 markers» and names the six it could
not read. **Nothing about that person changed; what the answer admits did.**

**A haplotype carried by two variants counted as two alleles.** DPYD HapB3 is one
allele described by `rs75017182` and `rs56038477`, which travel together. The
counter added copies per marker, so a single heterozygous carrier would have
produced two decreased-function alleles — CPIC activity score 1.0 read as 0.0, an
intermediate metaboliser reported as fully deficient. The direction is towards
caution, which is why it could have sat there; it is still a wrong statement
about a person. Markers may now declare a `haplotype`, and one is counted once.

**Five markers were outside the extraction target and nobody could have seen it.**
`fastq_to_vcf.sh` carried its own table of regions to align against. Two CYP2C19
markers were written on chromosome 19 — the gene is on 10. Two DPYD intervals
stood 373 kb and 899 kb from their loci. `rs1142345` — TPMT `*3C`, the commonest
deficient allele in Europeans — was 31 bases outside the left edge. None of that
surfaces as an error: `bcftools` finds no row outside the target and the marker
comes out `./. (ref/not covered)`, exactly what a position the sequencing
genuinely missed produces. Anyone following the documented route was told nothing
was found where their genotype was. The table is gone: the target is generated
from the catalogue at every run.

### What is withdrawn

**Any previous «DPYD looks normal» rests on two positions out of seven and does
not exclude a deficiency.** It was never phrased as an exclusion, but it was read
as one, and at full-dose fluoropyrimidine the difference is not academic.

**Any previous genotype for CYP2C19 `*2`/`*17`, TPMT `*3C` or the two DPYD
markers, obtained through `fastq_to_vcf.sh`, is not a result.** Those positions
were never in the alignment target; `./.` there means «not looked at», not
«reference».

### What needs recomputing

For anyone whose VCF came through `fastq_to_vcf.sh`: **re-run the extraction**,
because the target now reaches five markers it did not before. Genotypes read
from a full-genome VCF produced elsewhere are unaffected — only the targeted
route was narrow.

Nothing else needs recomputing. The wider DPYD panel does not change a stored
value; it changes how much of the panel an answer admits to having read.

### Changes by file

**Knowledge — a break in the series**

- `src/scholion/knowledge/cpic_drug_gene.json` — DPYD: 2 markers → 8, `haplotype` on the HapB3 pair
- `src/scholion/knowledge/loci.json` — 6 DPYD loci added; new `regions` section for whole-gene windows

**Engine and application**

- `src/scholion/engine.py` — a multi-tag haplotype counts once

**Data preparation**

- `src/ingest/fastq_to_vcf.sh` — the target BED is generated from the catalogue
- `src/ingest/update_check.sh` — the version of ClinVar is read by the name it is written under

**Tools and build**

- `src/tools/check_staged.py` — `in_forbidden_dir`: a personal-data folder under a neighbouring name
- `src/tools/check_push.py` — uses that predicate instead of its own copy

**Tests**

- `tests/test_answerability.py` — haplotype counting; the online drug route
- `tests/test_catalogue_integrity.py` — the DPYD panel against the external consensus
- `tests/test_pgx_script_coordinates.py` — BED-shaped coordinate tables; the margin invariant; note vs catalogue
- `tests/test_privacy_guard.py` — a renamed personal folder


## v0.1.3 — 17.08.2026

_Comparison base: v0.1.2 → HEAD. Commits: 6. 21 files changed, 356 insertions(+), 19 deletions(-)._

### What this changes in the conclusions

One new layer: `prescription` can now surface a hand-curated fact from the
patient's own record. `medications[].safety_flags[]` in `profile/medications.json`
holds entries the engine never invents — it only reads one a person wrote down: a
documented diagnosis, a documented event, a conflict with their own history. A
flag marked `red_flag` lifts the overall verdict to `high`, anything else to
`moderate`, and the renderer prints it first — above the genome, the labs and the
interactions, because a flag read last is a flag not read. The web view carries
the same block, and both skill editions now say when to raise one: as soon as a
new document yields a diagnosis that changes how a current prescription reads,
and in reverse — check any new document against the current drug list.

Nobody who has not written a `safety_flags` entry into their own profile sees any
difference in output; the layer is silent until a person fills it in.

Everything else in this release is process and safety-net, not a change to any
result: the shipped skill file is now checked against substitution at build time
(the package ships two editions of `SKILL.md` and a build error used to be able to
put the wrong one at a given path without anything noticing); the package's own
test suite is now verified to pass from *inside* the package it built, not only
inside the repository that builds it; a repository-hygiene test that mistakenly
flagged the package's own shipped profile/genome templates as personal data is
corrected; and a publication commit can now be signed with a real identity
instead of the anonymous one the tooling used before.

### What is withdrawn

Nothing.

### What needs recomputing

Nothing computed from existing data changes. `safety_flags` is something a person
adds by hand to their own `profile/medications.json`; it has no effect until they
do.

### Changes by file

**Tools and build**

- `src/tools/check_language.py` — changed
- `src/tools/check_staged.py` — changed
- `src/tools/install_hooks.sh` — changed
- `src/tools/make_shareable.py` — changed
- `src/tools/publish_share.sh` — changed

**Skill**

- `share/SKILL.shared.md` — changed
- `src/skill/SKILL.md` — changed

**Engine and application**

- `src/scholion/engine.py` — changed
- `src/scholion/format.py` — changed
- `src/scholion/i18n/en.py` — changed
- `src/scholion/i18n/ru.py` — changed
- `src/scholion/skill/SKILL.md` — changed
- `src/scholion/web/index.html` — changed

**Guides and documentation**

- `CLAUDE.md` — changed
- `README.md` — changed
- `docs/DATA-LAYOUT.md` — changed

**Tests**

- `tests/support.py` — changed
- `tests/test_build_audit.py` — changed
- `tests/test_licensing.py` — changed
- `tests/test_repo_hygiene.py` — changed

**Other**

- `.gitignore` — changed

<details><summary>Commits</summary>

- a diagnosis of the patient's own can now outrank a computed verdict
- the package's own template files no longer read as somebody's personal data
- readme: trim the versioning explanation to one sentence
- the publication commit can be signed by a person, and the setting that does it no longer kills the script
- the suite stops being red inside the package it was built from
- the shipped edition of the skill is checked, and the layout gains a slot for what was made to be read

</details>

## v0.1.2 — 17.08.2026

_Comparison base: v0.1.1 → the working tree (not committed yet). Commits: 0. 5 files changed, 79 insertions(+), 13 deletions(-)._

### What this changes in the conclusions

Nothing about anyone's health, and nothing in how a result is computed.
`set-folder` used to accept only a fixed list of eight domain names (labs,
medications, metrics, genome, labs_docs, med_docs, garmin, apple_health — the
last one newly recognised in this release, though nothing parses it yet) and
refused everything else outright. A source folder that is legitimately
personal — a CGM app's screenshots, a specific sequencing provider's export
folder, whatever the next such folder turns out to be called — had no way to
be recorded at all.

An unrecognised domain name is now accepted rather than refused, and filed
under a new `external_sources` section of `profile/sources.json` instead of
`folders`. `core.source_config()` — what every reader of a configured folder
actually calls — merges both sections, so the split matters only at the
moment a folder is set, never when one is read back.

The trade-off is explicit, not accidental: the old refusal also caught a typo
of one of the eight names as a side effect ("grmin" for "garmin"). Opening the
domain up removes that — a near-miss is now just an ordinary new
`external_sources` entry, and the intended domain is left untouched, not
corrected. Nothing reads `external_sources` programmatically yet, so today
that costs nothing silent.

### What is withdrawn

Nothing.

### What needs recomputing

Nothing. No stored value, no catalogue and no conclusion changed.

### Changes by file

**Engine and application**

- `src/scholion/cli.py` — changed
- `src/scholion/core.py` — changed
- `src/scholion/store.py` — changed

**Tests**

- `tests/test_external_sources.py` — added

**Other**

- `VERSION` — changed

## v0.1.1 — 16.08.2026

_Comparison base: v0.1.0 → the working tree (not committed yet). Commits: 0. 1 file changed, 53 insertions(+), 1 deletion(-)._

### What this changes in the conclusions

Nothing about anyone's health. Two defects in the gate that runs last — the
pre-push hook — one of which would have stopped the first push of this repository
anywhere.

**The pre-push check refused the synthetic genome fixture.** `tests/fixtures/genome/
tiny.vcf.gz` is the one genome file this project allows into its history, and it is
allowed by content rather than by name: the header has to declare it invented, and
the call set has to be small enough that nothing real fits through. Four gates ask
`synthetic_fixture` that question — the pre-commit hook, the build audit, the
repository-hygiene test, the `.gitignore` negation. `check_push.py` never did. It
saw a `.vcf.gz` in the history and blocked, which means every earlier gate could
approve the repository and the last one would refuse it at the moment of pushing,
over a file the project ships deliberately. The exception is now asked of the same
module the other four ask, so it cannot drift between them.

**The pre-publication tags could travel out with `git push --tags`.** 32 tags named
`v1.0.0` … `v2.24.0` live under `pre-0.1.0/` because the numbering was reset at
publication and those same numbers will be used again. `git push --tags` does not
ask which tags — it sends every tag it has. The CI filter (`tags: ["v*"]`) would
not have published them to PyPI, but by then they would already be in a public
history, and a pushed tag is not taken back by deleting it locally. The hook is the
only place that sees the refs and can still say no; it now refuses them by name and
prints what to push instead.

Neither would have fired today — the private repository has no remote, so there is
nowhere to push. Both would have fired the first time one was added.

### What is retracted

Nothing published. The claim being corrected is internal: that the five gates
guarding personal data all asked one predicate. Four did.

### What needs recomputing

Nothing. No stored value, no catalogue and no conclusion changed.

### Changes by file

**Tools and build**

- `src/tools/check_push.py` — changed

## v0.1.0 — 16.08.2026

_The first release anyone outside the project can install._

### What this changes in the conclusions

Nothing is retracted and nothing needs recomputing: there is no previous public
version to compare against. What follows is what the release contains and, more
importantly, what its number means.

### What the number means

**Below `1.0.0` the public contract may break.** Command names, the top-level
fields of `--json`, the file names inside a profile — the project's own rule is
that these may grow and may not shrink, and `python3 src/tools/check_compat.py`
enforces it on every run. Until `1.0.0` that rule is **internal discipline, not a
promise made to anyone outside**: it is stated here so that a person who builds on
`--json` knows precisely how much weight it carries, which is some, and not all.

**`1.0.0` arrives by use, not by features.** The condition is a number of people
who have run this on their own medical data and said what happened — not a count
of finished capabilities. Everything in this release was verified on invented
forms, an invented profile and one real record; the failure modes that matter for
a system like this appear in the second record and in the tenth, not in the first,
and no amount of building substitutes for that.

### What it does

Reads a person's genome, laboratory history, prescriptions, clinical conclusions
and wearable data against each other, locally, with the source shown behind every
statement. One core with three entry points — a local web app, a command line, and
a skill for a language model — and a rule, enforced by a test, that a capability
appears in all of them at once.

The part worth naming is what it refuses to do:

- **A value without a reference corridor is never shown as normal.** Green means
  «inside the corridor»; with no corridor there is no such claim to make.
- **A connected genome cannot make an answer less cautious.** A position with no
  row in a VCF is either the reference or no coverage at all, and the file does
  not say which — so it is carried as an explicit confidence level rather than
  collapsed into «reference». Before this was fixed, a person with a genome
  attached could get a calmer answer about a drug than the same person without one.
- **Units are a gate before they are a conversion table.** A value is admitted into
  a series only in a unit the marker declares, and the reference range is converted
  with it — the two travelling apart is a defect this project found in itself.
- **A source that was never reached makes no negative statement.** «No significant
  pharmacogenetics» and «the database did not answer» are different sentences.
- **What is not known is printed.** `scholion limits` states the coverage behind
  the genomic conclusions and names what cannot be concluded from the data present.

Everything it produces is material for a person's own decisions and for a
conversation with their physician. It is not a medical device, it is not a
clinical decision support system, and it does not diagnose.

### What is knowingly incomplete

- **Nobody outside has run this yet.** That is the single largest gap in the
  evidence behind everything above.
- **eGFR is not read from an English laboratory form.** Its value is printed on the
  line below its name, and relaxing that rule would take a wrong number on the very
  form the rule was written for. It needs a real English form to decide on, and
  there is not one — so it stays named rather than fitted.
- **175 markers are recognised in Russian only** — urine organic acids, the
  coprogram, the dysbacteriosis culture, the element panels. They are barely
  ordered outside Russia; their labels are work an outside contributor can do
  without touching any logic.
- **LOINC codes are absent.** The table is available from Regenstrief, and using it
  obliges the project to ship a verbatim notice in `NOTICE` in the same commit.
  Neither half could be done honestly on release day.
- **Pharmacogenetics covers seven genes** — the core with the strongest evidence,
  not a full panel. CYP2D6 as a whole needs a dedicated tool: structural variants
  and phasing.

### What holds it together

393 tests, run offline against synthetic fixtures and executed inside the built
package rather than only in the repository. A parsing baseline recorded *before*
the dictionary migration that followed it — the timing is the value: a baseline
recorded after a change states that the code equals itself and passes on any
behaviour. Every test written for a defect was re-run against the un-fixed code to
prove it catches it. A build audit that fails the package on any personal datum —
in plain text or encoded — and three independent barriers keeping personal data
out of git.

---
