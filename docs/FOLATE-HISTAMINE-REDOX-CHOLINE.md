# Folate, histamine, redox and choline position panel

This is an on-demand, cross-system panel of 16 positions in eight genes. It has
no aggregate risk score or laboratory half. Open the knowledge description with
`scholion panel folate_histamine_redox_choline`, or read the positions against
the active genome with `scholion system folate_histamine_redox_choline`.
Both entry points are also available in the web interface's on-demand cards.

| Gene | Positions |
|---|---|
| MTHFR | rs1801133, rs1801131 |
| COMT | rs4680 |
| AOC1 (DAO) | rs10156191, rs1049742, rs1049793, rs2052129 |
| MAOA | rs6323, rs1137070 |
| GSTP1 | rs1695, rs1138272 |
| GPX1 | rs1050450 |
| NOS3 | rs1799983, rs2070744 |
| PEMT | rs7946, rs12325817 |

## What is curated

The position list and forward-strand coordinates are verified for GRCh38 and
GRCh37: Ensembl REST and NCBI dbSNP esummary agree on all 16 positions in both
builds. The catalogue adds 13 loci; MTHFR and COMT were already present. A
multiallelic dbSNP position is represented by the specific change in the list;
that alternative allele is not an assignment of risk.

The panel reuses the existing MTHFR and COMT interpretations and their sources,
evidence levels and review records. The 13 new rows carry references and the
population of their research context, without assigning a risk allele or a
sentence for a genotype. Their clinical review remains open. A request to add a
list is not a clinical sign-off of every possible interpretation.

## Genotype and phenotype

A genotype must be checked against symptoms, measured laboratory values, diet,
exposures and treatment history. Absence of an allele does not demonstrate
normal enzyme activity or exclude a clinical condition. These positions do not
establish nutrient deficiencies, brain neurotransmitter concentrations or
supplement doses. Research-context rows at C or D are hypotheses, never
personal clinical conclusions. MAOA is on chromosome X: male calls are read as
hemizygous, and the two SNPs do not genotype the promoter VNTR.

## Existing data

Run `scholion genotype-sites` when an alignment and the matching reference are
available: a site file made for the previous catalogue lacks these positions.
A missing record in a variant-only VCF remains reference-or-unread, never a
confirmed reference genotype. The card preserves that distinction and reports
unread positions. No laboratory re-import is needed.

Personal interpretations supplied for a particular case stay with that person's
local files. They are not part of the public panel or its review signatures.
