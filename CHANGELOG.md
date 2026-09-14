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

## v0.5.2 — 14.09.2026

### What you can do now

**An assistant tells a person that a newer version is out, and installs it on
their word.** Somebody who uses Scholion through Claude or another assistant never
sees the local page, so a newer version went unnoticed. `scholion update` says
whether a newer build is out and how it installs in this environment — pip, pipx
or uv as it was installed, or `git pull` for a source checkout — asking the package
registry at most once a day, sending only the package's name, and never with
`SCHOLION_OFFLINE=1`; `scholion update --yes` installs it. Through the tool
interface the same is `sch_version` and `sch_update`: the first tool answer of a
session mentions a newer build once, and `sch_update` installs nothing without
`confirm=true`, which is reserved for the person's own yes. The skill's instruction
starts every session with `scholion update`.

**The menu checks for an update and opens the recompute.** The ☰ menu beside
the language switch now carries «Check for an update», which asks the package
registry on request and, when a newer version is out, prints the command that
installs it, and «Recompute after an update», which opens the list of steps
the releases since your data's version ask for. Both used to live only inside
the note shown right after an upgrade, so once that note was dismissed there
was no way back to either. The same answers come from `scholion version` and
`scholion recompute`, and an update itself is `pip install --upgrade scholion`
followed by a restart.

### What is fixed

The engine's answers are the same; what changed is how they are shown.

**The body figure and the radar no longer wait for the genetic rings.** On the
Overview the figure appeared seconds after the rest of the page — about seven
seconds on a server that had just started — because it waited for the listing
of the systems' genetic halves, the slowest answer of the page, and asked for it
only after the person's block was drawn. The figure and the radar are drawn at
once now, a bar beside them shows the rings loading, and the rings are drawn in
when they arrive.

**A pharmacogenetic phenotype read from a diplotype in the profile is shown in
the reader's language.** A star-allele call carried by the profile — from PyPGx,
PharmCAT or a laboratory report — printed its phenotype as the English CPIC
phrase («Intermediate Metabolizer», «Normal Function») on a Russian page. It is
worded from the phenotype now, and a «likely» or «possible» qualifier is kept.

**A ClinVar drug-response record says what kind of response it is.** A record
named like «warfarin response - Dosage» reads «warfarin: response to the drug —
dosage» in the reader's language; the drug keeps ClinVar's spelling, and disease
names are still printed as ClinVar gives them rather than translated without a
source.

**A month without a day no longer reads wrongly after a preposition.** Dates
that carry only a month are abbreviated like full dates, and a system's
movement reads «was 80 (Nov 2025)».

### What needs recomputing

Nothing.

## v0.5.1 — 13.09.2026

### What you can do now

**An update can now run what it asks, and shows how far it is.** `scholion
recompute` lists every step the releases since your data's version ask for,
together with the genome steps your data lacks, and says for each one whether it
will run, what it still needs — a folder of forms not named, an alignment not
found — or that it is yours to do by hand. `scholion recompute --yes` runs the
ready steps one after another and prints the step, the item being read, the time
spent and an estimate of the time left; `--status` shows the same from another
terminal, and `--stop` stops after the item being read. Files a step rewrites are
copied into the archive first, and the version is recorded as done only when
nothing is left for you. The local web page offers the same from the update note,
keeps the progress through a reload, and on the radar a panel with positions not
read for this reason offers the step where the gap is seen.

**The catalogue positions can be genotyped from the alignment without the source
tree.** `scholion genotype-sites` reads every catalogue position from your BAM
with `bcftools`, one chromosome at a time with progress, in the build of the
alignment, and writes the file that lets a position missing from the VCF read as
the reference. It records beside the file which catalogue it answers for, so a
later release that grows the catalogue can tell that the file is behind. Until now
this step needed two scripts that only the source tree carries.

**Every file in a profile now records the build that wrote it.** `scholion
version` names the files a later release asks to rebuild — laboratory results
written by an older build before a release asked to re-read the forms — with the
command to run. Files written before this release carry no such record; they are
counted as such, and `scholion version --since` lists what to rebuild from a
version you name.

**A skill copied into a skills folder can say which build it came from.**
`scholion skill --install` copies the entry into `~/.agents/skills/scholion/`, or a
folder you name, records the build beside it and says what it replaced; `scholion
selfcheck` reports a copy that differs from the installed build as an error and
exits with a non-zero status until the copy is replaced.

**An update now says what it asks of the data you already have.**
`scholion version` names this build and its age, the version your data was last
used with, and — for every release in between — what that release asks: a command
to run and when it applies, or a step to take by hand. The same note stands under
the header of the local web page until you press «Understood»
(`scholion version --seen` on the command line). A profile that never recorded its
version says so, and `scholion version --since 0.4.8` lists everything after a
version you name. `scholion version --check`, or the button beside the note, asks
PyPI whether a newer version exists — one request, only when you ask, refused when
the network is switched off. The README has a new section, «Updating», with the
command for each way of installing.

**The panel of a radar segment is one picture of the system's genotype, and it
says it was checked whole.** Each panel opens with the genotype of the system,
assembled from the panel's own sentences and nothing else: in which positions
the named allele was found and what the panel says of each, which alleles are
not carried, which positions were not read. Every position is then a card by
gene — found ones bright, the rest muted with the sentence that says what «not
found» means for that one — until now the patient's view showed two rows of a
seven-position panel and nothing about the other five. The polygenic scores
mapped to the system fold into one line and open by a click. «Genotype against
the measurements» puts, for every found position that names a marker, the
expected direction beside the measured value with its place in the corridor and
the number of the question it raises; whether they agree stays that question.
Where no found position predicts a measured marker, the block says so: the
panel's genotype does not account for those measurements and their cause lies
outside it — and the expectations the panel holds for alleles not carried are
listed as what did not apply, so the check is seen to have happened.
Positions a guideline weighs when a drug is chosen are named last, as what they
are: not a prescription, and no statement that a drug is taken. The same view is
on the system's own card, both for the patient and for the clinician, and the command line prints the
same conclusion.

