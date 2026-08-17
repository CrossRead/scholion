#!/usr/bin/env python3
"""Precise parsing of the EVOGEN-GENOME report straight from the PDF, WITH COLOUR.

Why colour: in the report the "ordinary" variant of a gene is marked green, the
"detected particularity" orange. The colour carries meaning the text layer does not.
This makes an internal consistency check possible: the colour of the patient's genotype
must match the colour of the row's conclusion. A mismatch = a defect of the report
(exactly of the kind found in one of its rows).

Output: evogen_pdf_rows.json — one row per polymorphism.
"""
import json, os, re, pathlib, collections
import pdfplumber

PDF = os.environ.get("EVOGEN_PDF", "")   # path to the laboratory PDF report
if not PDF:
    raise SystemExit("Give the path to the report: EVOGEN_PDF=/path/to/report.pdf "
                     "python3 src/ingest/parse_evogen_pdf.py")
OUT = pathlib.Path(__file__).parent

GREEN = (0.078431, 0.537255, 0.172549)
ORANGE = (0.968627, 0.572549, 0.196078)
ORANGE2 = (1.0, 0.501961, 0.0)
GREEN2 = (0.0, 0.501961, 0.0)

RS = re.compile(r'^rs\d{3,}$')
GTOK = re.compile(r'^(?:[ACGT]{2}|[ACGT]/[ACGT]|[ACGT-]+/[ACGT-]+|[ACGT]{3,})$')

def colname(c):
    if not c:
        return 'black'
    t = tuple(round(float(x), 3) for x in c)
    def near(a, b, eps=0.06):
        return len(a) == len(b) and all(abs(x - y) < eps for x, y in zip(a, b))
    if near(t, tuple(round(x, 3) for x in GREEN)) or near(t, tuple(round(x, 3) for x in GREEN2)):
        return 'green'
    if near(t, tuple(round(x, 3) for x in ORANGE)) or near(t, tuple(round(x, 3) for x in ORANGE2)):
        return 'orange'
    if near(t, (0.0, 0.0, 0.0)):
        return 'black'
    if near(t, (1.0, 1.0, 1.0)):
        return 'white'
    return 'other'

# Section map — the printed page each one starts on (from the contents, p. 3).
# The names are copied from the report itself and stay in the report's own language:
# they have to match the headings printed on the paper the reader is holding.
SECTIONS = [(6,'Краткий отчёт'),(18,'I. Клинически значимое'),(19,'Наследственные заболевания'),
 (24,'Онкориски и опухолевые синдромы'),(30,'Моногенные ССЗ'),(32,'Моногенные ССЗ — кардиомиопатии'),
 (34,'Моногенные ССЗ — аортопатии'),(36,'Моногенные ССЗ — нарушения ритма'),
 (38,'Моногенные ССЗ — врождённые пороки'),(40,'Моногенные ССЗ — другие'),(42,'Фармакогенетика'),
 (51,'II. Мультифакторные заболевания'),(53,'Мультифакторные — сердечно-сосудистая'),
 (56,'Мультифакторные — эндокринная'),(61,'Мультифакторные — нервная'),(67,'Мультифакторные — иммунные'),
 (73,'Мультифакторные — дыхательная'),(77,'Мультифакторные — опорно-двигательный'),
 (80,'Мультифакторные — глаза'),(85,'Мультифакторные — мочеполовая'),(89,'Мультифакторные — пищеварение'),
 (92,'Мультифакторные — кожа'),(95,'Мультифакторные — беременность'),(98,'Профессиональные заболевания'),
 (113,'COVID-19'),(120,'III. Образ жизни'),(121,'Нутригенетика'),(173,'Спорт и красота'),
 (196,'Генетика в повседневной жизни'),(199,'Повседневная — черты характера'),
 (205,'Повседневная — циркадные ритмы'),(208,'Повседневная — долгожительство'),
 (211,'Повседневная — музыкальные способности'),(213,'Повседневная — потребление кофе'),
 (215,'Повседневная — похмелье'),(217,'Повседневная — вкусовые предпочтения'),
 (221,'Повседневная — световой чихательный рефлекс'),(223,'Генетика происхождения'),
 (227,'Дополнительная информация')]

def section_of(page):
    # The pages before the first section; named in the report's own language so
    # that one `section` field does not mix two languages.
    nm = 'Титул'
    for start, s in SECTIONS:
        if page >= start:
            nm = s
        else:
            break
    return nm

