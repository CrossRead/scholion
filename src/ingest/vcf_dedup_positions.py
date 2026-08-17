#!/usr/bin/env python3
"""DEPRECATED — do not use. Kept in order to explain why its rule is harmful.

The script collapsed positions carrying several rows by the rule "keep the
SNP-level row". Measurement on real data (prs_verify.py --all) showed the rule
to be wrong: among the overlaps of PGS models with contested positions, most
turn out to be INDEL variants of the models themselves. "An SNP outranks an indel"
discards exactly the row such variants need, trading double counting for a lost dose.

The correct solution is an allele-aware choice of row for the specific models:

    python3 src/ingest/prs_verify.py --emit-fixed <out.vcf> [--vcf <target>]

and in the regular pipeline prs_genotype_sites.sh does this itself after genotype calling.
"""
import sys

sys.exit(__doc__)