**The panel itself, with its studies, on a page of its own for the clinician.**
Every radar block with a panel, and the system's card, link to a description of
that panel as the catalogue holds it: each position with its locus and named
allele, the sentence it prints for one copy and for two, the kind of link, the
guideline or study it rests on with the effect size, what it expects of a marker,
the gene–disease classification where there is one, and who signed the sentence
and when. It reads no genome and no laboratory result, so it is the same page
for anybody; the reading against a person's genome stays on the radar. `scholion
panel <system>` prints the same, and `scholion panel` lists the panels.

**One design across the application.** Every page is built the same way now:
a title, the question the page answers, a strip of the few numbers worth
seeing first, the sections, the details folded, and the sources in one line
at the bottom. There are six tabs — Overview, Radar, Labs, Genome, Medicines,
Lifestyle — with the Guide and the Assistant in a menu beside the language
switch. Medicines joins the list of prescriptions and the check of a new
drug, which used to be two tabs under two names. The body figure and the radar
open both the Overview and the Radar; the Radar adds an index of the systems, and each
system's block leads with a one-sentence verdict, the measurements as a table,
the genotype as findings with whether it agrees with the measurements, and the
questions for the doctor; every position of the panel, the scores and the notes
are under «More». Labs shows what is out of range first and folds the values
in range. Dates read «3 Sep 2026» instead of «2026-09-03T08:22», ClinVar
significance is shown in the reader's language, long notes are cut at three
lines until clicked, and a finding without a usable rsID is named by its
position. The Russian interface addresses the reader formally throughout. On a
phone the header takes one line, the tabs scroll sideways, the disclaimer sits
in the footer instead of covering the tabs, and the page no longer scrolls
sideways. A prescription that could not be removed now says so instead of
doing nothing, a test's priority is shown in words instead of an English code,
and the count of unread target genes agrees with its number.

**The radar shows its head at once and fills the systems in as they arrive.**
The tab used to wait for everything before showing anything. The head of the
tab now appears as soon as the quick answers are back, well under a
second; the blocks by system, which are the slow part, fill in under
their own loader. The server also reads every system's card once right after
it starts, on a thread of its own, so the first page of a session finds the
genome folder, the catalogue positions and the coverage table already read.
The two ways out of a block — the system's card, and the panel with its
studies for the clinician — are labelled buttons with a hint each, no longer
two blue links run together.

**Switching tabs no longer fetches every answer again.** What a tab has fetched
is kept for the session: coming back to the radar takes a tenth of a second
instead of seconds. Every write made from the page, a finished recompute or
ClinVar refresh, and a change of language forget what was kept; the answers that
describe a running job are never kept.

**A block of the lifestyle brief due for a review opens what changed.** The
flag «needs a review» is a button: for every block due it shows, per watched
marker, the value at the review date, every measurement since, where each stands
against its range and whether that position moved — beside «the wording still
holds» and a request for the assistant built from the same facts, carrying the
block's live tokens. The flag on the Assistant page, in the menu, goes there. `scholion
brief-review [block]` prints the same.

**The coverage of the genes the panels read can be measured from the package.**
`scholion coverage` reads, with `samtools`, how well the alignment covered every
gene of the ACMG list, the CPIC genes and the composed genetic half of each body
system, and writes the table the cards judge coverage by. Until now that step was
a shell script of the source tree, and its table held 93 genes while the systems
read 1203 — so most genes were honestly reported as not read, with nothing a pip
install could do about it. `scholion recompute` plans this step when the table
is missing or covers fewer genes than the panels read.

**A loading view shows the project's helix and how much has arrived.** Every
view that loads shows the DNA mark turning above a bar that fills as the view's
requests come back, with a count of what has arrived; the motion stops under the
system's reduced-motion setting.

**Every segment of the radar has a panel of its own: the positions a
clinician acts on, read on the genome and set beside the segment's laboratory
markers.** Ninety-two authored positions across twelve systems, each of one of
three kinds and saying which: a position that changes a prescription by a
guideline (the statin, thiopurine, NSAID, warfarin, clopidogrel and
allopurinol genes), a position that explains a laboratory marker with a
measured effect from a named study (PCSK9 and LDL-C, the LPA positions and
lipoprotein(a), PNPLA3 and liver fat, GC and vitamin D, FUT2 and B12, TMPRSS6
and ferritin, ABCG2 and urate, SHBG and testosterone, DIO1 and the T3/T4
ratio), and a position people ask about that decides nothing, printed with
that note. Each row prints the person's genotype with its depth, the sentence
written for that state, and — where the position bears on a marker of the
segment — a question comparing the expected direction with the last value; when the marker was
never taken, the positions waiting on it are named inside one question
rather than asking for the same test once per position. The
panel follows the verdict on the segment's card and in each block of the radar page; the broad
disease list from the base stands after it as the background. The clinician's
blank for the thyroid is in, sorted by kind rather than copied as a list. The
locus catalogue grew from 61 to 113 positions, every new one verified against
two independent sources; two whose second-build position the sources disagree
on are held without it and say so.

**A gene short reads cannot read is named as such, never as clear.** The
21-hydroxylase gene beside its pseudogene, the androgen-receptor repeat and
the Gilbert promoter repeat are printed as «requires a separate method», with
the method named, and are never counted as read; a «nothing found» over them
would have been a statement about the method.

**The radar page shows panels, not scores.** Polygenic scores stay on the
genome tab; on the radar each system's block opens with its verdict and panel,
and the scores mapped to it are folded under «More».

**The radar has a thirteenth segment, «Heart and vessels».** Until now the
body was laid out as eleven laboratory panels and one wearables segment, and
the heart had no panel of its own — so the pharmacogenetics that matter most in
a cardiology prescription (warfarin with VKORC1, CYP2C9 and CYP4F2; clopidogrel
with CYP2C19; the beta-blockers; the anticoagulants and antiplatelets) and the
cardiovascular polygenic scores had no card to stand on. The new segment is
built from the five markers a laboratory issues beside the lipid panel rather
than inside it — lipoprotein(a), apolipoprotein B, apolipoprotein A1,
fibrinogen and D-dimer — and answers like every other system: `scholion system
cardio` prints the laboratory now and its movement, a genetic half of 258
genes composed from the Gene Curation Coalition export (cardiomyopathies,
channelopathies and inherited arrhythmias, aortic aneurysm and dissection,
monogenic thrombophilia and hypertension, the monogenic forms of coronary
disease and of cerebral small-vessel stroke; pulmonary arterial and portal
hypertension are excluded by name because they belong to the lungs and the
liver), the ten cardiovascular scores, the prescriptions acting on it, and the
questions for a clinician. On the figure it is drawn at the heart. Lipids stay
a separate segment and keep the lipid measurements; the pulse and heart-rate
variability a wearable records stay in fitness, because a segment has one
source. Nothing stored is rewritten: the five markers were already recorded
under their own keys, and the segment reads them where they are.

### What is fixed

**A click on a radar label opened nothing, and the dot beside it was hard to
hit.** The dot's hit area was eighteen pixels across, and the label beside it —
«Lipids 56» — was not a door at all, so a click on it did nothing and looked like
a hang. The label opens the system like the dot does, and the dot answers within
a wider circle around it. A click from the radar now opens the system's card at
once and asks the server for nothing: the answer the radar already drew is the
one the card shows.

**The radar tab took about a minute to open on a real profile.** The list of
systems and every card asked the same questions hundreds of times: the genome
folder was searched and each file in it opened by content on every genome read,
the genotyping program was started once per position for the list and again for
every card, the laboratory results were analysed again for each card, and the
coverage table was parsed again for every gene. What a file's content says is
now remembered while the file is unchanged, the rows read at a position are
remembered while the file and its index are unchanged, and inside one reading
each of those questions is asked once. The list of systems opens in about four
seconds after a start and under a second after that; the cards in about two.

**The Ouroboros installation never loaded.** The instructions copied the tools
module into Ouroboros's own tools package, where it could not import its
neighbours, so the plugin failed on its first line and registered nothing. They
now place one line that imports the installed package, which also means an
upgrade of the package is the whole update of the plugin.

**A reference file refreshed on this machine outranked a newer one the package
carries.** An import kept answering for as long as the file existed, so after an
upgrade a months-old local copy silently beat the newer copy the build brought. The
newer of the two now answers, by the date each carries; `scholion sources` says
which copy answers each file and why, and a local copy with no date keeps
answering and says that it cannot be compared.

**The button labelled «Check for updates» refreshed ClinVar, and after a pip
install it answered with a file path.** It never updated the program: it ran a step
of genome preparation that a pip install does not carry, and the reason it printed
was a path inside the Python installation. It is now called «Refresh ClinVar»,
where it cannot run it is replaced by a sentence saying where that step is done,
and updating the program itself is `scholion version`.

**A cardiology prescription was printed as acting on nothing, and six
polygenic scores appeared on no card.** An ACE inhibitor, a sartan, a
beta-blocker, a calcium-channel blocker, a thiazide or loop diuretic, warfarin,
a direct oral anticoagulant, clopidogrel or an antiarrhythmic was listed as
«unmapped» on every system card, so `scholion prescription` could not
reach its genes through a system; the scores for atrial fibrillation, heart
failure, hypertension, systolic blood pressure, ischemic stroke and venous
thromboembolism were computed and shown on the genome tab but placed on no
system. All of them now stand on «Heart and vessels», and coronary artery
disease, myocardial infarction, peripheral arterial disease and abdominal
aortic aneurysm move there from the lipid card, where they had been the only
outcomes among measurements.

**Three lines of every form from one laboratory were read by nobody.** Total
calcium, magnesium, zinc and serum copper — the biochemical rows, printed in
mmol/L and µmol/L — were excluded from any form whose text or file name
contained «исп», the three letters that stand for the elemental method. Those
letters also stand inside «Исполнитель», the word that names the performing
laboratory in the header of every form one Russian laboratory prints, so on
those forms the four rows matched nothing at all: the elemental series does not
answer to the plain printed names, and the biochemical series had excluded
itself. Nothing failed — the other rows of the same form were read as usual, and
the missing ones were simply absent. The rule now names the form it meant
(«ИСП-МС», «Ответ ИСП»), and a check refuses any form rule short enough to hide
inside an ordinary word.

**A form could be counted as already read without ever having been read.** The
list of files a loader has taken remembered each one by the name it was given on
the command line. Named by a path relative to the directory the command ran in —
`ingest-labs ../forms` — that name meant a different folder from a different
directory. Two folders reached by the same relative name, a file of the same name
and the same modification time in each, and the second was passed over in
silence: present, never refused, its rows simply absent from the history.
Copying is what makes modification times equal, since `cp -p`, rsync and every
cloud sync carry them over with the bytes. A file is now remembered by its full
resolved path, so two files can no longer be one entry, and one file reached
through two paths — a folder of forms opened through a symbolic link, say — is no
longer read twice. Lists written by earlier versions go on working and are
renamed as each file is met again, so nothing is re-read because of this change.

### What needs recomputing

**Run `scholion genotype-sites` — if the catalogue positions were genotyped from an alignment before this version.**
The locus catalogue grew from 61 to 113 positions. A position the genome file
does not list counts as the reference only when a sites file genotyped from the
alignment confirms it, and a sites file made before this version holds none of
the new positions: in a segment panel they print as not read, never as the
reference. `scholion recompute` finds this step by itself and runs it with the
alignment and the reference it names. Everything else in the panels, the
heart-and-vessels segment included, is read from the reference base at every run
and needs nothing.

**Run `scholion ingest-labs --force` over your folder of laboratory forms — if a form names its performing laboratory in its header.**
Total
calcium, magnesium, zinc and serum copper from those forms are in no series at
all; re-reading adds them. Two cautions. A value converted by an earlier version
out of the biochemical row into the elemental series — a calcium of 2.31 mmol/L
stored as 92.58 mg/L, and the same shape for magnesium, zinc and copper — is NOT
removed by re-reading: it stays beside the true elemental readings, where a
change of method reads as a trend. Such a point carries no date beyond its month
and no source, which is how to recognise it. Delete it by hand — but only AFTER
the re-read has put the printed row where it belongs, or the value leaves the
profile altogether.

**Run `scholion ingest-labs --force` — if the folder of forms has ever been named by a path relative to the directory the command ran in.**
A form passed over for that reason left nothing behind to find it by: it counted
as unchanged, not as refused, so no report names it. One full pass over the
folder is what rules it out, and it is the same pass the note above asks for.

## v0.5.0 — 13.09.2026

### What you can do now

**Every body system now has its genetic half, composed from a base with a
version, without waiting for anyone's signature.** Eleven systems of the radar
carry a gene list taken from the Gene Curation Coalition's export: which genes
have an asserted link to the diseases of that system, who asserted it, how
strongly, under which mode of inheritance, and on what date — 945 genes in
all, from 31 for the growth axis to 218 for the kidneys, every submitter's row
kept side by side. The disease groups behind each list are named per system
and tuned title by title against the export; a term that matched the wrong
things — a bare «gout» that reached a neurological syndrome, «short stature»
that reached sixty syndromic genes — was vetoed by name, and the tool now
carries such vetoes so a refresh keeps them. The primary analysis runs on
every system at once: what was read, what was not, what ClinVar holds, and the
questions that follow. A clinician's signature is still what the curated
layer waits for — the positions, the phrases per genotype state, the signed
exclusions — but a list composed from the base no longer waits for it.

**COMT rs4680 stands on the radar, under the adrenal axis, and says what it
does not decide.** The catalogue held the locus since the previous release;
the adrenal system now carries it as an authored position: one or two copies
of Met are printed with the sentence that CPIC names the gene in its opioid
guideline and issues no recommendation by it, that the behavioural and
cognitive associations of the 2000s do not reproduce, and that nothing is
decided by the genotype — it is shown because it is asked about. It is printed, and it is not a finding: a
position never read prints as unread, and the named allele not found prints as
read and absent, with the depth.

**Polygenic scores stand beside every body system, as scores.** Of the seventy
pinned polygenic models, thirty-eight are placed with the system they measure —
LDL and coronary disease with the lipids, type 2 diabetes and glycated
haemoglobin with carbohydrate metabolism, Crohn's and lupus with inflammation,
gout and kidney disease with the kidneys — and each system's card prints its
scores under their own heading, never interleaved with the gene rows and never
inside the 0–100 index or the verdict: a genotype cannot be refuted by the next
blood draw. A reliable score at or above the eightieth percentile becomes one
question for the clinician — whether a screening is worth discussing — with the
caveats in the sentence: a percentile is not a probability, and the panels are
mostly European. The thirty-two models that fit no system of the radar are
named, with the reason, in the file that maps them. A profile with no scores
says so, and says that scores are computed from a full genome.

**The card says what a full genome would add.** For a person whose genome file
is an array, an exome or a panel — or who has none yet — the «to read in the
genome» basket names, per system, the genes of the list a full genome would
read and the polygenic scores it would make possible. A full genome prints
nothing there, because nothing is missing.

**The «Second opinion» tab is now «Radar», and it carries the whole picture.**
The figure and the radar with two rings per system, and one block per system
below them: what is outside the corridor, the genetic half composed from a base
with a version and how much of it was read, the polygenic scores, the
prescriptions acting on it, what to test and the questions for the clinician —
with the system's full card one click away. An explanation of what the rings
and the genetic half mean stands on the page itself, and the page still prints
as the sheet to take to an appointment.

**A body system answers as one card on every face.** Click a segment of the
radar or an organ on the figure, run `scholion system thyroid`, ask the local
API or the assistant's tool, and the same card comes back: the laboratory now
and its movement since the previous draw, the genetic half and how much of it
was actually read, the prescriptions acting on the system, the target a
clinician set, what to test, and the questions to bring to the appointment. The
next step comes in three baskets — laboratory, genome, ask — and a basket that
is empty says why it is empty. The card has two densities, one for the patient
and one for the clinician; they differ in how much is said, never in the
verdict, and no line in either is an instruction.

**The second look is laid out by body system.** What is outside the corridor,
what is prescribed for that system, what to test and what to ask now stand
together under one heading per system, where before the thyroid appeared three
times in three layers without being called one subject. Each block prints
whole, and a system with nothing to say is named as silent rather than left
out.

**Every system carries two rings, never merged.** How much of its laboratory
panel has been measured, and how much of its genetic half has been read, drawn
as two rings on the figure and on the radar. A system whose genetic list is not
composed shows that ring dotted — an absence, not a zero.

**Markers, genes and prescriptions point to their system.** A marker card says
which system it belongs to and opens that system's card; a gene says in which
systems it is named; a prescription says which system it acts on. A
prescription's genes now come from the system it acts on, and a clinician's own
rows about that drug stand as exceptions on top — a sentence, a class of link,
or a signed exclusion; an unsigned exclusion is refused and counted. Thirteen
drug classes are mapped to a system; the classes whose target is a use rather
than an organ — blood pressure, anticoagulation, pain — are left unmapped, and
the file says why.

**Three entries refuse in one voice.** A prescription, a class of disease and a
body system all judge their gene list through one form: the same gate (printed
only with a sentence and a source, the rest counted), the same pending row, the
same four-state verdict with the number of unread genes inside it, and the same
sentence. A list that was not read end to end is never called clear, whichever
door was used.

**The genetic half of a body system is composed from a base with a version, and
a clinician signs exceptions.** For the thyroid the monogenic composition comes
from GenCC — 38 genes, every submitter's assertion side by side with its
classification, mode of inheritance and date, and the export the list came
from printed with it. A clinician's own positions, phrases and exclusions are
read from a curated file that ships empty and says why. Ten systems say plainly
that their genetic half is not composed; the twelfth, built from wearables,
says it has none by design — three different answers where an empty block used
to be the only one.

**What the engine says about genetics is bounded.** Every row carries its
evidence mode and the three modes never print alike; an assertion classified
Limited, Disputed or Refuted is never a finding; one copy of an allele in a
recessive gene is printed as carriership and raised as a question, never as a
risk line; a single common variant prints only with an effect size from a named
study; and genetics does not enter the 0–100 score — a genotype cannot be
refuted by the next blood draw, so it stands beside the score, not inside it.

**A target your treating clinician set has a place of its own.** «TSH between
1 and 2», «free T3 5.0» — beside the reference interval printed on the form and
separate from your personal goals. You enter it with who set it and when; a
target without either is refused, and the product never proposes a figure of
its own. The figures convert to the marker's standard unit the way a laboratory
value does. The labs report, the marker cards and the marker charts show the
target beside the corridor, drawn in a different stroke so the laboratory's
range and the treatment's aim are never confused. When a value sits inside the
corridor but outside the target, the product asks whether it is worth
discussing at the next visit — a question, not an instruction. Standing outside
a target is never counted as an abnormality: the flag and the out-of-range
count are exactly what they were before. Targets live in their own file, so
re-importing a folder of forms rewrites the series and leaves them in place;
`scholion target` and a matching block on the labs page list, record and
withdraw them, and name in one place the values that are in the corridor yet
outside a target.

**The monogenic half of a system's gene list can come from a curated base
instead of from one person's memory.** A single command pulls the Gene
Curation Coalition's weekly export, keeps only the genes whose diseases belong
to a system, and writes them down with everything a reader needs to weigh each
line: who asserted the link, how strongly, on what date, under which mode of
inheritance, and which version of the base it came from. Every submitter's row
is kept, so two groups disagreeing about one gene are shown side by side rather
than averaged, and a weak or refuted assertion travels marked as such rather
than being silently dropped or silently promoted. The thyroid system ships
composed this way — thirty-eight genes with the recessive ones named recessive,
which is the difference between «carrier» and «at risk» for a heterozygote. A
freshness check says how far behind the base the shipped copy is, and the tool
refuses to touch the network when told to work offline. The other ten systems
remain unfilled on purpose: their terms are entered from a named panel or
report, and none has been named yet, so each says so instead of looking like a
system nobody asked about.

**A gene answers with what has been decided about it, not only with genotypes.**
Asked about a gene, the build now prints the curated verdict written about that
gene before the findings and again under them — including the case where the
verdict is that no clinical decision follows from it. Where such a sentence
exists it is quoted with the file it came from: a statement about what does not
follow from a gene is as much a claim as one about what does, and neither is
printed unattributed.

**How well a gene was read travels with the answer about a prescription.** The
measure arrived with the gene question and was wired only there. It is now beside
every gene on the prescription path as well, where «no pharmacogenetic finding»
is read as permission to proceed and is worth exactly as much of the gene as was
read. One state stays silent — a gene read like the rest of the file — and that
is not a claim that the reading was sufficient: sufficiency depends on the
question, which the product does not know. Without an alignment file the answer
is «not measured», which is a fact about the input.

**A second way in: a class of disease instead of a prescription.** `scholion
screen` answers the question a person has when nothing has been prescribed and
the examination says they are well — what to look at for the conditions where
inheritance carries most of the weight. The gene list there is fixed in advance,
which is what a panel is, and this build still invents none: the classes come
from the published secondary-findings panel it already carries, with the
panel named as the source, and every class that panel does not cover is printed
as absent rather than left out. A curated file takes classes a clinician
supplies, under the same rule as the prescription side — a list without a named
source is dropped and counted.

The answer for a class is gene by gene, and it will not call a class clear it
did not read: something reportable was found; nothing was found and every gene
of the class was read; nothing was found and part of the class was not read,
with how many and which; or the screen has not been run. On a screening result
«nothing found» is taken for health, and over a gene nobody read it is a
statement about the file. A finding does not cancel the gap either — both travel
in the same sentence.

The entry is on every face at once: the command line, the page (a pane of the
genome tab), the plugin, the model-facing tool list and the instruction the
model reads.

**Everybody has the gene; what can be missing is a variant, or knowledge of
one.** The class of link that used to read as «this gene is not here» was making
a claim about a person. It now reports what this build can say about variants in
that gene, measured against the reader's own file and never defaulted: positions
read and matching the reference, with how many of how many and at what depth —
which is a measured absence of a finding; positions held and not read in this
file — which is an absence of measurement; or no position held for the gene at
all — which is a statement about the build. Positions with no row are counted
beside the ones that were read, so two confirmed out of eight held no longer
reads as «nothing here».

**A gene somebody named, whose meaning nobody has written yet, is kept and
printed as unwritten.** It used to be dropped with the unattributed entries. It
is the most informative row on such a screen: it says a clinician put the gene
on the list and that what follows from it is still to be written — and the build
says plainly that it will not fill that in. The class of link is authored too: a
gene arriving without one is printed as named and unclassified rather than filed
under a class this program chose.

**A prescription is answered with a judgement about the choice, not only with
genotypes.** Asked to check a drug, the answer now opens with one of three
statements, and each is about what this build holds rather than about what to
do: a rule for this pair exists and the reading selects a row that is not the
neutral one; a rule exists and the reading selects the neutral row, which is a
statement about the rule and not clearance; or no rule could be reached, with
the reason named.

**The link between a prescription and a gene has a class, and the class decides
what may be said.** Two classes are computed from this build's own tables — a
pair with a guideline, and a pair recognised with no table, which travels with
the date of the copy. Three cannot be computed: a gene that handles the
substance with no dosing rule following, a gene asked about from which nothing
follows, and a gene named in a list and unknown here. Which genes belong to a
prescription is a medical statement and so is «nothing follows from this one»,
so those three are read from a curated file and never derived. An entry without
a named source is not printed, and the number of entries dropped that way is
printed instead — an entry that vanishes quietly is indistinguishable from one
nobody wrote.

The curated file ships empty, deliberately. Until a clinician writes a row, the
honest answer to «what else bears on this prescription» is that this build holds
no list for it — and that sentence is printed, because a silence there is
completed by whoever is answering the reader, out of knowledge that never passed
through this build.

**Every locus stands on one of five named things, and two of them license
nothing.** What permits saying anything about a position — a guideline rule, a
curated note, a verdict about the gene, or the bare fact that the gene is a
recognised pharmacogene this build holds no table for — is now decided from the
files and printed. The fifth state is a position with none of those, and it no
longer prints a genotype and stops: it says this build holds no reading for the
position, the genotype is named and not interpreted. A check walks the whole
catalogue and fails on a locus that stands on nothing silently.

### What is fixed

**A gene the ACMG scan had put through ClinVar was still called «not put
through ClinVar».** The system card counted a gene as read only when the
wide ClinVar annotation — a separate pipeline step — had been run; on a full
genome with only the product's own ACMG scan, APOB and LDLR on the lipid list
said the annotation had not been run, although the scan had done exactly that
for its 84 genes. For those genes the scan now counts; every other gene still
says, in words, that its variants were not put through ClinVar, and what
closes it.

**Why a gene was not read printed as a code.** «not read (clinvar_not_run)»
stood on every such row and once per gene in the genome basket — two hundred
and eighteen lines for the kidneys, none of them saying what to do. A reason
is now a sentence in the reader's language, the basket groups the genes by
reason on one line each, and each line names the step that closes it: the
ClinVar annotation of the file, or the coverage table computed from the reads.

**A position whose author says nothing follows counted as a finding.** An
authored position of the «asked about» kind — COMT Val/Met — was counted into
the system's verdict as something reportable, while its own sentence said
nothing is decided by it. Such rows are printed with their sentence and are
not findings; the patient's register shows them, since the sentence was
written to be read, and shows the genotype state on them instead of «not
determined».

**The demo-genome recipe ended in a refusal.** The fetcher printed «lay out a
profile, then point the product at both», and the product then refused to
read the reference genome beside a profile it took for the person's own. A profile
can now be laid out for a reference sample — `scholion init --subject
reference` — every file of it says so, the reference genome is read beside
it, and the refusal that used to print a raw key names this way out.

**The demo-genome fetcher crashed on its first request.** `fetch_demo_genome.py`,
the one tool that downloads a public Genome in a Bottle sample so the product
can be shown with a real genome, had `encoding=` pasted onto its HTTP calls to
satisfy a text-file check, and every run since 0.4.9 stopped with a type
error before listing anything. The three calls are HTTP openers again, and the
check now knows them by line.

**Three tools could not be called through the tool server.** A model asking to
note an episode in the focus journal, to record why a day holds two draws, or
to propose a marker name received a type error instead of an answer — on every
call since those tools appeared, because the three read their arguments in a
way no host passes them, and the test that covered them filled the arguments in
by hand. All thirty-two tools now answer over the wire with the arguments their
schemas declare, and a test calls every one of them that way. Nothing stored
changes.

**Five tools were served without a description.** The register of sources, the
array report, the flag rate, the draw context and the marker proposal showed a
raw key where a description belongs, in both languages. They are described now,
and a raw key in a tool list fails the build.

**Asked to transcribe laboratory forms with no folder named, the tool read the
current directory.** An empty folder name resolves to wherever the process is
standing, so a call that named nothing could transcribe every PDF under the
working directory into the profile. A folder must now be named; an empty name
is refused before anything is read, a refused call no longer copies the
transcription manifest into the profile, and on success the tool prints the
same report as the command line — it used to fail on a spreadsheet export
after having written the profile. If such a call ever ran against your
profile, the points it added carry the file names they came from and can be
removed by re-importing the folder you meant.

**An unknown register was served as the patient's.** Asked for a system card in
a register that does not exist, the local API and the tool answered the
patient's card labelled with the word given. The request is now refused by
name, with the two registers listed; the command line always refused it.

**Two writing commands were listed as reads.** Recording the context of a
double draw and proposing a marker both write to the profile, and the
capability manifest called them reads. They are listed as writes of the
dictated kind — what the person said, never a value — and the skill text and
the tool descriptions no longer claim that only one tool writes: four do, and
each records what the person handed over.

**The web's source badges had no command-line twin.** The route the page reads
its «where this data comes from» badges from was mapped to the provenance
audit, a different function. `scholion sources --json` now carries the same
block under `data_sources`.

**A Russian card explained an empty genetic list in English.** The sentence a
system prints when its genetic list is not composed shipped in one language.
Both now.

**A wearables file in the oldest layout listed the years as kinds of workout.**
A file that kept workouts as «kind, then year» was carried over to the current
layout without being turned, so the summary printed «2024» as a type of
training and «Walking» as the last active year. The file is now turned on
read, once; nothing stored changes, and a file already in the current layout
is read exactly as before.

**A gene link typed into a person's own lab file no longer reads like a curated
statement.** Such a line is free text without a source; on the second look it
was printed in the same voice as a sentence that had passed the gate. It now
travels marked as the person's note, so every page shows it as one. Nothing in
the stored profile changes.

**A deletion or duplication in a position list could be read as the reference —
with an empty genotype.** Asked about a position whose event is not a
single-base substitution — a frameshift deletion, a duplication, an insertion —
the locus reader fetched the coordinate, found no row there, and answered
«assumed reference» with an empty string where the genotype belongs. A variant
of that kind is written one base upstream in a VCF as a pair of alleles of
different length, so the reader was looking at the wrong base with the wrong
instrument and calling the silence calm. Such a position is now refused by name
before any file is opened: the coordinate is given, the event is named, no
genotype is written and no reference is assumed, and the answer says what would
read it. A position list that contained such an event now shows a refusal where
it showed an empty reference.

**A position with three alternative alleles can now be held, without anyone
choosing one.** The catalogue holds one alternative nucleotide per position,
which is right for comparing genotypes and left some studied positions unable to
be entered at all. Such a position is now kept with its coordinate and the
alleles observed there and no alternative chosen — which of them a study meant is
not in the source, and this build does not pick. Every reader refuses on it by
name, before reading anything: the coordinate is given, the observed set is
named, no verdict is offered. An entry may hold a comparable pair or an observed
set, never both — one carrying both would be compared against the chosen allele
while looking as though it had declined to choose.

**A catalogue refresh could rewrite the alleles it was only meant to check.** The
documented update command refreshes the coordinates of every locus it already
holds, and it was writing into the alternative-allele field whatever the public
source returns — the full observed set, `A/T`, `C/G`. The catalogue holds one
nucleotide on each side and the genotype comparison reads one character from
each, so a run left thirty-five of fifty-five loci compound, among them the ones
dose answers are drawn from. A refresh may move a coordinate and may not decide
what the alleles are: a disagreement about alleles is now reported and never
applied, since which is right is a curation decision with a source behind it. A
position the source reports with more than one alternative allele is named and
left out rather than guessed at, and the whole file is checked against its own
invariant before anything is written — a run that would break it writes nothing
and exits non-zero, instead of printing «Written to:» over a broken catalogue.
Adding a locus no longer leaves an empty record behind when the source does not
answer.

**«Coverage not measured — » printed with nothing after the dash.** The value of
that line is the reason: no alignment file, no index, or a gene outside the
coverage table need opposite actions, and an empty one reads as text that broke
off. A reason is always printed now, including the one that says nothing said
why.

**An annotation beside the data was not looked for there.** The gene-coordinate
search consulted two declared folders, and on a machine where neither was the
one holding the file — while the live source was unreachable in the same moment
— three genes came back unresolvable with the file one directory away. The
folder holding the alignment the profile already knows about, and its
neighbours, are now part of the declared list. An explicit setting still
switches the search off entirely.

**A caveat vanished when a gene was listed rather than a position.** Each line of
a gene listing is cut to its first line, and everything a position had to add
about itself was on the lines after it. On one locus that discarded sentence was
the one that decided the answer: the catalogue's own note saying the variant read
there is the minor one for most readers, and that the main one is not a single
substitution and cannot be read from a variant file at all. The curated note, the
note about that particular read, and any refusal are now printed under their
locus in a listing as well.

**A verdict written about a gene reached nobody.** One gene carried a sentence,
written and checked, saying that no guideline exists for it and that testing it
is not recommended. The field was translated into both languages and covered by a
check — a check that the field was in the file, which is a different claim from a
reader seeing it. On the screen that gene printed two bare genotypes. Nine more
curated sentences were in the same position, across four files: how an analyte is
measured and why its published limit may be the wrong one for the reader, what a
laboratory code means for that analyte, why a missing guideline row is missing,
and which tools were examined, not taken, and what taking one would close. All of
them now reach the reader, each where its own answer is. A check enumerates every
curated field of this kind and fails on one that nothing renders, so that the
next such sentence cannot be written for nobody.

**«No meaningful pharmacogenetics for this drug» carried no date.** «Nothing is
known about this pair» and «our copy of the guidelines is a release behind» are
different facts, and the date of the copy is what tells them apart. The
drug-by-name path said it; the prescription check — the path taken before a
tablet — did not. It does now, in the command line and on the page alike.

**A mineral measured by two methods stayed one series.** An elemental analysis
(ICP) reports calcium, magnesium, zinc, copper and iron as mass per litre; a
clinical-chemistry panel reports the same elements in molar units, and the two
disagree by more than rounding — over ten per cent on the same sample. The
dictionary converted the molar result by the atomic weight and appended it to
the elemental series, so a change of method read as a change in the person; for
iron the elemental row had no unit gate at all, and a molar value carrying the
symbol was stored as micrograms unchanged. Every such element now has two
markers, each declaring its method; the elemental one accepts no molar unit, and
each is kept off the other method's forms. Serum copper by the biochemical method
is a new marker with a standard adult interval by sex. A check refuses the next
element that mixes.

**Re-importing laboratory forms could add a second point for a draw the series
already held.** When the earlier point was dated to the month — the shape older
imports wrote — and the form carried the day and clock time, nothing was
refused: the marker count stayed the same while the number of points grew, and a
trend read the same draw twice. A point of the same period now stands in for the
earlier one at every resolution: a draw replaces its day or month, a day replaces
its month, and the finer date is kept whichever order the two arrived in, with
what the earlier entry recorded about the draw carried over. A month or day that
arrives against two distinct draws inside it still replaces neither and is
reported, because choosing one would be a guess.

### What is retracted

Nothing.

### What needs recomputing


**Run `scholion ingest-labs --force <folder of laboratory forms>` — if forms were ingested by an earlier version.**
A month point beside a dated point of the same draw is collapsed into one (the
next write to that marker, of any shape, does the same), and biochemistry copper
points move from the elemental series to their own marker.

**By hand — if an elemental-iron point sits in the low tens.**
It is a molar value stored as micrograms; remove it from the series.

## v0.4.11 — 12.09.2026

### What you can do now

**A variant file with no index is read.** Every reader of a genome file used to
need an index beside it, and the tools that build one are not on a physician's
machine. Such a file is now read once from beginning to end — the catalogue's
positions in both builds, the counts that tell what kind of file it is, and the
header — and no index is written, because one written subtly wrong would be
trusted by every other tool. What that reading cannot answer is refused by
name: a question about a whole region says it needs an index and names the two
commands that make one, rather than answering with an empty list that reads as
«this gene carries no variants».

**The screen for what is worth acting on runs from an installed package.** The
secondary-findings screen over the 84 ACMG genes does not compute when asked: it
reads a table, and the pass that writes that table lived in the data-preparation
directory, which does not travel with `pip install`. `scholion acmg-scan` runs it
now, with no external tools and no index, from the person's variant file and the
published ClinVar file; when that file is missing the command prints the one
download it needs, for the build the person's file is in. Each file's build is
established from the file itself, and a crossed pair — a GRCh37 genome against a
GRCh38 ClinVar — is refused before a single position is compared, because a
crossed pair does not fail: it finds nothing, or matches a position that belongs
to a different base, and both look like an answer.

**An exome is told apart from a panel.** Breadth used to be probed in windows
that are gene-poor by construction, where an exome is empty, so an exome was
classed as a sparse panel — and that class shuts the ClinVar and ACMG paths, on
the one input where a screen for known pathogenic variants is most obviously
worth running. A second set of probes in gene-dense windows tells the two apart
by contrast. The two paths open on an exome and say what an exome can and cannot
answer; polygenic scores stay shut, because a score summed over the coding two
per cent of the genome has no distribution behind it.

**The status says which questions this input can carry, before any finding.**
Six paths — catalogue loci, pharmacogenetics, a whole region, ClinVar, the ACMG
panel, polygenic scores — each marked open or shut for this file, with the
reason; «this input cannot carry the answer» is told apart from «the annotation
this path reads has not been produced», which used to be invisible because the
narrower gate fired first and blamed the file for a missing table.

**A gene is asked of every shelf that holds anything about one.** What this build
knows about a gene sits in four places, each keyed differently — the curated
catalogue by rsID, the ClinVar scan by coordinate, the shipped ACMG secondary
findings panel by symbol, coverage by gene — and nothing joined them. Asking about
a gene read the catalogue alone and answered «not in the coordinate reference»,
which is a statement about one shelf and reads as a statement about the genome. A
clinician asked about the bile-acid transporters and was told there was nothing to
say «even in general terms from your genome», while the ClinVar table on that
machine held 386 findings.

`scholion genome --gene X` now prints a frame before the findings: what each layer holds,
that it holds nothing, or that it could not be asked and what would let it be. A
gene in the ACMG panel is recognised with no network and no annotation file,
because those 84 symbols travel inside the build — so a question about BRCA1 on a
machine that cannot reach Ensembl gets an answer rather than a shrug.

**ClinVar can be asked by gene.** `scholion clinvar --gene X` matches findings to a gene by
COORDINATE — the scan table carries no gene column, and this needs no re-scan of
the genome. A gene whose coordinates cannot be obtained is reported as unresolved,
with what would resolve it, rather than as a gene with no findings.

### What is fixed

**A row at the position was taken for the locus.** The reader took the first
variant row at a catalogue position and built the genotype from that row's own
alleles. A coordinate is not an identity: an insertion, a neighbouring
substitution or a multi-allelic row can stand on the same base, and the genotype
printed then belonged to somebody else's variant while carrying the locus's name
and the label «called». On three clinical files the alleles at the Factor V
Leiden position disagreed with the catalogue in every one. The row is now
chosen, not taken — its alleles must be the catalogue's — and the two ways of
failing to find one are named: another variant on this base, and a reference
base that is not ours at all, which is a statement about the file's build, never
about the person.

**A genome file with no index that had been cut short was read up to the cut
and answered «reference» at every position past it.** A copy or a download that
did not finish leaves such a file; a heterozygous APOE ε4 carrier could be
printed as a non-carrier under a status line saying the genome was connected.
Such a file is now refused by name — the status says the file ends before its
end — and a reading that dies part-way is answered as a failure rather than as
an empty result.

**Two shapes of a gVCF row printed the strongest label the layer has over
stretches that were never read.** A reference block whose genotype is a no-call
(`./.`, depth 0 — what a caller writes over an unread region) answered
«confirmed reference»; and a row whose only alternative is a spanning deletion
(`*`), left behind when a multi-allelic row is split and one half filtered,
answered «confirmed reference» at a base that lies inside a deletion on one
chromosome. The first is now a no-call; the second a refusal naming the allele
found.

**A deletion or multi-base change standing on a catalogue base was reported as
«the file is in another build»** — a claim about the file made from a row that
merely carried a different variant; it is now «another variant at this
position». A multi-allelic row written with a shared trailing base rendered a
heterozygote as a four-letter string labelled «called»; it now prints the
locus's own allele pair, and a genotype naming an allele of another length
beside ours is refused by name instead of concatenated.

**An owner of a genotyping chip saw a status that said the array was connected
and, six lines later, «no genome is connected» on every question** — closing
the locus catalogue and the pharmacogenetics a chip answers as designed. The
frame now belongs to the input that answered: the catalogue and
pharmacogenetics are open, a gene region is closed because a chip reads chosen
positions and a gene is a stretch nobody chose, and the screens are closed as
too narrow; a gene query on a chip refuses with the same reason instead of
proceeding without a file.

**The secondary-findings screen could report a variant a person does not carry,
and miss one they do.** A row whose genotype was not called at all — the
ordinary shape of a family file or a gVCF — was written as a finding, because
«not a reference» was the only test. A row with two alternate alleles was
matched on the pathogenic one and judged from the other, so a person homozygous
for a benign second allele was reported homozygous for the pathogenic first. And
in a file holding several samples the first column was read as the person's: a
mother's BRCA1 heterozygote, screened as her child's. Each is now a named step —
the column is chosen, the allele index is required in the genotype, a no-call is
counted and said with the result — and a call the caller itself flagged as not
PASS is written as filtered rather than decided.

**The refusal against matching two builds could be switched off by the one
variable meant to arm it.** Declaring the build of a headerless personal file
also declared it for the ClinVar file, so a declared GRCh37 against the
downloaded GRCh38 ClinVar read as «GRCh37 against GRCh37» and ran. The ClinVar
build is now read from the ClinVar file alone. And a personal file whose build
could not be told at all went into the scan with a clean «ok»; it now refuses
and names what closes it, the same way the ClinVar side already did.

**The table was written beside the variant file while the screen read it from
the genome folder**, so with the file anywhere else the command said «written»
and the screen said «not run». It now lands where the screen looks, and carries
a sidecar saying which builds it was matched in, which ClinVar release, when,
and how many positions were unread — so a stale or crossed table can be told
from a current one.

**The advice about external tools described a product that needed them.** The
first command a new person types offered four binaries and explained that
without them «the genome layer does not work at all». True when written, false
since a file without an index became readable and the ACMG screen became
runnable. It now says what the four buy — seeking a region or a whole gene, and
the wide ClinVar annotation — and what answers without them.

**The gene frame said the wrong thing about a scan that had not run.** Asking
about a gene prints, above its findings, which shelves of the build hold
anything about it. When the ClinVar scan had simply never been run, that frame
said the gene's coordinates could not be obtained — sending a person to fetch an
annotation file they did not need — and `clinvar --gene` blamed a missing or
broken index. Worse, the ACMG line printed «in it, 0 findings» for a panel
nobody had scanned: a false «clean» on a hereditary-cancer gene. Each layer now
says which of three things is true — what it holds, that the scan has not been
run, or that it could not be asked and why — and a warning that only part of the
findings table was read now reaches the frame instead of dying on the way.

**The web page still showed a genotype for a position with no row.** A position
absent from the variant file means either «reference» or «never read», and the
command line had already stopped rendering that state as an answer. The page
had not: the card printed the reference bases in large type with the caveat in
small type beside it, and a gene listing did the same for every such locus. The
page now prints a dash there, on both views.

**A prescription's status could not be set, was erased on re-entry, and stopped
drugs looked current.** No writer — command, page or API — could record whether
a drug was current, so for anyone not editing the file by hand every entry was
«no status recorded» while the wording claimed those entries predated the field.
Re-adding a name to change its dose replaced the whole entry, so a stopped drug
came back current with its start date and monitoring gone, silently. And every
listing of the regimen drew a stopped drug like one taken this morning, while the
interaction check had already excluded it. A status can now be written
(`add-med --status`, a field on the page, `status` in the API); re-adding merges
and says what it kept; and every listing — command, page, and the context handed
to a model — marks entries that are not current. A pulse course counts as
current everywhere, by one rule.

**A gene filter over a truncated scan said the gene was clear.** The ClinVar
scan is read a page at a time, and the gene filter took the page: on a profile
with more findings than one read, «0 in this gene» would have been printed
where the finding sat past the cut. The filter now compares what it read with
what exists and says when it could not see everything. In the same pass: a gene
frame that failed to build vanished without a trace and now reports itself
unavailable with the reason; a single letter of a supplement's name matched a
drug and earned it a pharmacogenetic tag, and a match now needs a whole name; a
folded provenance note could still run to three hundred characters and now has
a ceiling.

**What the person is taking NOW is asked instead of assumed.** Every comparison —
interactions, drug classes, the laboratory monitoring rules, the limitations —
ran against every name in the prescriptions file, so a drug the physician stopped
carried exactly as much weight as one taken this morning. A statin that left the
scheme on the day an azole course was replaced still produced «↑ statin
concentration, risk of myopathy», and beside it a warning about a probiotic
paused six weeks earlier.

A status decides now, and it decides by a WHITE list, so a value nobody taught the
code about is not silently treated as current. An entry with no status at all
stays current: those predate the field, and reading them as stopped would delete
real prescriptions from every check at once — silence where a warning belongs is
the worse mistake. And what was left out is named in the answer, because a red
line that is absent for a reason and a red line nobody computed look identical on
the page.

**How well a gene was read comes with the answer about it.** Coverage was a
footnote at the bottom of a report, and the question it qualifies is asked one
gene at a time. It now travels beside the answer — and only when it is worth
saying: a gene read in line with the rest of the file is left in silence, a gene
far below it says so and says by how much.

The ruler is the file's own middle, and it was measured before it was chosen. At
20× on a 30× whole genome the callable fraction runs to a median of 79.8 %, with
the best gene of ninety-three at 92 % and none at 95 %: any clinical-looking
threshold therefore fires on 89 of 93 and is measuring the shape of a depth curve
rather than anything about a gene. Against the file's own median, eight fire —
and they are the genes that are hard to sequence for known reasons, X-linked or
carrying a pseudogene. The rule travels with the sequencing depth, so it says
something useful at 30× and at 100×.

Four states, one of them silent. «In line with the rest of this file» is never
reported as «adequate»: what is adequate depends on the question, which the
product does not know. A gene the coverage table does not cover, and a profile
where coverage was never computed, both say so — a silence that means «nobody
measured» is read as reassurance, which is the same mistake as a missing row
printing as «reference».

**A position with no row in the file was printed as a confirmed reference.** A VCF
of variants has no line where the genome matches the reference, and none where
nothing was read either; the layer calls that state «assumed», and every decision
in the engine already excluded it. The last mile did not. It rendered the state in
the shape of an ANSWER — «genotype TT (reference)» — with the honest note beneath.
On a single locus a reader got both, a reassuring label and a warning contradicting
it on the next line. In a GENE LISTING they got only the first, because a listing
keeps one line per locus and the note is the second.

A physician running this over DPYD — fluoropyrimidines, where the genotype is
required before the first dose — met eight positions labelled reference, six of
which have no row in the file at all. The state is now rendered as the refusal it
is, in one line, so it survives being cut to one line.

**A genotype with no curated reading behind it says so.** A variant outside the
curated set reached the reader as a bare genotype, and the silence where a reading
should be was filled by whoever was talking: asked about COMT, the product
correctly said the variant is outside its set, and the conversation supplied «the
low-activity variant» from general knowledge with no source inside the product.
The sentence is a statement about this build's catalogue, not about medicine.

**A refusal about a drug names which silence it is.** «We could not look», «we
looked and there is no such drug» and «we looked, found it, and no guideline for it
is in our copy» wore one sentence. The third now carries the date of the guideline
copy it is a statement about — which is what tells «the literature has nothing»
from «this build is behind».

**The regimen says which entries the model can speak about at all.** A list of
supplements produced «no interactions found», which is true and uninformative:
most of them are outside pharmacogenetics and always were. Entries with a
gene-drug pair are marked; the rest are named as outside the model rather than
left to look unexamined. Long provenance notes fold to their first sentence — a
list of forty-five entries carrying a paragraph each is not a list anybody reads.

**The build says when it is old.** It reported a stale reference database and said
nothing about its own age. It now reads its own release date out of the journal it
ships and says so on the first screen once that date is old enough to matter.
Nobody is contacted to find this out: a product whose claim is that the profile
never leaves the disk does not acquire an outbound host to deliver a convenience.

### What is retracted

Answers that labelled a position «reference» where the file has no row at it. No
stored value changes — the engine never counted those positions — but a printed
page or an exported summary made before this version may carry the old label, and
for DPYD and CYP2D6 that label reads as permission to prescribe.

A genotype printed at a catalogue locus whose row carried other alleles than the
catalogue's. It was somebody else's variant under our locus's name; it is now
withheld with the reason, so a report made before this version may carry a call
that will not be repeated — the Factor V Leiden conclusion among them.

An exome classed as a sparse panel, with ClinVar and the ACMG screen reported
shut. The same file now opens both paths; the earlier statement about what that
input could answer no longer stands.

### What needs recomputing


**Run `scholion acmg-scan` — if an ACMG table was written by an earlier version.**
That table was matched without checking that the personal file and the ClinVar
file share a build; if the two were crossed, it is a silent zero or a match on a
different base. The scan rebuilds it from the files and refuses a crossed pair; a
table whose files were of one build comes out unchanged.

## v0.4.10 — 09.09.2026

### What you can do now

**The Genome tab is one page at a time, and it opens with findings.** Seven
headings on one scroll — all open, the maintenance block above every conclusion,
and the same gene appearing in four of them without any of them saying so — are
now panes of one tab. The first is neither ClinVar nor polygenic nor longevity: it
is one list, ordered by how much a line can change and marked with the source each
came from. Clicking a gene anywhere on the tab gathers what every source holds
about it into a single card: the loci and their genotypes with coverage, what
ClinVar says at those positions, what the longevity layer and the lipid card say
about that gene. Nothing was removed — the sections are still there, one at a
time, and the service text each of them opened with is folded rather than first.

**The documents inside the package open as pages, and the second opinion offers
the one written for a clinician.** The product's own output names files — «see
PREPARING-THE-GENOME.md» — and after `pip install` the only way to read one was
`scholion doc <name>` at a terminal, which the person reading the interface may
not have open. The local server now serves the same nine documents at
`/doc/<name>`, each as a self-contained page that prints on paper and pulls
nothing from the network. «Second opinion» carries a button to the one-page
description for clinicians and researchers: what the program is, what it
computes, and where it refuses to answer — meant to be handed over at the
appointment.

**The first screen is the person.** It opened with the one experiment being run
this month and reached the reader before anything about the reader. The order is
now the order the questions come in: who the data belong to — sex, age, height,
body-mass index, the reference panel — then their own indicators, then the
targets they are aiming at, then the body systems and the figure, then what is
out of range right now, then what is worth measuring, and last the focus of
attention. Every block still names the tab that owns it and goes there on a
click.

**The Profile tab is retired into that first block.** It held four cards and two
forms, and the four cards were the ones a watch measures every day; as a tab of
its own it had become the emptiest page in the product. Nothing it could do was
lost — the profile form, the manual measurement form and the list of what the
profile is still missing all open at the top of the first screen.

**The state of the genome is said in one place, including when it is not being
read.** The tab used to show a grey badge and leave the reason unprinted; a
person whose folder held more than one candidate file met «not read» in six
places and the cause in none. The state now carries the file, the assembly, the
sample, what was set aside and why — and, where a choice is open, the names with
a button beside each. The choice is kept, so it is asked once
(`scholion choose-genome` at the command line).

**«What to test» is part of the second opinion.** Every row of it is a line for
the same conversation, and it was a tab that handed half of its own list back to
the tab beside it. The routine controls travel with it, folded.

**The lifestyle brief's «needs review» can be answered.** The flag is raised when
a marker a block watches is measured after the block's wording was last read, and
until now nothing in the product could lower it: it went up once and stayed up, at
the top of the tab, above the content. There is now one button — the wording still
holds — which records the date that has always been what the flag compares against
(`scholion brief-reviewed <block>`). It also moves down the page to sit beside the
wording it is about.

### What is fixed

**Accepting the reach baseline moved the whole file to whichever machine ran
it.** A number in `test_reach_baseline.json` is not a property of the code
alone: it is what the suite reached on one interpreter, with one backend — the
two do not count a line identically — and, for at least one module, only where a
file the repository does not carry happens to sit. `--strict` had printed a
warning whenever the run and the recorded stamp disagreed; `--accept` rewrote
every number regardless, restamped the file, and reported it in one line.

There are three writing modes now, and only one of them moves the file.
`--accept` records the whole measurement and refuses when the baseline was taken
elsewhere — before measuring, since the answer never depended on the ninety
seconds. `--accept-new` records only modules that have no accepted number yet,
which is what the suite's own guard asks for when a module is added; it changes
no other number, not the overall, and not the stamp, and it does not run the
suite at all when there is nothing to add. `--rebaseline` is the deliberate
whole-file move and prints every number it lowers, old → new, before writing.

**A document name was tolerant about spelling, which was free until a route
handed it one.** `DATA_LAYOUT`, `data-layout.md` and `data-layout` are one
request, and refusing two of them teaches nothing but the exact spelling. While
the only caller was a person typing at their own prompt, that was the whole
story; a URL is composed by whoever holds it, and `../../../etc/passwd` builds a
path outside the package as readily as a name builds one inside it. The
tolerance stays and the shape does not: a document name is one file name, or it
is nothing. Anything else opens the list of documents instead.

**Seven of the thirteen rows of the goal table said «—» while the numbers sat in
the file.** Weight, body-mass index, body fat, muscle mass, VO₂max, resting heart
rate and steps come from a wearable device, and five of the goal charts drew
nothing at all. The lifestyle layer stores a measurement together with the device
that made it — two watches do not measure resting heart rate the same way, and
one series built out of both shows a step on the month the second export was
loaded — and the goal reader had been written before that was true. It looked for
the metrics where they used to sit, found nothing, and returned an empty series.
Nothing failed and nothing was logged: «—» is what that table prints when there
is no data, and there was a decade of it.

Two things follow, and both are new behaviour rather than a repair. The reader
goes through the accessor that knows the file's shape, so a file written by an
older version answers exactly as a current one does. And a row with no number now
says which of three things is the matter — nothing carries this series, the
series is empty, or more than one device measures it and the goal has to say
whose. The last of those is refused rather than averaged, and a goal may name the
device (`wear:garmin:RestingHeartRate`) to answer it.

**A number the watch already had was reported as missing, or as three weeks
old.** Some indicators are kept twice: what a person types in, and what a device
records every day. Only the first was read. Steps stood at a single figure
entered in July and were called «below target», while the device series had the
month just gone above it; sleep showed nothing at all beside seventy-five months
of nightly data; a resting heart rate from December stood as the current one in
September. The two are joined now: the newest measurement is the one shown, each
card says which store it came from and on what date, and the other store is
printed beside it rather than instead of it. A tie goes to the hand-entered
reading — a monthly mean and a measurement taken on a day are not the same
statement. Neither file is written to.

The pairing is declared once, in the shipped wearable reference, and only where
the two are the same quantity. Where they are merely similar it is left out and
the row goes on saying it has nothing behind it: intensity minutes are not
«minutes of activity», and a pairing that is nearly true prints a number nobody
can act on.

**The goal board was dated by one of the files behind it.** The heading read
«data as of» the timestamp of the wearables file, while half the rows come from
the laboratory — so a table carrying a draw from the 3rd was headed with the 23rd
of the month before. Every row carries its own date now, and the heading carries
the newest of them.

**A stored result was deciding what language the product speaks.** Polygenic
risks and longevity markers printed in Russian while the interface was English.
Neither catalogue is missing a translation — both carry every name in both
languages. The names were coming from `prs_results.json` and
`longevity_findings.json`, which are stored RESULTS: each label is a copy of the
catalogue made on the day of the run, in whatever language that run was speaking.
The catalogue now decides what a thing is called and the file decides what the
number is; a trait or a marker the catalogue does not carry keeps the name it was
stored with, because a percentile with no name is worse than a name in one
language.

**The longevity layer showed genotypes and explained none of them.** Each row
printed a gene, an rsID, a genotype — and an explanation line that was always
empty, because the page asked for a field these rows do not carry. Everything
that says what a marker MEANS was in the catalogue, in both languages, unread: what
the allele is, what a second copy does, what it argues for, what population the
direction holds in, and the papers behind it. Rows now carry all of it, sorted so
that what was found comes first and what was checked-and-quiet folds away. The
verdict and the strength of the sources are written out as sentences rather than
as the internal words they are — and a word the catalogue does not recognise is
never turned into a message key, which is how «⟦longevity.verdict.…⟧» used to
reach a reader.

**APOE says what APOE is.** The card led with «APOE — status» over two rsID
numbers, which tells a reader nothing about the gene or about their own
combination. It now opens with what the gene is and what this particular pair
means, says plainly that it is a factor and not a diagnosis, and folds the two
positions it was computed from underneath.

**A file carved out of a genome was counted as a second genome, and the whole
genomic layer went dark behind it.** Files called from the same reads at a chosen
list of positions — the loci of the catalogue, the scoring sites of the polygenic
models — sit beside the main file by design. They were recognised by NAME, from a
list of four; an output written under a fifth name became a second candidate, the
choice became ambiguous, and a refusal to guess between two files means no locus is
read at all. Nothing failed and nothing was logged. Every genomic answer said «not
read» — including a card that named two positions and said they had not been read
while the reads sat in the file beside it.

What a file is called no longer decides anything. bcftools records its command in
the header, and a pileup restricted to a list of sites, or an annotation pass over
another file's rows, is an extraction rather than the genome it came from; files
this project writes stamp themselves besides. The rule may narrow the set of
candidates and may never empty it — a folder holding nothing but extractions still
holds the person's reads — and whatever it sets aside is named with its reason
rather than dropped in silence.

**A card no longer blames the positions when the genome is not being read.** «The
PCSK9 positions have not been read» is a statement about two rows of a file that is
open. With no genome connected there is no such file, and the sentence sent a
reader to look at their sequencing when the answer was in the folder beside it.

### What is retracted

No stored value changes. Answers that said «not read» for the reason above will
now say what the reads say — which is not a retraction of a claim but the end of
a refusal.

One claim is retracted, and it was a claim about a person rather than a silence:
an indicator whose hand-entered point was older than the device series was judged
against its target on the old point. Where that judgement was «below target» and
the device disagrees, the flag changes with this version. Nothing was stored, so
nothing has to be undone — but a printed page or an exported summary made before
this version may carry the old flag.

### What needs recomputing

Nothing has to be recomputed and nothing has to be re-imported. A profile whose
genome folder holds one file behaves exactly as before; one that holds several is
asked, once, which file is the genome, and everything that was silent answers
from it. The wearable series were on disk the whole time — they are read now, not
rebuilt — so the goal charts fill in on the first run with no export and no
ingest.

## v0.4.9 — 08.09.2026

### What you can do now

**The Overview draws the body beside the radar.** The same systems, twice:
the radar as before, and a figure on which every system with a place on a body is
lit by its score. Around each mark a ring shows how much of that system was
actually measured, which is the number the radar has never been able to show. A liver scoring 100 out of 100 on one marker of three is a full
point at the edge of the radar and a ring closed a third of the way on the body.
Picking a system on either picture marks it on the other.

**The endocrine system is four systems, and each is scored on the panel a
laboratory actually issues.** One domain called «Hormones», averaged from
testosterone, IGF-1 and TSH, is gone. In its place the radar carries the thyroid
axis (TSH, free T4, free T3, anti-TPO), the adrenals (cortisol, DHEA-S), the
gonads (testosterone, DHT, estradiol) and the growth axis (IGF-1, growth
hormone). The ring beside each now says how much of that panel exists, instead of
how much of a mixture of three markers nobody orders together; a system with
nothing measured is not drawn at all rather than averaged into the picture.

**A hormone is marked at the gland that makes it**, not at the organ it is read
for: TSH and growth hormone at the pituitary that secretes them, free T4, free T3
and anti-TPO at the thyroid, cortisol and DHEA-S at the adrenals, IGF-1 at the
liver that writes it, testosterone at the gonads. Each mark carries the score of
what is made there — the average of a whole axis would print the same number in
two places and mean it in neither. Two hormones answer instead that there is no
one place to mark: DHT is converted in the tissues that respond to it, and
estradiol comes from the ovary in one person and from adipose tissue in another.
An antibody is the one named exception to the rule — anti-TPO is made by
lymphocytes, which are everywhere and mean nothing as a place, so it is marked at
the gland it is raised against. A reason is recorded beside every placement, and
beside every refusal to place.

**The pancreas is on the map.** It is a system of its own now — amylase, its
pancreatic fraction, lipase and C-peptide, the acinar cell and the beta cell
together — and insulin, which stays in the carbohydrate panel because HOMA-IR is
computed from it, is marked at the gland that secretes it. Nothing else about
carbohydrate metabolism moves: glucose, HbA1c and the index itself say plainly
that they are made nowhere in particular.

**A reference interval that belongs to one sex is no longer lent to the other.**
Six markers carry both corridors and were already handled. Every other marker
carries one, transcribed from the forms of one person — and it was borrowed by
anybody whose own laboratory printed no range. HDL's floor of 1.0 mmol/L is a
man's; so are AST's ceiling of 40 U/L, GGT's of 60, and the intervals for DHEA-S,
DHT and estradiol. Borrowed for a woman, none of them failed: each produced a
verdict, and the wrong one. Every marker a body system is scored on now declares
whether its corridor depends on sex — silence was what made the class invisible,
so silence now fails the build — and a corridor is withheld, with the reason
printed, rather than lent across that boundary. A person's own form is unaffected:
it is always preferred, and this only ever governed what fills a hole.

**A number with no reference interval beside it no longer costs its system
points.** Such a marker scored 55 out of 100 — the score for «a deviation whose
size cannot be assessed» — when there is no deviation, because there is nothing to
deviate from; and it was counted among the system's deviations, while the marker
list on the same screen said, correctly, that it was not one. It is now left out
of the score and out of that count, and still counted as measured: a system whose
only measured markers carry no corridor reports no score rather than a mediocre
one.

The five systems with no place on a body say so rather than being drawn on an
organ they do not belong to; which is which is recorded with a reason beside each
entry, and a system added to the radar without one now fails the build. The figure
is drawn male or female from the profile; where the profile does not say, it is
not drawn at all and the radar answers alone.

**Windows is a supported platform.** The package, the command line, the local
web application and the assistant skill run there, and a cell of the test matrix
now says so on every commit rather than leaving it to hope. The promise and the
check are tied together: a platform named in the package metadata with no runner
behind it, or a runner with no promise in front of it, now fails the suite.

Two things stay Unix-only and both are optional. The `crossread` wrapper is a
shell script — on Windows the installed `scholion` command is the same core, so
nothing is lost but the second name. Building a genome from raw reads drives
external alignment and coverage tools through shell scripts; every such tool is
looked for before it is used, so where one is missing the answer names it
instead of failing. The data directory on Windows is `%USERPROFILE%\.scholion`,
and `SCHOLION_REPO_DIR` overrides it as everywhere else.

**The suite can be started without a shell.** Until now the only way to run it
was a bash script, including the run the release procedure requires INSIDE the
unpacked package. There is now a second entry point written in Python that does
the same run, so a person who received the package can check it on a machine
that has no shell at all. The build carries it, and a check makes sure of that:
every way of starting the suite that the project's own automation uses must be
present in the package a recipient receives, or the build fails.

**Any gene can be asked about, not only one in the curated catalogue.** `scholion
genome --gene CASR` used to answer "Gene CASR is not in the coordinate reference"
— true about `loci.json`, which is a book of pharmacogenetic loci, and easily read
as a statement about the genome, whose reads were there the whole time. The gene
name is now resolved to coordinates from a local Ensembl annotation (or from
Ensembl live, cached afterwards), the interval is cut out of the personal VCF,
coding variants are separated from the rest by the coding exons of the canonical
transcript, and what each one does to the protein is computed against the same
reference the genome was called against — no web service is asked, and no
coordinate leaves the machine.

**A gene report prints coverage before it prints findings.** Every reassuring
thing such a report can say has the form "no such variant", and that sentence is
empty until the region is known to have been read. Read depth is computed
directly from the alignment, without samtools or pysam, and it reproduces the
project's own native callability run exactly — mean and every threshold, to the
last base, on four genes across three chromosomes. Where a piece is missing the
report names it and what would supply it: coverage without an alignment prints as
"not measured — because", and "changing the protein: 0" is replaced by "not
computed" wherever the reference was absent, because a zero and an uncomputed
number look identical on the page and mean opposite things. The two blind spots
of short reads — large exon-level deletions, and deep intronic or regulatory
variants — are printed on every answer, not only on the reassuring ones.

**Three analytes the dictionary did not know are now recognised.** A urine
albumin-to-creatinine ratio, a urine microalbumin and a **total** T3 went through
`ingest-labs` without a word: an unrecognised line is skipped, and a skipped line is
indistinguishable from a line that was never on the form. All three sit on real forms
of an ordinary laboratory, and the ratio is one of the two axes of KDIGO staging — a
value whose absence changes what may be said about the kidneys. Total T3 gets its own
table rather than joining free T3: the two are reported in different units (ng/dL
against pg/mL) and the same number under the wrong one is out by an order of
magnitude. The unit table learned `mg/g`, so the ratio prints with a unit rather than
a code.

**A polygenic percentile is printed with two quantities beside it: how stable
the number is, and how informative the model is.** A bare percentile looked
equally convincing for coronary artery disease and for intelligence, and it is
not: for the second, the choice of reference population moves the number by
some fifty points while the model's whole range separates the outcome by a
few. The two are different properties and are shown as such, under every
percentile in the `prs` report and in its JSON. Stability belongs to the
measurement — the spread of the percentile across the five reference
populations, its spread across the models scored for the trait, and the share
of the model your file actually covers. Informativeness belongs to the model —
its discrimination (AUROC), and what the score's range from the 10th to the
90th percentile does to the outcome, read per standard deviation as the
catalogue reports it. A figure that is not on the machine is named as «not
recorded» rather than left out, because a line with one number and a line
with three look alike only when the missing two are silent. The two are not
folded into one «signal to method» ratio: the effect size cancels out of such
a ratio, and what remains is the population spread written in other letters.

### What is fixed

**A corridor transcribed at one age was lent at every age, and most corridors
did not say whose they were.** The rule that keeps one sex's interval from the
other covered only the markers the body systems score; the other three hundred
and forty held a corridor and were silent about it, so a man's prolactin or
LH interval could still be borrowed for a woman whose form printed no range.
And age was not modelled at all: IGF-1 and DHEA-S depend on it more than on
sex, every laboratory bands them, and the dictionary held one corridor each.
Every corridor now declares both — whose it is, and whether age governs it —
with three states for age: independent, banded with the band on record
unknown (lent to nobody), or a band in years (lent inside it; an unrecorded
age is not lent a band). A corridor that could not be checked against a form
or a standard interval says so in a word — `unreviewed` — and is lent to
nobody until it is; nine are marked so, the estrogen-metabolite panel among
them, and that number may only shrink. PSA is a different case again: not a
man's interval but a test that exists for the male sex only, and for a woman's
profile the value is shown with that sentence rather than with a borrowed or
withheld corridor. The reason is printed beside the value in each case, and it
names what would supply the corridor: the range on the person's own form, or
the birth year in the profile.

**A value was judged by a range its own form did not print.** The rule that
the range on the person's own form wins held only at the level of the marker,
which keeps the first range it met and is not rewritten by later forms; no
stored value carried the range printed beside it. A September draw was then
judged by a corridor recorded in December, or by one entered by hand. An ionised
calcium the form called a hair under its 1.10–1.35 read as deeply low against
a 1.16–1.32 recorded months before; a DHT five per cent under one corridor was
twenty-three per cent under the other. The range printed on the form now
travels with the value and the verdict stands on it; where a value has none,
the marker's recorded range answers and the report says so; and a series whose
corridor changed between draws says that its values compare and its flags do
not.

**A bound printed instead of a number lost its sign.** A laboratory that
cannot quantify a value prints the limit — «< 0.09 nmol/L» — and the ordinary
form reader stored the number without the sign, as if 0.09 had been measured.
The engine has carried a censoring mark for such values all along, and two
special readers (flora, titres) supplied it; the common path did not, and a
series of «below the limit» results read as a level that later rose. The sign
is now read from the text immediately before the value — `<`, `>`, `≤`, `≥`
and their spelled-out forms — so a bound in a reference column further along
the row cannot be mistaken for it.

**Calcium measured by two methods was filed as one series.** Elemental
analysis (ICP) prints calcium in mg/L; a biochemistry panel prints total
calcium in mmol/L; one marker caught both and converted the second into the
first by molar mass. The two methods disagree beyond rounding — thirteen per
cent on the same person two months apart — and a series that holds both
presents a change of method as a trend. Total calcium is now a marker of its
own, the elemental one no longer reads a biochemistry form, and the rule is
written where the next mineral will meet it: a series belongs to a method, not
to a substance — a unit conversion is legitimate within a method and not
across methods. Magnesium and the other minerals have not been checked yet.

**A form that printed «HOMA-IR» in the Cyrillic alphabet was not read.** The
dictionary knew the index by its Latin spelling only; the file was refused
with an honest reason and the value had to be entered by hand. Both alphabets
are recognised now, and «insulin resistance index» as well.

**A report could not be redirected to a file.** `scholion labs > labs.txt`, and
every other command whose output was piped or saved rather than read on screen,
ended in a crash partway through — thirteen of sixteen commands measured. The
reports are written with arrows, dashes and guillemets, and the encoding a
redirected stream inherits from the system cannot always carry them. Output is
now written as UTF-8 whatever the system would have chosen, so a saved report is
the report. A character that still cannot be written appears as its own escape
rather than as a question mark, so what was lost is visible.

**Files were read in whatever encoding the machine assumed.** A genotype table,
a cached answer or an export written as UTF-8 and read back through a national
code page does not fail — it decodes, wrongly, and where the read also asked for
replacement characters the wrongness was silent by construction. Every text read
and write in the package now states its encoding, and a check over the source
refuses a new one that does not. Twenty-nine places were corrected; six of them
were never reached by any test, which is why the check reads the source rather
than watching a run.

**Two programs writing the profile at once could lose a change.** Where the
system offers no lock between processes — Windows has none — the local web
application and a command line each read a file, changed one field and wrote it
back; whoever finished last erased the other, with no error anywhere. A lock the
program takes itself now covers that case, and where it is already held the
second writer says who holds it and stops rather than writing over them. A lock
left behind by a run that died is taken over after a minute.

**The update button reached for a shell that need not exist.** On a machine
without one it now says so in a sentence, instead of showing the failure of a
program it tried to start. The search path it builds is also joined the way the
platform joins it, rather than always with a colon.

**The monthly reanalysis stopped at its first step.** The ClinVar annotation
(`annotate_clinvar.sh`) died with «GEN: unbound variable» on the first scheduled
run: the branch that looks for a reference FASTA named a variable that belongs
to the orchestrator calling it, not to the script itself, and `set -u` stopped
it at the first of three such places. All three now use the script's own
`GENOME_DIR`. The annotation has not yet been re-run against the fresh ClinVar
release; until it is, findings stand on the release recorded in the profile.

**A profile that spelled its sex «f» or «m» could be measured against the wrong
reference row.** Several spellings of sex are accepted when a profile is
written — «f», «female», «woman» and their male counterparts — but the reader
that picks the applicable row of a multi-row reference interval compared the
raw spelling with «male»/«female», so for any other spelling the sex half of
that choice was silently off: a men-only row could fit a woman, a women-only
row a man. The reader now recognises sex the way everything else does. A
profile created by `scholion init` was never affected — it can only write the
two spellings; the demonstration profile and imported or hand-edited profiles
were.

**The version shown could be another installation's.** With any `scholion`
distribution installed on the machine — an older one from the registry, kept
for comparison — a copy run from its source tree reported the installed
number rather than its own, in the server's header and in `--version`. The tree
now answers for itself; an installed copy still answers from its metadata.

**The polygenic-score layer could stop starting on a machine that had run it
the week before.** The scoring sidecar is fetched into an isolated environment
on first use, and its own dependency declaration left one library unbounded; a
newer major version of that library reached the index in August, and any fresh
cache took it — the sidecar then died at start-up, before the first request,
and `prs`, its page in the web application and the monthly reanalysis all
reported a server that «exited without an answer». The resolution is now pinned
below that major version wherever the sidecar is launched, from the application
and from the setup script alike; a constraint already set in the environment
by whoever runs it is respected rather than overruled. The message for a server that
exits without answering now carries its exit code and names this cause and the
pin, so a recurrence reads as «the pin was not applied» rather than as silence.

**Every polygenic-score computation went to the server twice.** Two optional
settings of the report — a wider pool of candidate models, and the models of
child traits — are not accepted by the pinned sidecar; they were sent with every
trait, refused with every trait, and each trait was computed again without them,
so a full panel cost double for a setting that was never in force. A refusal is
now remembered for the rest of the run and the panel pays it once. The two
settings are honoured only by a newer sidecar than the pinned one, and the help
says so.

**Three models were computed for a trait and one was shown.** The client asked
the server to score several models per trait and then to return only its
favourite, so the spread between them — for a trait whose score explains five
per cent of the variance, half of the answer to «how much of a number is
this» — never reached the page. Every scored model now comes back, the spread
is stored with the panel and printed as part of the percentile's stability.
And the count of candidate models left unscored — eighty-five of eighty-eight
for coronary artery disease — travelled without its rule; the rule is the
report's own `--models` limit, and the count now says so wherever it appears.

**A panel entered by hand and then re-imported from its form stood twice in
every series.** The form prints the draw hour, so the re-import arrived with a
finer date than the day entered by hand; the two did not match as strings, and
the second point joined the series beside the first — identical values, one
draw, nothing reported. Trends were then computed against a «previous point»
that was the same blood. A point now stands in for every point of the same day
whatever precision either carries, the more precise date is the one kept
whichever order the two arrived in, and what the earlier entry recorded about
the draw — its context, its source — travels to the replacement instead of
being erased on every re-import. The importer names each replacement. The one
case that cannot be decided — a bare day arriving against two timed draws of
that day — is still reported and left to the person.

**One file the reader could not handle stopped `ingest-labs` for the whole
folder.** A traceback, every form after it unread, and no indication of which
file was at fault. Each file is now read on its own: a file that raises is
listed among the files nothing was taken from, with the exception's type and
text, the rest of the folder is processed, and the command exits with a
non-zero status so that a partial run is not mistaken for a clean one. The
failed file is tried again on the next run rather than remembered as done.

**The list of files already read was shared by every profile on the
machine.** `ingest-labs` and `ingest-studies` remembered what they had read in
the application-wide cache rather than beside the profile, so anyone working
with more than one profile — a family member's, a temporary one — shared a
single list, and a form already read for one profile could be silently skipped
for another. The list now lives in the profile directory, one per profile
(`ingest_labs_manifest.json`, `ingest_studies_manifest.json`); on the first run
after upgrading the old list is carried over from the cache and the run says so
once, so no form is read as new because of the move. Both loaders report the
carry-over as a `manifest_moved` field in `--json`.

**The reach baseline could not be accepted for a commit that added a module.**
The suite fails when a module of the package has no accepted reach, and its
message says to run `--accept`; `--accept` in turn refused to record a suite
that had failed. Adding any module therefore closed a circle the tool could not
be talked out of, and the only exit was to seed the new module in
`test_reach_baseline.json` by hand. `--accept` now enters missing modules at
0.0 before the suite is measured, drops entries whose file is gone, says which
it did, and records the measured numbers over the seeds. When the suite fails
anyway the file is put back exactly as it was. `--strict` is unchanged and
still fails on a module nobody has reviewed.

### A series break

`knowledge/lab_markers.json` now records whose reference interval each scored
marker holds, and a corridor that belongs to one sex is no longer lent to
another. On unchanged input that changes the verdict in one place: a profile
whose sex differs from the corridor's, for a marker whose own laboratory form
printed no range, used to receive a flag and now receives the value together with
the reason no corridor is shown. Thirty-six markers can be affected — the six the
body systems score (HDL, AST, GGT, DHEA-S, DHT, estradiol) and thirty more
whose adult interval is sex-specific: the red cell count and ESR, iron and
transferrin saturation, the gonadal and pituitary hormones, calcitonin,
osteocalcin, leptin, PSA, urine creatinine and the estrogen metabolites — and
only where the range was borrowed: a person's own form has always been
preferred, and this governs nothing but the hole it filled. The remedy is the
form itself, or a range recorded by hand.

Age is the same line, one axis over. Four markers whose interval every
laboratory bands by age — IGF-1, DHEA-S, inhibin B and total PSA — held one corridor
each, transcribed at one age, and lent it to everybody. The band on record is
not known, so the corridor is now lent to nobody and the reason is printed; a
value that used to receive a verdict against it receives the value alone. The
same remedy applies. Every corridor in the dictionary now states both — whose
it is, and whether age governs it — and a marker that does not fails the suite,
because absence was how the question used to be spelled.

A verdict now stands on the range printed beside the value rather than on the
range first recorded for the marker. For a value whose own form printed a
different range from the one on record, the flag can change either way; the
value does not. Which ruler each flag stands on is printed, so the two can be
told apart on the page.

The score of a body system also moves where a measured marker had no corridor:
such a marker used to take 45 points off its system and no longer takes any. The
overall health index is a mean over systems, so it moves with them. Values from
either side of this line belong on one chart only with a note.

### What is retracted

No stored value changes and no conclusion is revisited. One correction above —
the spelling of sex — is to how a reference row is chosen for a profile spelled
other than «male»/«female»; what that asks of such a profile is under the next
heading. The rest are to how reports are written and how files are read.

### What needs recomputing


**Run `scholion ingest-labs --force <folder of laboratory forms>` — if forms were ingested by an earlier version.**
The folder is read again, and for each of these what an earlier version stored
is corrected: reference intervals picked without the sex filter, for a profile
whose sex is spelled other than «male»/«female»; urine albumin-to-creatinine
ratio, urine microalbumin and total T3 lines that were left out; a hand-entered
day beside the same draw's timed re-import, collapsed into one point that keeps
the timed date, with every collapse named; the range each form printed, which
replaces the marker's recorded range a value was judged by until then; and the
sign of a bound («< 0.09»). Points entered by hand before the form was read keep
whatever was typed.

**By hand — if a biochemistry total calcium was ingested by an earlier version.**
It sits in the elemental series converted to mg/L. Reading the folder again files
it under total calcium, but the converted point is not removed from the elemental
series; remove it, or the report shows a method change as a trend.

**Run `python3 -m scholion.prs report` — if a polygenic panel was computed by an earlier version.**
Such a panel carries no spread across models and no AUROC, and the report prints
«not recorded» in their place. Recompute it, then rebuild the panel with the
panel-build step of the genome guide; the spread across reference populations
comes from the ancestry-sensitivity step of the same guide, run once per panel.

**By hand — if a report saved from an earlier version stops short.**
It may be truncated at its first unwritable character; running the same command
again produces the whole report.

## v0.4.8 — 31.08.2026

### What you can do now

**`ingest-studies` names every file it took nothing from.** The report used to be
four counts, and the number of files seen was never reconciled against them: a
file that was read and then dropped moved no counter at all. Each such file is
now listed with the reason it produced nothing — the PDF gave up no text, it is a
laboratory form that the other loader owns, it reads like a study but no
conclusion could be lifted out of it, or this loader cannot place it at all. The
counts and the named files add up to the files that were looked at.

**A PDF holding several studies is reported with what is inside it.** A discharge
summary — several examinations, and often a laboratory panel, in one file — is
listed section by section with each section's own date, together with the plain
statement that this loader cannot split such a file yet and that nothing from it
reached the profile. Until now such a file was declared a laboratory form and
handed to the laboratory loader, which dropped it for a reason of its own, and
neither report held a line about it.

**A decision you made about a wearable series survives the next import.** A
rebuild is written from the export every time, so an edit made inside
`wearable_trends.json` was lost at the next run — a weight point removed by hand
as physically impossible came back as soon as a fresh export was read. Put the
decision in `profile/wearable_corrections.local.json` instead: `remove` or
`replace` a month of one metric of one device, with a reason. The import applies
them over the rebuilt series and says which it applied, which it refused and why,
and which no longer match anything — a reason is required, and a correction
without one is refused rather than applied. `LOADING-DATA.md` describes the file.

**A monthly point from a wearable now says what it stands on, and a movement too
small to see is no longer given a direction.** Each month carries the number of
days that held a reading, the days the month had, the median beside the mean and
the spread. From those the lifestyle answer works out the smallest difference the
data can tell from its own sampling, and when a shift is smaller than that it says
so instead of naming a direction — for a monthly sleep series measured on a
typical month that threshold is on the order of several minutes, and movements
under it were previously reported as improvement or decline. A month measured on
part of itself — nineteen nights of thirty-one — says that too. A series written
by an earlier version carries no sample description and behaves exactly as before:
nothing is invented for it.

**A laboratory arrow says whether the change can be told from the marker's own
scatter.** «↑ 44 % since the previous measurement» is arithmetic on two numbers
and it stays; what follows it now is whether this marker's own history has ever
shown itself able to tell a change that size from its own wobble. The threshold
is measured from that history — no outside table is required and no coefficient
is assumed — and it is reported with it, so it can be argued with. A rule that
suggests a test because a marker is trending no longer fires on a movement the
series cannot distinguish: a suggested test costs a real draw of blood. Where
the history is too short to support the statement, none is made.

**A genotype read from a VCF says how well the reads actually supported it.**
Depth said how many reads there were; nothing said how they were divided. A
heterozygote whose reads split 15/85 — a mosaic, a duplicated region, an
artefact — was presented in the same words as one that split evenly. The allele
fraction and the caller's own quality score are now read, and everything worth
confirming about a call arrives as one list with the measurement that raised each
entry, instead of three separate flags a reader had to know to look for. These
are quality-control heuristics and they say «have this confirmed by another
method», never «this is wrong».

**A gene a variant file cannot answer now says so, instead of showing a tag
SNP.** CYP2D6 decides codeine, tramadol, tamoxifen and the tricyclics, and it is
settled by the full diplotype — copy number and phase — not by any single
position. Asked about codeine, the answer used to print the gene, the word
«important», a bare genotype and the promise that a full genome would bring the
rest, which for this gene is not true. It now states that a diplotype is what
decides it, shows the tag SNPs under a name that says what they are, and names
the two things that actually close the gap: a star-allele call over your reads,
or a laboratory report that states the diplotype — the only route open to
somebody who has no alignment file. A diplotype already on file is used as
before, and the sentence beside it now follows where it came from instead of
asserting the caller's name over both cases.

**The genes a «nothing found» cannot rest on can be handed to a laboratory.**
The coverage table knew which genes were under-read and could give the list to
nobody: a percentage names a gene, and re-reading something needs coordinates.
The intervals the measurement was made over are now recorded and the weak list
exports as a BED, worst gene first, each interval carrying its own percentage.
The track line states that these are gene loci with a margin rather than coding
sequence — a small dropout inside an exon barely moves a locus-wide percentage,
so the file is a worklist of genes to look at again, not a map of the bases that
were missed. A coverage table written before the coordinates existed is refused
with the run that would fill them in: a gene name is not an interval and none is
invented from it.

### What is fixed

**A conclusion written in mixed case produced an empty record, and an empty
record was dropped without a word.** The recogniser accepts the heading whatever
its case; the extractor beneath it demanded the word in capital letters and
required the text to begin on the following line. A document that writes the
heading in ordinary case, with the text after a colon on the same line, was
therefore accepted as a study and then yielded nothing at all. Both shapes are
read now, and the printed disclaimer that contains the same word is not mistaken
for the finding.

**A laboratory point is dated in one of three shapes, and anything else is
refused.** A month, a day, or a day with the clock time of the draw — the last
one because two draws can fall on one day and a key no finer than the day loses
the second. Nothing checked the string before: a value that was not a date at all
would have become a key of the series and been sorted and charted beside real
dates. And when the same period is already present at another resolution — a
month point and a dated point of that month, one measurement standing twice — the
import now says so rather than quietly holding both.

**A doubled measurement was found and then not mentioned, for anyone whose
results arrive as a table.** The importer notices when one measurement ends up in
a series twice at two resolutions — a month point and a dated point of that
month. It said so for results read out of a PDF and stayed silent for results
read out of a CSV or TSV export, because the two kinds of file reach the profile
by different routes and only one of them carried the report. The doubling was
detected in both cases and shown in one. Both now say it.

### What needs recomputing


**Run `scholion ingest-studies --force <folder of documents>` — once, if studies were ingested by an earlier version.**
Studies that were dropped in silence may now be read, and whatever is still not
taken is named in the report.

**By hand — if you want the BED of under-read genes.**
Measure coverage once more: the measurement now records the intervals its
percentages were taken over, and a table produced before it did does not carry
them.

**Run `scholion ingest-garmin` — once, if Garmin months were imported by an earlier version.**
Existing months gain the description of their sample; the values themselves do
not change, so charts and comparisons are unaffected. Until an import has run, a
series simply has no sample description and no statement about what is
distinguishable is made for it.

## v0.4.7 — 27.08.2026

### What you can do now

**The Ouroboros Hub skill now says where your files go, on a page of its own.**
Installed there, Scholion arrives by a click into a machine whose paths you have
never seen and cannot list. Until now it registered thirty tools and nothing
else: no data directory was created, and the first thing the skill said was a
tidy report — `markers: 0`, `genome: not connected` — about a person it had
never been given anything about. A statement of absence, phrased as a finding.

Enabling the skill now adds a **Scholion** tab to the Widgets page, and that tab
is the first thing to read:

- it names the data directory this installation actually uses, and the exact
  folders for laboratory forms and for the genome;
- a button lays that directory out — empty templates, plus a README in every
  folder saying what belongs in it. Pressing it a second time writes nothing,
  and it never touches a file that already exists;
- if your files already live in a folder of their own, a field points at that
  folder instead of copying them.

The directory the skill creates is one the host keeps, so it survives restarts
and is not scattered inside a container. To put it somewhere else, set
`SCHOLION_REPO_DIR` (the whole layout) or `SCHOLION_PROFILE_DIR` (the profile
alone) in the host environment before enabling — either is respected, and
nothing is moved.

Nothing changed for the command line or the local web application: the same
layout is what `scholion init` has always written, and the tab creates it
through the same command.

### What is fixed

**A freshly created, empty directory was described as a connected genome.** The
introduction the skill prints was reading the genome section of the report as
«present» rather than reading its ready flag, so a person who had just pressed
the button — with no VCF anywhere — was told the genome was connected and then
handed a list of loci «still unread». Both halves were wrong and the second made
the first look substantiated. It now says `not connected` until a VCF is
actually there, which is what `scholion genome-status` said all along.

**A profile that cannot be read is no longer reported as an empty one.** If a
file in the profile is malformed, the tab now says so, with the reason, instead
of showing zeroes that look like a person with no history.

### What is retracted

Nothing. No stored value changes, and no conclusion drawn from a previous
version needs revisiting: the corrections above are to what the skill said about
its own state, never to a reading of anybody's data.

### What needs recomputing

Nothing.

## v0.4.6 — 25.08.2026

### What you can do now

**A tool that installs skills from a repository can now find this one.**
`npx skills add` and its kind read a repository rather than a package: the root
if it holds an entry, then `skills/`, then the agent folders — the documented
shape being `skills/<name>/SKILL.md`. None of those existed here, so the entry
was reachable only by such a tool's fallback recursive search, at a path whose
folder is called `skill` while the file inside calls itself `scholion` — and the
format requires those two to agree.

The published repository now carries `skills/scholion/`, and it holds the entry
and nothing else. That is the licensing decision rather than economy: what is
published as a skill is the entry; the long instruction and the canon of rules
stay with the package they are printed from, under their own licence, and a
folder carrying both would put one licence over two bodies of text.

Unlike the standalone skill folder in the downloadable archive, this one is not
excluded from the repository — a tool fetches it from there, and a folder kept
out of version control does not exist for the purpose it was made for.

**An assistant that reads skills from a folder can now be given this one, in one
line.** Several hosts read the same path, with no registry, no account and
nobody's moderation in between — and until now nothing in this project mentioned
it:

```bash
mkdir -p ~/.agents/skills/scholion
cp "$(scholion skill --path)" ~/.agents/skills/scholion/SKILL.md
```

That single file is the whole installation, which is what makes it worth doing
and also what it had to be repaired for. **The entry did not name the tool
server.** A host with a plugin mechanism finds `scholion mcp` through its own
means; a host that reads only this file had no way to learn the door existed —
so the door built for exactly those runtimes was invisible to them. It names the
tool server and the in-process module now, and says that neither writes to a
profile.

**And it pointed at reference texts that a one-file install does not have.** The
full instruction and the canon of safety rules sit beside the entry in the
downloadable bundle and nowhere else; the entry named them by path regardless, so
a model following the pointer would report a missing file rather than ask for
what it needed. Each is now named twice — the path, for the bundle, and the
command that prints it out of the installed package, for every other way in.

`scholion capabilities --json` lists this door beside the others, derived from
the build: the size of the entry and whether it names the tool server are read
off the file rather than asserted about it. `scholion doc connecting-an-agent`
describes it in words, and the heading there has stopped counting the doors —
it said «four» through the arrival of a fifth and a sixth.

**The checks now run on the oldest Python the package promises, before a release
rather than after one.** `pyproject.toml` says this runs on Python 3.10 and
later. That sentence is a promise to everybody who installs it, and until now
nothing checked it before a release: the matrix that runs every promised version
lives with the published repository, so it answers about a version that is
already out.

It answered twice in two days, both times too late — once with a release build
that failed and never reached the registry, once with a red matrix on a version
that had. Both were the same shape: a repair verified on one interpreter and
promised about four.

`./run_tests.sh` now runs the whole suite a second time under the oldest promised
version, taking that version from the promise itself rather than from a number
written into the script — `scholion doc contributing` describes how to run the
checks that come with the package. Where `uv` is available it fetches the interpreter and
caches it; where it is not, the run says the check could not be made instead of
passing over it in silence. `SCHOLION_SKIP_OLDEST=1` skips it while editing.

Three places name that floor — the promise, the versions the matrix runs, and
this step — and a test now compares them, so a version can no longer be promised
and never run, or run and never promised.

## v0.4.5 — 24.08.2026

<!-- This entry is open. While 0.4.5 is unpublished, further work is added here
     rather than under a new number. Refresh the date in the heading before
     publishing, and delete this note. -->

### What was wrong

**The README told you the plugin adds fourteen tools. It adds twenty-nine, and
there are not four doors but six.** Neither sentence was wrong when it was
written; both stopped being true and nothing was obliged to notice. They are
corrected, and the numbers are gone rather than updated: a count kept by hand
beside a count the build derives will go stale again, so the README no longer
writes one and a check refuses a new one.

The installation table for a skill folder was rewritten against each product's
own documentation rather than from memory. `~/.agents/skills/` is the shared
path and two runtimes read it as they are; the others keep their own folder and
take the same single file. The table carries the date it was checked, because
paths move and that is the kind of claim that goes stale quietly.

The published format's own limits are now a test: the name a valid slug matching
its directory, the description within its ceiling, the body within the
recommended length, and no frontmatter field the format does not define. They are
somebody else's rules, which is exactly why they are worth checking — a file that
breaks one is refused with a message about YAML, and the person meets that
instead of this product.

**What the data cannot answer reached every way in except the one most people
use.** `scholion limits` says what cannot be said from a profile and what would
close it — and the page had never asked for it. Not a broken renderer: no screen
called that route at all, so the whole layer existed for the command line and for
an assistant and for nobody sitting in front of the interface.

The Profile tab now opens with what the profile is still missing and what each
absence costs — a reference interval withheld rather than guessed, the age-banded
rows of a form that cannot be read — with the fields to fill them in directly
below. And the caveat about which reference panel a percentile is a position
inside is printed beside the percentiles, where the number is met.

A check now holds the general rule: every route the server answers is asked for
by the page, or is named with the reason it is not. Two writes are named — one
superseded, and one an acknowledged gap: conclusions from a doctor can still only
be loaded from the command line.

**A percentile said which population it was a position in, and the answer could
be wrong.** The reference panel a polygenic score is computed against decides
what the percentile means: against another population it is not your position.
The report carried a panel and, beside it, a claim that the panel had been
settled — and those two came from different places. The claim asked the profile
whether a panel was known; the number had been computed against whatever the
scoring run was given, which fell back to Europe in a function signature.

While a panel could only be typed in by hand the two rarely disagreed. Once it
began to be determined from the genome, they came apart for everybody who had
one: the screen said the panel was settled and showed percentiles computed
against a different one. No error and no gap — an ordinary number with a wrong
sentence attached.

Three facts are reported now where one was: the panel the stored numbers used,
whether it was chosen or fallen back on, and which panel applies today. Where
they disagree the report says so beside the number and names both, rather than
leaving it in a field. A result computed before any of this was recorded cannot
say which panel was chosen, and that reads as «cannot say» rather than as «yes».

`scholion prs` takes the panel from the genome unless told otherwise, and a run
that had nothing to go on says it used a default.

**Determining that panel is a step of preparing a genome now, and it can be
asked what it does before it does it.** The tool that answers it existed and was
reachable from nowhere — no command, no mention in the guide. Worse, it took no
arguments and checked its inputs while being imported, so any invocation at all
ran the whole job: about three hundred requests to a public database over
somebody's real genome, from what was meant to be a question. It has an entry
point now — `--help` explains, `--dry-run` names what it would read and write and
fetches nothing, and a missing input is refused by name with where it comes
from. The guide carries it in the sequence, at the point where the data it needs
exists.

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

**The facts the application cannot derive can be given from the page at last.**
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

**A body measurement in a bundle is now kept, not dropped.** This product has
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

**A form the interface never showed.** The page holding sex, year of birth and
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

**«1 markers are printed without a reference range».** A number and the word
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


Nothing stored changes value and the knowledge base is untouched, so series
already on a chart stay comparable. What changed is what can now be read.

**Run `scholion genome-status` and `scholion overview` — to see what can now be read.**

**Run `scholion ingest-labs <folder>` — if laboratory PDFs were refused because no draw date could be found.**

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


**Run `scholion labs` and `scholion overview` — if their output was saved with an earlier version.**
The thresholds that depend on sex have changed.

**Run `scholion drug <name>` — if a star-allele table or a called diplotype is in the profile.**
For CYP2D6, CYP2C19, CYP2C9, DPYD, TPMT, NUDT15, SLCO1B1 and the rest of the
eighteen.

**Run `scholion acmg` and `scholion prs` — if their output was saved with an earlier version.**
The ACMG report now carries coverage; sex-specific polygenic traits are withheld
and the method caveats are printed.

**Run `scholion ingest-labs <folder>` — if the folder holds non-PDF files or an American form.**

**Run `scholion genome` — on a GRCh37 file, a consumer array, a multi-sample file, a folder with several genomes, or a file that was never actually readable.**

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


**By hand — if your VCF came through `fastq_to_vcf.sh`.**
Re-run the extraction: the target now reaches five markers it did not before.
Genotypes read from a full-genome VCF produced elsewhere are unaffected — only
the targeted route was narrow.

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