def parse():
    rows = []
    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            try:
                words = page.extract_words(extra_attrs=['non_stroking_color', 'size'])
            except Exception:
                continue
            for w in words:
                w['color'] = colname(w.get('non_stroking_color'))
            rs_words = [w for w in words if RS.match(w['text'])]
            if not rs_words:
                continue
            # table row height = the median vertical step between neighbouring rsIDs
            for rw in rs_words:
                top, bot = rw['top'], rw['bottom']
                band = [w for w in words
                        if w['top'] > top - 22 and w['bottom'] < bot + 22 and w is not rw]
                right = sorted([w for w in band if w['x0'] > rw['x1'] - 2], key=lambda w: (w['x0']))
                left = sorted([w for w in band if w['x1'] <= rw['x0'] + 2], key=lambda w: (w['x0'], w['top']))
                # ---- split the right-hand part into columns by x clusters
                gtoks = [w for w in right if GTOK.match(w['text'])]
                variants, gt = [], None
                if gtoks:
                    xs = sorted({round(w['x0']) for w in gtoks})
                    # x clusters with a gap > 25 pt
                    clusters, cur = [], [xs[0]]
                    for x in xs[1:]:
                        if x - cur[-1] <= 25:
                            cur.append(x)
                        else:
                            clusters.append(cur)
                            cur = [x]
                    clusters.append(cur)
                    # the first cluster holds the VARIANTS (usually 3 values in a column)
                    c0 = set(clusters[0])
                    variants = [(w['text'], w['color']) for w in gtoks if round(w['x0']) in c0]
                    rest = [w for w in gtoks if round(w['x0']) not in c0]
                    if rest:
                        gt = min(rest, key=lambda w: w['x0'])
                    elif len(variants) == 1:
                        gt, variants = gtoks[0], []
                    else:
                        # YOUR GENOTYPE is the one on the same line as the rsID
                        same = [w for w in gtoks if abs(w['top'] - top) < 6]
                        gt = same[-1] if same else None
                        variants = [(w['text'], w['color']) for w in gtoks if w is not gt]
                # more reliable: the genotype is the last COLOURED Latin word on the rsID line
                # (covers delC/delC, TAGTAAG/T, CCT and anything else that does not fit GTOK)
                lat = [w for w in right
                       if abs(w['top'] - top) < 6 and w['color'] in ('green', 'orange')
                       and re.fullmatch(r'[A-Za-z0-9/\-\*]{1,20}', w['text'])]
                if lat:
                    gt = max(lat, key=lambda w: w['x0'])
                    variants = [(w['text'], w['color']) for w in gtoks if w is not gt]
                concl_words = [w for w in right
                               if (gt is None or w['x0'] > gt['x1']) and not GTOK.match(w['text'])
                               and abs(w['top'] - top) < 18]
                conclusion = ' '.join(w['text'] for w in sorted(concl_words, key=lambda w: w['x0']))
                ccol = collections.Counter(w['color'] for w in concl_words if w['color'] != 'black')
                # ---- left-hand part: gene and trait (only on the same line as the rsID)
                same_line = [w for w in left if abs(w['top'] - top) < 6]
                lt = ' '.join(w['text'] for w in same_line)
                gene = ''
                m = re.findall(r'\b([A-Z][A-Z0-9]{1,9}(?:-[A-Z0-9]{1,6})?)\b', lt)
                if m:
                    gene = m[-1]
                trait = re.sub(r'\s+', ' ', lt.replace(gene, '')).strip(' -–—') if gene else lt.strip()
                rows.append(dict(
                    page=pno, section=section_of(pno), trait=trait, gene=gene, rsid=rw['text'],
                    variants=[v[0] for v in variants], variant_colors=[v[1] for v in variants],
                    genotype=(gt['text'] if gt is not None else ''),
                    genotype_color=(gt['color'] if gt is not None else ''),
                    conclusion=conclusion,
                    conclusion_color=(ccol.most_common(1)[0][0] if ccol else 'black'),
                ))
    return rows

if __name__ == '__main__':
    rows = parse()
    (OUT / 'evogen_pdf_rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                              encoding='utf-8')
    print('rows:', len(rows), '| unique rsIDs:', len({r['rsid'] for r in rows}))
    print('genotype colour:', collections.Counter(r['genotype_color'] for r in rows))
    print('conclusion colour:', collections.Counter(r['conclusion_color'] for r in rows))
    print('without a genotype:', sum(1 for r in rows if not r['genotype']))
