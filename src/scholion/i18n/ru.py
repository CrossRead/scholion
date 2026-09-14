"""Russian messages.

The only file in the shipped package where Russian is the point rather than an
oversight: it is switched on by the reader, not left behind by the author.

Keys must match `en.py` exactly — `tests/test_i18n.py` compares both the key
sets and the placeholders inside each entry. A translation that quietly drops
`{n}` produces a sentence with a hole in it, and in a report about someone's
health a hole reads as a number that was never measured.
"""
from __future__ import annotations

MESSAGES = {

    # ── overview ─────────────────────────────────────────────────────────
    "overview.title": "**Обзор.**",
    "overview.counts": "показателей: {total}; актуальных отклонений: {abnormal}",
    "overview.stale_note": " (плюс {n} давних, ≥12 мес — не текущий статус)",
    "overview.high": "**Повышено ({n}):**",
    "overview.low": "**Понижено ({n}):**",
    "overview.suggestions": "**Что сдать:** позиций {n}",
    "overview.suggestions_priority": ", из них приоритетных {n}",
    "overview.genome": "**Геном:** {state}",
    "overview.genome_gaps": "; пробелы: {genes}",
    "overview.medications": "**Назначений в схеме:** {n}",
    "overview.lifestyle_watch": "**Образ жизни — внимание:** {items}",

    # ── общий словарь ────────────────────────────────────────────────────
    "genome.connected": "подключён",
    "genome.not_connected": "не подключён",
    "common.none": "нет",
    "common.no_data": "данных нет",

    # ── раскладка данных и внешнее хранилище ─────────────────────────────
    "layout.header": "Где лежат данные:",
    "layout.missing": "  ✗ {slot}: источник не подключён, ожидался {path}",
    "layout.external": "  ↗ {slot}: {path} (внешнее хранилище)",

    # ── первый запуск ────────────────────────────────────────────────────
    "init.empty_profile": "⚠ профиль пуст: {path}",
    "init.empty_hint_files": "  разложить файлы:  scholion init",
    "init.empty_hint_demo": "  посмотреть демо:  scholion init --demo",

    # ── общие суффиксы строки показателя ─────────────────────────────────
    "common.trend": "тренд {arrow}{pct}",
    "common.stale": "давнее",
    "near.upper": "верхней",
    "near.lower": "нижней",
    "near.at_edge": "у границы: {margin} % до {side} границы {bound}",
    "near.corridor": "{pct} % ширины коридора",
    "decision.sex_unknown_most_cautious": "пол не указан, поэтому для этого порога взята более чувствительная из двух опубликованных границ — порог действия ошибается в сторону вопроса, в отличие от референсного интервала",
    "decision.crossed": "порог пройден: {label} ({sign} {value})",
    "decision.not_reached": "порог действия {value} ({label}) — не достигнут",

    # ── коридоры нормы рядом со значением ────────────────────────────────
    "ref.sex_unknown": "⚠ этот интервал зависит от пола, а в профиле пол не задан — коридор может быть не тот (`scholion profile --sex …`)",
    "ref.age_other_no_range": "(нет коридора: записанный интервал относится к другой возрастной полосе — применим диапазон, напечатанный на вашем бланке)",
    "ref.age_unknown_no_range": "(нет коридора: записанный интервал относится к одной возрастной полосе, а возраст в профиле не задан — `scholion profile --birth-year …` или диапазон с вашего бланка)",
    "ref.origin_profile": "(диапазон, записанный у маркёра, — на бланке этого забора не напечатан)",
    "labs.corridors_differ": "референсный интервал менялся между заборами ({spans}): значения сравнимы, флаги — нет",
    "ref.sex_unreviewed_no_range": "(нет коридора: записанный интервал не проверен, к кому он относится — применим диапазон, напечатанный на вашем бланке)",
    "ref.sex_not_applicable": "(тест существует только для мужского пола — значение показано; интервал не применим)",
    "ref.age_unbanded_no_range": "(нет коридора: лаборатории делят этот интервал по возрасту, а полоса записанного неизвестна — применим диапазон, напечатанный на вашем бланке)",
    "ref.sex_other_no_range": "· интервал не показан: коридор в справочнике снят с бланков человека другого пола, а одолженный через эту границу коридор даёт вердикт — и неверный",
    "ref.sex_unknown_no_range": "· интервал не показан: у этого показателя он зависит от пола, а пол в профиле не задан — коридор здесь был бы догадкой",
    "profile.recorded": "записано: {fields}",
    "markers.none_local": "локальных записей показателей пока нет",
    "markers.local_header": "Локально добавленные записи показателей — {n}. Запись `proposed` читается и показывается, но утверждений о норме не делает; `confirmed` означает, что за неё поручился человек.",
    "markers.local_footer": "файл: {path} — одна строка JSON на запись, проверяется глазами и уезжает наверх",
    "markers.entry_status": "{key}: {status}",
    "markers.need_marker_and_unit": "нужны и ключ показателя, и единица так, как она напечатана",
    "markers.need_factor_or_reason": "предложите либо коэффициент пересчёта, либо причину, по которой эта форма не пересчитывается",
    "markers.need_pattern": "нужен шаблон",
    "markers.need_example": "пример строки обязателен: шаблон без строки, которая его породила, нельзя ни проверить, ни закрепить регрессионным тестом",
    "markers.bad_rule_kind": "{kind} — не вид правила; используйте `alien` (строка чужая) или `label` (строка ЯВЛЯЕТСЯ помеченной строкой)",
    "markers.bad_pattern": "это не корректное регулярное выражение: {why}",
    "markers.unit_proposed_not_applied": "Для этой единицы есть предложенный пересчёт, и он НЕ применён: неподтверждённый коэффициент менял бы само число, а не только коридор. Подтвердите командой `scholion marker --confirm '{key}'` и повторите импорт.",
    "markers.need_key": "нужен канонический ключ (латиница, нижний регистр, подчёркивания)",
    "markers.need_names": "нужно хотя бы одно печатное название — именно оно опознаёт строку",
    "markers.already_shipped": "{key} уже есть в поставляемом словаре; локальная запись никогда не перекрывает проверенную",
    "markers.no_such_proposal": "локальной записи {key} нет",
    "markers.proposed_no_flag": "прочитано по локально предложенному правилу, ещё не подтверждено — значение сохранено, утверждений о норме не делается (`scholion marker --confirm {key}`)",
    "ref.range": "норма {low}–{high}",
    "ref.max": "норма <{high}",
    "ref.min": "норма >{low}",

    # ── сверка препарата с геном ─────────────────────────────────────────
    "drug.reference": "Справка: {url}",
    "drug.headline": "**{drug}** → ген **{gene}** ({drug_class}) — уровень: **{level}**",
    "drug.why_gene": "Почему ген важен: {text}",
    "drug.cpic_header": "CPIC, дословно — {phenotype}, сила рекомендации: {classification} (текст на языке источника):",
    "drug.co_phenotype": "Также {gene}: {phenotype} — {label}",
    "drug.driven_by": "Осторожность выше определяется геном {gene} (более тяжёлым из генов для этого препарата).",
    "drug.phenotype": "Фенотип пациента: **{phenotype}** — {label}",
    "drug.discuss": "**Что обсудить с врачом:** {text}",
    "drug.markers_header": "Маркеры пациента по гену:",
    "drug.marker_computed": "копий варианта: {copies}, функция: {function}",

    # ── один локус в геноме ──────────────────────────────────────────────
    "gene.unresolved_no_annotation": "Ген {gene} не удалось привести к координатам: локальной аннотации Ensembl на этой машине не нашлось, живой справочник не ответил. Это пробел поиска, а не утверждение о геноме. Искали в папках:",
    "gene.unresolved_not_in_annotation": "Гена {gene} нет в прочитанной аннотации, а живой справочник не ответил. Либо символ записан там иначе (синоним или прежнее имя), либо файл его не покрывает. Прочитано:",
    "gene.unresolved": "Ген {gene} не удалось привести к координатам: локальной аннотации Ensembl на этой машине не нашлось, живой справочник не ответил. Это пробел поиска, а не утверждение о геноме.",
    "gene.not_computed": "не посчитано",
    "gene.kind.synonymous": "синонимичная",
    "gene.kind.missense": "миссенс",
    "gene.kind.nonsense": "нонсенс (появился стоп-кодон)",
    "gene.kind.start_lost": "потерян стартовый кодон",
    "gene.kind.stop_lost": "потерян стоп-кодон",
    "gene.kind.not_coding": "вне кодирующей последовательности",
    "gene.kind.not_substitution": "вставка или делеция — последствие здесь не считается",
    "gene.kind.reference_mismatch": "референс расходится с файлом — не посчитано",
    "gene.kind.error": "посчитать не удалось",
    "gene.no_cds": "аннотация не знает кодирующих экзонов для {gene} — отделить кодирующие варианты от остального интервала нечем",
    "gene.no_reference": "референсной последовательности на этой машине нет, поэтому влияние вариантов на белок не посчитано",
    "gene.reference_contig": "в референсе нет контига {chrom}",
    "gene.coverage_no_bam": "выравнивания (BAM) на этой машине нет, поэтому «такого варианта нет» нечем подкрепить: неизвестно, какая часть участка прочитана",
    "gene.coverage_contig": "в выравнивании нет контига {chrom}",
    "gene.blind_cnv": "короткие чтения не вызывают крупных делеций и дупликаций целых экзонов — для части генов это заметная доля патогенных аллелей",
    "gene.blind_noncoding": "глубоко интронные и регуляторные варианты лежат внутри интервала, но здесь не интерпретируются",
    "gene.header": "**{gene}** — {chrom}:{start}–{end} ({strand}), {assembly}, транскрипт {transcript}",
    "gene.coords_from": "координаты: {source}",
    "gene.counts": "вариантов в гене: {total} · в кодирующей последовательности: {coding} · меняющих белок: {consequential}",
    "gene.whole": "ген целиком",
    "gene.cds": "кодирующая последовательность",
    "gene.coverage_line": "{what}: в среднем {mean}×, минимум {min}×, ≥10× на {pct10}% оснований, ≥20× на {pct20}%",
    "gene.coverage_not_computed": "для этого ответа оно не считалось, и причина здесь не "
                                  "названа — само по себе это и есть то, о чём стоит сообщить",
    "gene.coverage_missing": "покрытие не измерено — {why}",
    "gene.no_flagged": "отмеченных находок ClinVar внутри интервала нет. Это «ничего не отмечено», а не «ничего нет»: в таблице лежат находки, которые оставил шаг ClinVar.",
    "gene.flagged": "отмеченные находки ClinVar внутри интервала:",
    "gene.gaps": "**Не отвечено:**",
    "gene.blind": "**Чего это не видит:**",
    "gene.coding_none": "вариантов кодирующей последовательности нет.",
    "genome.unknown_gene": "Ген {gene} не найден в справочнике координат.",
    "genome.no_database": "полная геномная база ещё не подключена.",
    "genome.loci": "**{gene}** — локусы:",
    "genome.called": "вызван из VCF",
    "genome.assumed_ref": "референс (сайт не вариантный)",
    "genome.depth": "покрытие {value}",
    "genome.gene_at": 'ген **{gene}** ({assembly}{chrom}:{pos})',
    "genome.genotype": "генотип **{genotype}**",
    "genome.significance": "Клиническая значимость (ClinVar/Ensembl): {values}",
    "genome.consequence": "Последствие: {text}",
    "genome.resolved_by": "координата получена: {source}",
    "clinvar.gene_unresolved": "Координаты гена {gene} получить не удалось, поэтому "
                               "сопоставить с ним находки нельзя. Это пробел в справочнике "
                               "генов, а не утверждение о геноме: закрывается локальным "
                               "Ensembl GFF3 (SCHOLION_GENE_GFF3) или живым запросом к Ensembl.",
    "drug.not_checked_offline": "«{drug}» нет в собственной базе сборки, а международное "
                                "название посмотреть не удалось: сеть выключена "
                                "(SCHOLION_OFFLINE). Про этот препарат не установлено ничего "
                                "— ни в ту, ни в другую сторону.",
    "drug.no_pair_in_snapshot": "Препарат распознан, и пары «ген — препарат» для него нет в "
                                "копии руководств CPIC этой сборки (обновлена {date}). Это "
                                "утверждение о копии: либо руководства для этого препарата не "
                                "существует, либо оно есть и в сборку не попало — дата "
                                "показывает, что из этого стоит проверить.",
    "medications.in_pgx": "[фармакогенетика: {gene}]",
    "medications.pgx_unavailable": "[фармакогенетика: не проверено — база не прочиталась "
                                   "({reason})]",
    "medications.not_current": "[не текущее: {status}]",
    "medications.pgx_legend": "_Помеченные позиции — те, о которых эта сборка может сказать "
                              "что-то фармакогенетически. Остальные вне модели: не «не "
                              "проверены», а вне того, о чём генотип вообще высказывается._",
    "overview.build_ageing": "Эта сборка — {version}, выпущена {released}, то есть {ago} назад. "
                            "Возможно, вышла новее, и в ней починено то, на что вы смотрите: "
                            "`pip install -U scholion`.",
    "version.title": 'Scholion {version}',
    "version.released": 'выпущена {released} — {ago} назад',
    "version.last_used": 'данные последний раз работали с версией {version}',
    "version.not_recorded": 'версия, с которой данные работали последний раз, не записана — `scholion version --seen` запишет эту; `scholion version --since <ваша прежняя версия>` перечислит, что просят выпуски после неё',
    "version.since_head": 'После {since} действий просят {entries} журнала:',
    "version.nothing_since": 'После {since} ни один выпуск не просит ничего пересчитывать.',
    "version.run": 'выполнить {commands} — {condition}',
    "version.by_hand": 'вручную — {condition}',
    "version.seen_hint": 'Когда прочитаете: `scholion version --seen`.',
    "version.how_to_update": 'Проверить, есть ли новая версия: `scholion version --check`. Обновить пакет pip: `pip install --upgrade scholion`; остальные поставки описаны в `scholion doc readme`, раздел «Updating».',
    "version.seen_done": 'записано: данные теперь работают с версией {version}',
    "version.seen_no_profile": 'нет профиля, рядом с которым записать версию — `scholion init` его создаст',
    "version.check_offline": 'Задан SCHOLION_OFFLINE=1, поэтому реестр не спрашивали. Снимите переменную, чтобы проверить.',
    "version.check_unreachable": 'Реестр не ответил; эта сборка — {installed}.',
    "version.check_newer": 'Опубликована более новая версия: {latest} (эта сборка — {installed}). Обновление: `pip install --upgrade scholion`, затем `scholion version`.',
    "version.check_current": 'Эта сборка — текущая опубликованная версия: {installed}.',
    "version.written_before_head": 'Файлы, записанные более ранней сборкой, которые более поздний выпуск просит пересобрать:',
    "version.written_before_row": '{file} — записан версией {engine}; просят выпуски {releases}: {commands}',
    "version.unstamped": 'Записаны до того, как файлы стали нести версию сборки, поэтому неизвестно, какой выпуск они опережают: {files}. `scholion version --since <версия, с которой обновились>` перечислит, что пересобрать.',
    "web.update.note": 'Scholion обновлён с {from} до {to}.',
    "web.update.pending": 'С тех пор действий просят {entries} журнала.',
    "web.update.nothing": 'С тех пор ни один выпуск не просит ничего пересчитывать.',
    "web.update.show": 'Что сделать',
    "web.update.seen": 'Понятно',
    "web.update.check": 'Проверить новую версию',
    "pgx.snapshot_unreadable": "не прочиталось ({reason})",
    "clinvar.truncated_for_gene": "Прочитано {read} находок из {of}, поэтому «в этом гене "
                                  "ничего» сказать нельзя: находка может быть за срезом.",
    "web.genome.nav_screen": "Скрининг по классу",
    "tool.sch_screen.description": "Скрининг по классу заболеваний — для человека, у которого нет назначения на руках: какие гены сборка держит по классу, какие из них прочитаны в этом профиле и по каким классам списка нет вовсе. Без класса перечисляет классы. Никогда не называет класс чистым, если часть его не прочитана.",
    "tool.sch_screen.param.disease_class": "класс заболеваний, на любом из двух языков (например «онкология» / «oncology»). Без него перечисляются классы, по которым сборка может ответить.",
    "tool.sch_system.description": "Одна система организма с радара карточкой: лаборатория сейчас и её движение, генетическая половина системы и сколько из неё прочитано, назначения, действующие на систему, цель, заданная врачом, что сдать и вопросы к врачу — следующий шаг в трёх корзинах, ни одна не пуста молча. Без ключа перечисляет системы. Никогда не называет систему чистой, пока часть её генетической половины не прочитана.",
    "tool.sch_system.param.key": "ключ системы: thyroid, lipids, cardio, glucose, inflammation, adrenals, gonads, growth, pancreas, liver, micronutrients, renal, fitness. Без него — список.",
    "tool.sch_system.param.register": "«patient» (по умолчанию) или «clinician»: одни факты в двух плотностях — регистр врача добавляет rsID, генотип, глубину, классификацию, отправителя и счётчики гейта. Вердикт один в обоих.",
    "tool.sch_sources.description": "ТОЛЬКО ЧТЕНИЕ: реестр внешних источников — зеркалируемые базы, загрузки конвейера и живые сервисы — и когда каждый последний раз был импортирован в эту сборку. Обновление — команда владельца, а не инструмент.",
    "tool.sch_array.description": "ТОЛЬКО ЧТЕНИЕ: отчёт по чиповому генотипированию — что файл с чипа может и не может ответить рядом с полным геномом и какие позиции каталога он на самом деле несёт.",
    "tool.sch_flag_rate.description": "ТОЛЬКО ЧТЕНИЕ: как часто флаги самой лаборатории и коридоры словаря расходятся на этом профиле — доля и маркёры, на которых они расходятся.",
    "tool.sch_lab_draw.description": "ПИШЕТ сказанное человеком: почему в один день два измерения одного маркёра и что стояло между ними — инфузия, доза, нагрузочная проба. Записывает причину дословно; значения не трогает.",
    "tool.sch_lab_draw.param.day": "день с двумя заборами, ГГГГ-ММ-ДД",
    "tool.sch_lab_draw.param.reason": "причина второго забора словами человека",
    "tool.sch_lab_draw.param.between": "что стояло между двумя заборами — инфузия, доза, проба — как описал человек",
    "tool.sch_marker_propose.description": "ПИШЕТ предложение, а не факт: лабораторный маркёр, которого словарь не знает, под ключом и с названиями, под которыми он встречается на бланках человека. Хранится как предложенный моделью и ни для чего не используется, пока человек не подтвердит его через `scholion marker --confirm`.",
    "tool.sch_marker_propose.param.key": "ключ маркёра, строчными с подчёркиваниями (например «lp_a»)",
    "tool.sch_marker_propose.param.names": "названия маркёра на бланках, через «;»",
    "tool.sch_marker_propose.param.unit": "единица, в которой бланки печатают значение",
    "tool.sch_marker_propose.param.names_en": "английские названия того же маркёра, через «;», если есть",
    "system.unknown_register": "нет такого регистра: «{register}» — регистры: {registers}",
    "ingest_labs.folder_not_named": "папка не названа — по умолчанию из текущего каталога ничего не читается; назовите папку с лабораторными бланками",
    "screen.title": "Скрининг по классу заболеваний",
    "screen.classes_header": "классы, по которым эта сборка может ответить",
    "screen.class_row": "{label} — генов: {count}, источник: {source}",
    "screen.named_header": "классы, названные и этой сборкой не удерживаемые",
    "screen.no_named": "ни одного класса сверх удерживаемых сборке не назвали — курируемый список пуст, и это утверждение о сборке",
    "screen.dropped": "списков классов без источника, не использовано: {n}",
    "screen.finding": "в этом списке найдено то, о чём сообщают — гены: {genes}, находок: {n}",
    "screen.and_unread": "и список прочитан не целиком — непрочитанных строк: {unread}, из списка в {total}",
    "screen.clear_measured": "ничего, о чём сообщают, не найдено, и все гены списка прочитаны — генов: {total}. Это измеренный результат, а не заключение о здоровье: он говорит, что этот метод увидел в этих генах",
    "screen.clear_partial": "ничего, о чём сообщают, не найдено, И список прочитан не целиком — непрочитанных строк: {unread}, из списка в {total} ({genes}). По гену, который никто не прочитал, «не найдено» — утверждение о файле, а не о человеке",
    "screen.and_carriers": "строк, где найдена одна копия рецессивного аллеля, — это носительство, а не находка о собственном риске человека: {n} — см. вопросы",
    "screen.not_determined": "по этому списку сборка ответить не может — {why}",
    "screen.why.not_ready": "геном на этом профиле не читается — см. статус генома",
    "screen.why.unavailable": "геном не удалось открыть — см. статус генома",
    "screen.why.no_panel": "генетического списка для этой системы в сборке нет — его никто не написал, и это утверждение о сборке, а не о человеке",
    "screen.why.no_genetic_half": "у этой системы нет генетической половины по замыслу: она строится из показателей носимых устройств",
    "screen.why.class_not_held": "списка генов по нему в сборке нет — ни опубликованного, ни курируемого; что есть, сказано в списке классов выше",
    "screen.why.scan_not_run": "экран на этом профиле не запускался — `scholion acmg-scan`",
    "screen.gene_row": "{gene} — {phenotype}, наследование {inheritance}",
    "screen.gene_unread": "в этом файле прочитан недостаточно",
    "screen.gene_findings": "находок: {n}",
    "screen.scanned_on": "экран запускался {date}",
    "decision.rule_fires": "у сборки есть правило по этой паре, и прочтение выбирает строку, "
                           "отличную от нейтральной ({genes}) — какую именно, сказано ниже",
    "decision.rule_silent": "у сборки есть правило по этой паре ({genes}), и прочтение выбирает "
                            "нейтральную строку: здесь ничто выбора не меняет — это утверждение "
                            "о правиле, а не разрешение",
    "decision.no_rule": "сборка не дошла ни до одного правила, которое могло бы повлиять на "
                        "выбор — {why}",
    "decision.why.not_asked": "источник руководств не спрашивали; причина названа ниже",
    "decision.why.no_pair": "пары «ген — препарат» для него в этой сборке нет",
    "decision.kind.mechanism": "участвует в обмене этого вещества, правила дозирования не следует",
    "decision.kind.asked_about": "про него здесь спрашивают, и из него не следует ничего",
    "decision.kind.unassigned": "назван в списке; ни вид связи, ни что из него следует — ещё не написаны",
    "decision.not_written_yet": "назван в списке, и что из него следует — ещё не написано; "
                                "сама сборка это не дописывает",
    "decision.kind.no_variant": "назван в списке контекста, и вариантов в нём этой сборке "
                                "сообщить нечего",
    "decision.variant.variant_called": "и это не про этот файл: позиций с вызванным вариантом "
                                       "здесь {n}",
    "decision.variant.no_variant_called": "прочитано и совпало с референсом: {n}, из удерживаемых позиций {total}, глубина {depth} — это измеренное отсутствие находки, а не отсутствие измерения",
    "decision.variant.and_unread": "позиций без строки в этом файле, и ответа по ним нет: {n}",
    "decision.variant.not_read": "позиции, которые сборка держит по этому гену ({n}), в этом "
                                 "файле не прочитаны — это отсутствие измерения, а не находки",
    "decision.variant.no_positions": "позиций по этому гену эта сборка не держит, и сказать о "
                                     "вариантах в нём ей нечего — это утверждение о сборке, "
                                     "а не о человеке",
    "decision.source": "источник: {source}",
    "decision.no_context_list": "курируемого списка генов по этому назначению в сборке нет — это "
                                "утверждение о сборке, а не о геноме, и оно печатается потому, "
                                "что тишину на этом месте договаривает тот, кто отвечает",
    "decision.entries_without_source": "записей в списке контекста без источника, они не напечатаны: {n}",
    "decision.via_system": "{source} — через систему «{system}», на которую действует класс этого назначения",
    "decision.through_systems": "генетическая половина систем, на которые действует класс этого назначения: {systems}",
    "decision.system_reached": "достигнуто через систему «{system}»: генов в её генетической половине — {n}",
    "decision.system_not_composed": "достигнуто через систему «{system}», генетическая половина которой в этой сборке не составлена — из неё ничего не наследуется, и это утверждение о сборке",
    "decision.excluded_by_clinician": "гены, вычеркнутые врачом из унаследованного списка, с источником: {genes}",
    "genome.locus_no_basis": "по этой позиции у сборки нет прочтения: ни правила из "
                             "руководства, ни курируемого примечания. Генотип назван и не "
                             "истолкован",
    "genome.locus_pair_only": "{gene} — признанный фармакоген, и таблицы руководства по нему "
                              "в этой сборке нет: генотип назван и в решение не превращается",
    "gene.verdict": "что эта сборка решила про этот ген: {text}",
    "gene.verdict_source": "цитата из {source} — заключение без указания источника не печатается",
    "gene.coverage.low": "покрытие: прочитано {pct}% гена на 20× при типичных для этого "
                         "файла {median}% — уверенность в ответе по нему НИЗКАЯ, и «ничего "
                         "не найдено» здесь значит мало",
    "gene.coverage.fine": "покрытие: {pct}% на 20×, как и остальной файл (это не то же самое, "
                          "что «достаточно» — достаточность зависит от вопроса)",
    "gene.coverage.not_in_table": "покрытие: для этого гена не измерено — его нет среди генов "
                                  "таблицы ({n})",
    "gene.layers_header": "Что эта сборка знает про {gene}",
    "gene.layer.catalogue": "курируемые локусы: {count}",
    "gene.layer.catalogue_none": "курируемые локусы: нет — у этого гена нет каталожных позиций",
    "gene.layer.clinvar": "ClinVar: {count} в {chrom}:{start}–{end} ({source})",
    "gene.layer.clinvar_unresolved": "ClinVar: спросить нельзя — координаты гена не получены",
    "gene.layer.acmg_in": "панель ACMG SF: входит, {findings}",
    "gene.layer.acmg_out": "панель ACMG SF: не входит",
    "gene.layer.acmg_unread": "панель ACMG SF: входит, и панель сообщает, что ген не прочитан",
    "gene.layer.acmg_not_run": "панель ACMG SF: входит — и экран не запускался, так что "
                               "считать нечего; `scholion acmg-scan` даёт таблицу",
    "gene.layer.acmg_unavailable": "панель ACMG SF: спросить не удалось ({status})",
    "gene.layer.clinvar_not_run": "ClinVar: координаты гена известны, а скан не запускался — "
                                  "пока он не пройден, считать находки нечем",
    "gene.layer.clinvar_unavailable": "ClinVar: спросить не удалось ({status})",
    "gene.layer.coverage_no": "покрытие: не измерено — «ничего не найдено» значит «ничего в "
                              "прочитанной части»",
    "gene.coverage.unavailable": "покрытие: таблица не прочиталась ({reason}) — это не «не "
                                 "измерено»: измерение есть, и оно не открылось",
    "clinvar.gene_of_scanned": " (из {total} во всей таблице)",
    "count.findings.one": "{n} находка",
    "count.findings.few": "{n} находки",
    "count.findings.many": "{n} находок",
    "count.days.one": "{n} день",
    "count.days.few": "{n} дня",
    "count.days.many": "{n} дней",
    "genome.no_curated_reading": "Этой позиции нет в курируемом наборе проекта: генотип "
                                 "прочитан, клинического заключения по нему проект не "
                                 "даёт. Всё, что сказано о его значении, пришло откуда-то "
                                 "ещё — и должно это называть.",

    # ── блок ClinVar внутри отчёта по препарату ──────────────────────────
    "clinvar_block.header": "ClinVar по этому препарату:",
    "clinvar_block.via_gene": "ген {gene}",
    "clinvar_block.via_name": "по названию препарата",
    "clinvar_block.genotype": "генотип {genotype}",

    # ── второе мнение по новому назначению ───────────────────────────────
    "source.local": "база проекта",
    "source.none": "не распознан",
    "common.in_range": "в норме",
    "unresolved.pgx": "фенотип — не прочитано: {names}; полный VCF это закрывает",
    "unresolved.drug_not_classified": "класс препарата не определён, поэтому взаимодействия не проверялись",
    "unresolved.no_baseline": "текущих назначений нет — сравнивать не с чем",
    "unresolved.baseline_partial": "часть текущего списка не опознана и в сравнении не "
                                   "участвовала: {names}",
    "prescription.unresolved_h": "⚪ Не определено — и что это закроет:",
    "prescription.unresolved_gene": "{detail} ({gene})",
    "drug.phenotype_not_determined": "Фенотип {gene} по вашим данным не определён — дальше общее правило, а не утверждение о вас.",
    "drug.no_guidance_for_phenotype": "В каталоге нет рекомендации для фенотипа {phenotype} гена {gene} по этому препарату. Это пробел в справочных данных, а не вывод о вас — вопрос к врачу.",
    "basis.read": "Прочитано {read} из {total} маркеров модели.",
    "basis.missing": "Не прочитано: {names}.",
    "basis.obtainable": "Эти позиции есть в каталоге локусов: полный геном (VCF) из собственных ридов или прицельный фармакогенетический тест, который их покрывает, закроет этот пробел и превратит общее правило в утверждение об этом человеке.",
    "basis.not_in_catalogue": "В каталоге локусов их тоже нет — нужен лабораторный анализ.",
    "basis.not_called": "VCF подключён, но у {names} в нём нет строки — это либо референс, либо отсутствие покрытия, и по файлу их не различить. Собрать другой VCF ничего не изменит: эти позиции нужно прогенотипировать из выравненных чтений, и до тех пор они считаются непрочитанными.",
    "basis.not_modelled": "В каталоге проекта по этому гену есть {names}, и модель интерпретации это пока не использует — то есть даже полный VCF эту часть не закроет.",
    "phenotype.from_reported_diplotype": "по диплотипу {diplotype}, как его назвал {source} — сообщён, а не вызван по вашим ридам, и он старше оценки по тег-SNP по той же причине: назвавший его разрешил то, чего тег-SNP не разрешают",
    "phenotype.source_unnamed": "источник, не назвавший себя",
    "phenotype.from_called_diplotype": "по вызванному диплотипу {diplotype} (PyPGx/PharmCAT — с числом копий и фазой), что важнее оценки по tag-SNP",
    "phenotype.assumed": "{label} — ПРЕДПОЛАГАЕТСЯ, прочитаны не все маркеры",
    "prescription.title": "**Второе мнение: {drug}** — итог: **{overall}**",
    "prescription.class": "класс: {value}",
    "prescription.source": "источник: {value}",
    "prescription.genome_header": "Ваш геном:",
    "prescription.pgx_unchecked": "Фармакогенетика по CPIC НЕ проверялась — {why}. "
                                 "Это не то же самое, что «её у препарата нет».",
    "pgx_unchecked.offline": "сеть выключена (SCHOLION_OFFLINE)",
    "pgx_unchecked.unreachable": "база не ответила",
    "pgx_unchecked.not_identified": "препарат не опознан в RxNorm, спрашивать было нечем",
    "prescription.labs_no_rule": "Правила лабораторного контроля для этого класса ({classes}) "
                                 "в каталоге нет — это не то же самое, что «контроль не нужен».",
    "prescription.labs_class_unknown": "Класс препарата не определён, поэтому про лабораторный "
                                       "контроль сказать нечего.",
    "unresolved.pgx_source": "Фармакогенетика: CPIC не опрашивался — {why}.",
    "unresolved.labs_no_rule": "Лабораторный контроль: правила для класса {classes} в каталоге нет.",
    "prescription.no_pgx": "Значимой фармакогенетики по препарату нет (CPIC): генов, влияющих на дозу/эффект, не выявлено. Наша копия руководств от {date} — это и отличает «ничего не известно» от «сборка отстала».",
    "common.unknown_date": "без даты",
    "prescription.actionable": "важен",
    "prescription.gene_phenotype": "ваш фенотип **{phenotype}** — {label}",
    "prescription.tag_snps_only": "прочитанные здесь тег-SNP, сами по себе не дающие диплотип: {list}",
    "prescription.variants": "варианты: {list}",
    "prescription.labs_header": "Ваши анализы:",
    # ── red flags from the owner's own profile ───────────────────────────
    "prescription.safety_h": "Красный флаг из вашего профиля:",
    "prescription.safety_factor": "**Фактор:** {text}",
    "prescription.safety_why": "Почему это важно: {text}",
    "prescription.safety_pro": "Что говорит в пользу низкого риска: {text}",
    "prescription.safety_unknown": "Что неизвестно: {text}",
    "prescription.safety_action": "**Действие:** {text}",
    "prescription.safety_source": "Источник: {text}",

    "prescription.no_lab_control": "Специфического лабораторного контроля по классу не требуется.",
    "prescription.monitor": "Контролировать: {text}",
    "prescription.already_abnormal": "У вас уже отклонены: **{names}** — "
                                     "важно при этом препарате.",
    "prescription.threshold_crossed": "{name} {value} — пройден клинический порог действия "
                                      "{threshold} ({label}).",
    "prescription.source_ref": "источник: {source}",
    "prescription.near_edge": "В норме, но у границы коридора: **{names}** — "
                              "при этом препарате следить особенно.",
    "prescription.not_tested": "ещё не сдавали",
    "prescription.interactions_header": "Ваши назначения:",
    "prescription.interaction": "с **{meds}** — {effect} (механизм: {mechanism}).",
    "prescription.what_to_do": "Что делать: {text}",
    'prescription.excluded_from_check': 'В сверку не вошли: {names} — файл отмечает их как недействующие, и новый препарат с ними не сверяется. Если что-то из этого на самом деле принимается, это говорит статус в файле назначений.',
    'prescription.status_not_recorded': 'Учтены как действующие без записанного статуса: {names}. Статус у этих записей не записан; они участвуют в сверке, и это допущение, а не факт — `add-med --status` его записывает.',
    "prescription.no_interactions_partial": "Явных взаимодействий с опознанной частью текущего "
                                            "списка не найдено. НЕ сравнивалось, потому что класс "
                                            "не определён: {names}.",
    "prescription.no_interactions": "Явных взаимодействий с текущими назначениями не найдено.",
    "prescription.dose_header": "Дозовый и критический контекст:",
    "prescription.doses": "Дозы: нутрицевтическая {nutritional} · "
                          "фармакологическая {pharmacologic}.",
    "prescription.effect": "эффект: {text}",
    "prescription.by_dose": "по дозе: {text}",
    "prescription.not_measured": "{name}: не сдавали",
    "prescription.your_numbers": "ваши цифры: {items}",
    "prescription.forms": "Формы: {text}",
    "prescription.alternative": "альтернатива: **{name}**",
    "prescription.alt_melatonin": "мелатонин/сон",
    "prescription.alt_metabolic": "метаболика",
    "prescription.alt_caveat": "оговорка",

    # ── анализы ──────────────────────────────────────────────────────────
    "labs.header": "**Анализы:** {abnormal} из {total}",
    "labs.near_more": "ещё {n} у границы коридора",
    "labs.crossed": "клинических порогов действия пройдено: {n}",
    "labs.draw_context_saved": "записано для {day}: {context} — показателей, измеренных в тот день дважды: {n}",
    "labs.fasting_after_event": "⚠ пороги ниже предполагают пробу натощак; этот забор сделан после — {text} — поэтому пересечение здесь не означает названного состояния",
    "labs.condition_unknown": "⚠ это второй забор за день, а пороги ниже предполагают пробу натощак — пока не сказано, что было между замерами, считайте отмеченное пересечение неподтверждённым",
    "labs.same_day_repeat": "два замера {day}: {points} — это повтор, а не расхождение в данных",
    "labs.same_day_context": "между ними: {text}",
    "labs.same_day_ask": "почему в тот день сдавали дважды и что было между замерами — процедура, приём препарата, нагрузка? `scholion lab-draw --day <дата> --reason … --between …`",
    "labs.near_limit_is_flat": "«У границы» считается как плоские 10 % от предела для любого аналита. Это эвристика, а не reference change value: между заборами натрий меняется на доли процента, а CRP на десятки, поэтому зона для одних показателей слишком мягкая, для других слишком строгая.",
    "labs.below_own_scatter": "в пределах собственного разброса показателя: различимой его история показывала разницу лишь от {pct}%, посчитано по ней самой ({pairs} интервалов)",
    "labs.ref_from_reference_base": "интервал общий справочный, а не напечатанный на вашем бланке",
    "labs.genome_link": "геном: {text}",
    "labs.owner_note": "заметка владельца: {text}",
    "count.abnormal.one": "{n} отклонение",
    "count.readings.one": "{n} измерение",
    "count.readings.few": "{n} измерения",
    "count.readings.many": "{n} измерений",
    "count.entries.one": "{n} запись",
    "count.entries.few": "{n} записи",
    "count.entries.many": "{n} записей",
    "count.steps.one": "{n} шаг",
    "count.steps.few": "{n} шага",
    "count.steps.many": "{n} шагов",
    "count.positions.one": "{n} позиция",
    "count.positions.few": "{n} позиции",
    "count.positions.many": "{n} позиций",
    "count.chromosomes.one": "{n} хромосома",
    "count.chromosomes.few": "{n} хромосомы",
    "count.chromosomes.many": "{n} хромосом",
    "recompute.title": "Что пересчитать для этой сборки",
    "recompute.since": "Ваши данные последний раз использовались с {since}; эта сборка — {installed}.",
    "recompute.since_unknown": "Данные не записали, с какой версией использовались, поэтому планируется только то, чего не хватает самим данным; `scholion recompute --since 0.4.8` строит план от названной версии. Эта сборка — {installed}.",
    "recompute.nothing": "Пересчитывать нечего: ни один выпуск с тех пор этого не просит, а файлы генома, которые читает эта сборка, актуальны.",
    "recompute.state.ready": "будет выполнено",
    "recompute.state.needs_input": "пока не может выполниться",
    "recompute.state.not_applicable": "не относится",
    "recompute.state.already_current": "уже сделано",
    "recompute.state.not_run_here": "выполните сами",
    "recompute.state.by_hand": "сделать вам",
    "recompute.step.by_hand": "Вручную — {condition}",
    "recompute.from_releases": "просит {versions}",
    "recompute.from_data": "этого не хватает файлам генома",
    "recompute.why.no_file": "нет файла {file}, который надо пересобрать",
    "recompute.why.written_by": "{file} записан сборкой {engine}, в которой это уже учтено",
    "recompute.why.no_folder": "папка бланков не названа; её называет `scholion set-folder {domain} <путь>`",
    "recompute.why.not_runnable": "эта команда отсюда не запускается",
    "recompute.why.no_vcf": "геном не подключён",
    "recompute.why.sites_current": "позиции каталога сняты для этого каталога",
    "recompute.why.sites_missing": "{positions} каталога ни разу не снимались с выравнивания, поэтому каждая, которой нет в VCF, читается как непрочитанная",
    "recompute.why.sites_older_than_catalogue": "файл позиций сделан для более раннего каталога, чем нынешний ({positions}); добавленные с тех пор позиции читаются как непрочитанные",
    "recompute.why.no_bam": "выравнивания (BAM) на этой машине нет, и ни одна настройка его не называет: `scholion choose-genome --bam /путь/к/sample.bam` записывает путь рядом с профилем — на этот запуск и на все следующие; `SCHOLION_GENOME_BAM=/путь/к/sample.bam` называет его только на один запуск",
    "recompute.why.no_index": "у выравнивания нет индекса; его делает `samtools index`",
    "recompute.why.no_reference": "референсная FASTA с файлом .fai не найдена, и ни одна настройка её не называет: `scholion choose-genome --reference /путь/к/reference.fa` записывает путь рядом с профилем; `SCHOLION_GENOME_REFERENCE=/путь/к/reference.fa` называет её только на один запуск",
    "recompute.why.no_bcftools": "bcftools не установлен",
    "recompute.why.no_clinvar": "опубликованного VCF ClinVar нет в папке генома; `scholion acmg-scan` называет единственный файл, который нужно скачать",
    "recompute.why.alignment_unreadable": "выравнивание не читается как BAM",
    "recompute.why.alignment_build_unknown": "сборку выравнивания не удалось определить по заголовку",
    "recompute.why.no_positions_in_build": "в каталоге нет позиций в сборке выравнивания",
    "recompute.hint_run": "`scholion recompute --yes` выполнит готовые шаги ({steps}) по порядку и покажет ход каждого; файл, который шаг перепишет, сначала копируется в архив.",
    "recompute.hint_nothing_ready": "Ничего здесь не может выполниться само; в каждой строке сказано, чего не хватает.",
    "recompute.running_now": "Пересчёт идёт сейчас; `scholion recompute --status` показывает, насколько он продвинулся.",
    "recompute.busy": "Пересчёт уже идёт; `scholion recompute --status` показывает его, `--stop` останавливает.",
    "recompute.not_confirmed": "Ничего не запущено: пересчёт выполняется только после подтверждения.",
    "recompute.nothing_ready": "Ничего не запущено: нет шага, готового к выполнению.",
    "recompute.progress.step": "[{i}/{n}] {command}",
    "recompute.progress.items": "{done} из {total}",
    "recompute.progress.percent": "{pct}%",
    "recompute.progress.elapsed": "прошло {time}",
    "recompute.progress.left": "осталось около {time}",
    "recompute.job_step.waiting": "ждёт",
    "recompute.job_step.running": "идёт",
    "recompute.job_step.done": "готово",
    "recompute.job_step.failed": "ошибка",
    "recompute.job_step.stopped": "остановлено",
    "recompute.status.none": "Для этого профиля пересчёт не запускался.",
    "recompute.status.running": "Пересчёт идёт с {started}.",
    "recompute.status.finished": "Пересчёт закончен в {finished}.",
    "recompute.status.failed": "Пересчёт остановился в {finished} на шаге с ошибкой; следующие шаги не выполнялись.",
    "recompute.status.stopped": "Пересчёт остановлен в {finished}, как просили. Остановленный шаг ничего не отмечает как сделанное; повторный запуск начнёт его сначала.",
    "recompute.status.interrupted": "Пересчёт, начатый в {started}, прерван: его процесса больше нет. Оборванный шаг ничего не отмечает как сделанное, поэтому повторный запуск начнёт этот шаг сначала; копии файлов до запуска лежат в архиве.",
    "recompute.backup": "Копии переписанных файлов: {path}",
    "recompute.recorded": "Теперь данные записаны как используемые с {version}.",
    "recompute.not_recorded_since_unknown": "Версия не записана: данные не сообщали, с какой версией использовались, поэтому то, что просят прежние выпуски, не планировалось. `scholion recompute --since <версия>` это спланирует, а `scholion version --seen` запишет версию, когда вы проверите.",
    "recompute.remaining": "Не отмечено как сделанное: ещё открыты {by_hand} вручную и {needs_input}, которые не смогли выполниться.",
    "recompute.stop_requested": "Остановка запрошена: работа остановится после элемента, который читает сейчас.",
    "recompute.stop_not_running": "Пересчёт не идёт.",
    "coverage.progress": "ген {i} из {n}: {gene}",
    "coverage.progress_write": "записываю таблицу",
    "coverage.done": "✓ {genes} измерено по выравниванию ({seconds} с) → {path}",
    "coverage.without_clinvar": "генов без записи в ClinVar, а значит без координат и без строки: {n}. Карточка о каждом говорит, что таблица его не держит, — это правда и это не то же самое, что «прочитан плохо»",
    "coverage.stopped": "Остановлено после {measured} из {genes}; измеренное сохранено, следующий запуск продолжит с этого места.",
    "coverage.failed": "✗ измерение ничего не дало: {error}",
    "recompute.why.coverage_current": "таблица покрытия уже покрывает все гены, которые читают панели",
    "recompute.why.coverage_missing": "покрытие ваших генов никогда не измерялось, поэтому ни один ген панелей нельзя считать прочитанным",
    "recompute.why.coverage_older_than_panels": "таблица покрытия считалась по меньшему списку генов, чем читают панели сейчас",
    "recompute.why.no_samtools": "samtools не установлен",
    "sites.progress": "хромосома {i} из {n}: {chrom}",
    "sites.progress_merge": "объединение хромосом в один файл",
    "sites.done": "✓ {positions} сняты с выравнивания ({assembly}, {chromosomes}, {seconds} с) → {path}",
    "sites.failed": "✗ bcftools завершился с ошибкой на {step} (код {rc}): {error}",
    "sites.stopped": "Остановлено до замены файла; прежний файл остался как был.",
    "system.genetics.assumed_ref_hint": "{positions} не прочитаны, потому что позиции каталога не сняты с выравнивания; этот шаг планирует `scholion recompute`.",
    "web.recompute.open": "Что пересчитать",
    "web.recompute.h": "Пересчёт",
    "web.recompute.cli": "То же в терминале: scholion recompute --status",
    "web.recompute.start": "Запустить",
    "web.recompute.stop": "Остановить",
    "web.recompute.close": "Закрыть",
    "web.recompute.confirm": "Выполнить готовые шаги ({steps}) сейчас? Файл, который шаг перепишет, сначала копируется в архив. Повторное чтение бланков или выравнивания может занять минуты; ход работы останется на этой странице и переживёт перезагрузку.",
    "count.results.one": "{n} результат",
    "count.results.few": "{n} результата",
    "count.results.many": "{n} результатов",
    "count.rows.one": "{n} строка",
    "count.rows.few": "{n} строки",
    "count.rows.many": "{n} строк",
    "count.genes.one": "{n} ген",
    "count.genes.few": "{n} гена",
    "count.genes.many": "{n} генов",
    "count.bytes.one": "{n} байт",
    "count.bytes.few": "{n} байта",
    "count.bytes.many": "{n} байт",
    "count.abnormal.few": "{n} отклонения",
    "count.abnormal.many": "{n} отклонений",
    # родительный падеж: «из 21 показателя», «из 27 показателей»
    "count.markers_of.one": "{n} показателя",
    "count.markers_of.few": "{n} показателей",
    "count.markers_of.many": "{n} показателей",

    # ── назначения ───────────────────────────────────────────────────────
    "medications.empty": "Схема лечения пуста — назначений в профиле нет.",
    "medications.header": "**Схема лечения ({n}):**",

    # ── показатели (каталог профиля) ─────────────────────────────────────
    "markers.empty": "В профиле пока нет показателей.",
    "markers.header": "**Показателей в профиле: {n}**",
    "markers.note": "Пустой коридор — не ошибка: он берётся из вашего бланка, "
                    "и без него показатель выводится БЕЗ флага отклонения.",

    # ── радар здоровья ───────────────────────────────────────────────────
    "radar.overall": "**Общий индекс здоровья: {score}/100**",
    "radar.delta": "{delta} к прошлому измерению",
    "radar.domain_counts": "отклонений {abnormal} из {total}",
    "radar.domain_partial": "отклонений {abnormal} из {measured} измеренных — "
                            "в домене заявлено {total}",

    # ── второй взгляд перед визитом к врачу ──────────────────────────────
    "second_opinion.title": "**Второй взгляд перед визитом к врачу**",
    "second_opinion.abnormal": "**Отклонения ({n}):**",
    "second_opinion.no_abnormal": "**Отклонений нет.**",
    "second_opinion.stale": "давнее, не текущий статус",
    "second_opinion.pgx": "**Фармакогенетика — на будущее ({n}):**",
    "second_opinion.pgx_none": "**Фармакогенетика:** значимых пометок нет.",
    "second_opinion.tests": "**Что имеет смысл сдать ({n}):**",
    "second_opinion.tests_none": "**Дозаказов нет.**",
    "second_opinion.note": "Это список вопросов к врачу, а не назначение.",

    # ── личные показатели здоровья ───────────────────────────────────────
    "metrics.title": "**Личные показатели здоровья**",
    "metrics.age": "возраст {value}",
    "metrics.height": "рост {value} см",
    "metrics.bmi": "ИМТ {value} ({category})",
    "metrics.empty": "Пока не заполнено.",
    "metrics.empty_hint": "Внесите вес/сон/шаги во вкладке «Показатели».",

    # ── предложения по анализам ──────────────────────────────────────────
    "tests.none": "Дополнительных анализов по текущим правилам не предложено.",
    "tests.header": "**Предложения по дополнительным анализам** ({n}):",
    "tests.specialist": "к кому: {name}",
    "tests.why": "зачем: {text}",
    "tests.nothing_pending": "Актуальных дозаказов нет — заказанное сдано; "
                             "ждём только ещё не готовые результаты.",
    "tests.rule_error": "правило {id}: ошибка ({error})",
    "tests.routine_header": "**Плановый контроль — уже сдано, следим по интервалу:**",
    "tests.done": "{name} — измерено {date}, повтор ~через {months} мес.",

    # ── цель ─────────────────────────────────────────────────────────────
    "goal.not_set": "Цель ещё не задана. В profile/health_goals.json под "
                    "`_meta._example` лежит заполненный пример — перенесите его на "
                    "верхний уровень и перепишите под свою цель.",
    "goal.title_default": "Цель",
    "goal.as_of": "данные на {date}",
    "web.metrics.from_device": "{device}, {date}",
    "web.metrics.from_hand": "введено вручную, {date}",
    "web.metrics.also_hand": "вручную: {value} ({date})",
    "web.metrics.also_device": "{device}: {value} ({date})",
    "goal.no_now.unknown_metric": "в профиле нет такого ряда",
    "goal.no_now.several_devices": "это измеряет больше одного прибора — в цели "
                                   "надо назвать, чей ряд: wear:garmin:<метрика>",
    "goal.no_now.empty_series": "ряд есть, точек в нём пока нет",
    "goal.measured_by": "измерено прибором {device}",
    "goal.headline": "Одной фразой: {text}",
    "goal.targets_header": "Целевые показатели (сейчас → цель · лучшее):",
    "goal.best": "лучшее {value}",
    "goal.live_note": "Значения и ряды — ЖИВЫЕ из единой модели данных "
                      "(labs.json + wearable_trends.json).",
    "goal.progress_rule": "Прогресс = жир вниз при мышце на месте.",

    # ── находки ClinVar ──────────────────────────────────────────────────
    "clinvar.how_to_run": "Аннотация ClinVar — часть подготовки генома, она запускается из "
                          "исходного дерева проекта, а не из установленного пакета. Весь "
                          "путь описан в `scholion doc preparing-the-genome`.",
    "capabilities.title": "**Что умеет эта сборка** — Scholion {version}, команд: {n}",
    "capabilities.how_to_read": "Собрано из разборщика команд и карты входов, поэтому отстать от "
                                "них не может. Если выданная вам инструкция и этот список "
                                "расходятся — прав список: это сборка, которая перед вами. "
                                "Каждая команда принимает `--json`.",
    "capabilities.reads_h": "Только читают — команд: {n}. Безопасно вызывать, чтобы ответить на вопрос.",
    "capabilities.writes_h": "МЕНЯЮТ данные — команд: {n}. Не для ответа на вопрос. Двух родов, помечено на каждой строке: одни СОЧИНЯЮТ значения в профиль — такие модели как инструмент не выдаются никогда; другие ПЕРЕНОСЯТ в профиль собственные документы человека и ничего не выдумывают — такие модели доверить можно.",
    "capabilities.kind.authors": "сочиняет значения — модели не выдаётся",
    "capabilities.kind.transcribes": "переносит собственные документы человека",
    "capabilities.face.web": "есть в веб-интерфейсе",
    "clinvar.low_confidence": "низкая достоверность (0-1 звезды): уровень пересмотра не подтверждает это с силой, которую подразумевает класс",
    "clinvar.low_confidence_note": "{n} из них опираются на пересмотр ClinVar 0-1 звезды — патогенная трактовка на таком уровне — самый переоценённый класс для потребительского секвенирования; воспринимать как повод перепроверить, а не как находку.",
    "clinvar.empty": "Значимых вариантов ClinVar в вашем VCF не извлечено.",
    "clinvar.header": "**Клинически значимые находки (ClinVar): {n}**",
    "clinvar.shown": "(показаны первые {n})",
    "clinvar.how_to_read": "**Как это читать.**",

    # ── вторичные находки ACMG ───────────────────────────────────────────
    "acmg.unread_header": "Прочитано недостаточно глубоко для решения — генов панели: {n}. Отрицательный результат по ним не является утверждением:",
    "acmg.needs_phase_header": "Находок в генах, которым нужны обе повреждённые копии, обнаруженных как две гетерозиготы: {n}. Лежат ли они на разных хромосомах — а именно это делало бы их биаллельными — нефазированный файл сказать не может; в цис человек обычный носитель. Разрешается генотипом родителя или длинными ридами:",
    "acmg.needs_class_header": "Находок в генах, которые ACMG репортит только для узкого класса вариантов: {n} — класс нужно установить, прежде чем это станет находкой:",
    "acmg.how_to_run": "Запустите `scholion acmg-scan` — он сверит ваш VCF со списком генов "
                       "ACMG Secondary Findings. Ему нужен опубликованный файл ClinVar для вашей "
                       "сборки и больше ничего, а когда файла нет — он печатает ту самую "
                       "единственную загрузку.",
    "acmg.header": "**Вторичные находки — {version}** ({genes} генов, проверено {scanned})",
    "acmg.reportable": "**Требует обсуждения с генетиком: {n}**",
    "acmg.coverage_unknown": "покрытие этих генов на этом геноме не измерялось, поэтому «ничего не найдено» здесь означает «ничего не найдено в том, что прочитано», а сколько прочитано — неизвестно. Чем это закрывается, говорит `scholion limits`.",
    "acmg.negative_qualified": "⚠ этот ответ опирается на неполное чтение: из {genes} генов {weak} покрыты ниже {threshold} % при 10× и {unmeasured} не измерены вовсе. Отрицательный результат по непрочитанному гену — это не утверждение о гене, а утверждение о файле.",
    "acmg.no_reportable": "Находок, подлежащих действию, нет.",
    "acmg.carriers": "Носительство (для себя не значимо, значимо для планирования "
                     "семьи): {n}",
    "acmg.caveat": "Пустой результат не значит «генетических рисков нет»: короткие чтения "
                   "не видят структурные варианты, экспансии повторов и регионы с псевдогенами.",

    # ── полигенные риски ─────────────────────────────────────────────────
    "prs.not_ready": "Полигенные баллы ещё не рассчитаны.",
    "prs.title": "**Полигенные риски (PGS)**",
    "prs.reliable": "{reliable}/{total} надёжных",
    "prs.population_not_stated": "⚠ перцентили посчитаны относительно референсной популяции {population}, и это ДЕФОЛТ — вас не спрашивали. Перцентиль это положение внутри популяции; относительно чужой это не ваше положение. `scholion profile --ancestry EUR|AFR|EAS|SAS|AMR`",
    "prs.reference": "референс {population}",
    "prs.above_average": "Заметно выше среднего (скрининг):",
    "prs.withheld_by_sex": "не показан: признак существует только у пола {sex}, а перцентиль про орган, которого у читателя нет, не становится меньшей ошибкой оттого, что напечатан вежливо",
    "prs.withheld_sex_unknown": "не показан: признак существует только у пола {sex}, а пол в профиле не указан — ответ на «мы не знаем» это «тогда мы не говорим», а не умолчание",
    "prs.caveat.strand_ambiguous": "вариант, у которого два аллеля комплементарны друг другу (A/T, C/G), совпадает с любой цепью, поэтому перепутанная цепь в исходном файле неотличима от верного вызова — для чипа этот сборник такие локусы называет, а внутри скора, который считает не он, назвать не может",
    "prs.caveat.missing_as_zero": "вариант модели, отсутствующий в вашем файле, просто не добавляется к сумме — арифметически это импутация нулевой дозы, и она смещает скор вниз; какая доля ВЕСА модели реально присутствовала, измеряется и показывается, а перцентиль ниже порога снимается с доверия, а не снабжается сноской",
    "prs.caveat.hard_genotypes": "только жёсткие генотипы: неуверенный вызов учитывается как уверенный, без дозировки",
    "prs.caveat.panel_out_of_date": "Эти перцентили посчитаны против панели {used}, а по вашему геному определена {applies}. Перцентиль — это место внутри популяции; против другой это не ваше место. Пересчитайте, чтобы одно сошлось с другим.",
    "prs.caveat.panel_defaulted": "Эти перцентили посчитаны против панели {used}, потому что никакая не была определена — её никто не выбирал. Какая панель подходит, выясняется при подготовке генома, а до тех пор число — это место внутри популяции, которая может быть не вашей.",
    "prs.caveat.reference_panel": "перцентиль — это положение внутри референсной выборки; пакет расчёта пинуется по версии, а не по хешу, а референсная панель, которую он скачивает при первом запуске, не пинуется вовсе — две машины в принципе могут поставить один и тот же геном относительно разных референсных данных",
    "prs.no_model": "нет модели",
    "prs.measure_legend": "Под каждым перцентилем — УСТОЙЧИВОСТЬ числа (его разброс по пяти референсным популяциям · разброс по моделям, посчитанным для признака · доля модели, покрытая вашим файлом) и ИНФОРМАТИВНОСТЬ модели (AUROC — как часто один балл отличает случай от не-случая · что диапазон балла от P10 до P90 делает с исходом, в расчёте на стандартное отклонение, как это указывает каталог). «не записано» значит, что величины нет на этой машине, а не что она мала.",
    "prs.measure_line": "устойчивость: {stability} | информативность: {informativeness}",
    "prs.stab_ancestry": "по {pops} перцентиль расходится на {pp} п.п.",
    "prs.stab_ancestry_missing": "разброс по популяциям не записан",
    "prs.stab_models": "по {models} — на {pp} п.п.",
    "prs.stab_models_missing": "разброс по моделям не записан — пересчитайте панель, чтобы он появился",
    "prs.stab_coverage": "покрытие {pct} %",
    "prs.info_auroc": "AUROC {auroc}",
    "prs.info_ratio": "{kind} P90 против P10 ×{x}",
    "prs.info_shift": "P90 против P10 сдвигает признак на {value} в единицах самого исследования",
    "prs.info_missing": "размер эффекта моделью не указан",
    "prs.models_line": "    · посчитано {scored} из {candidates}; не посчитано {not_scored} — за пределом --models {limit}",
    "count.models.one": "{n} модель",
    "count.models.few": "{n} модели",
    "count.models.many": "{n} моделей",
    "count.candidates.one": "{n} кандидат",
    "count.candidates.few": "{n} кандидата",
    "count.candidates.many": "{n} кандидатов",
    "count.populations.one": "{n} референсная популяция",
    "count.populations.few": "{n} референсные популяции",
    "count.populations.many": "{n} референсных популяций",
    "prs.evidence_legend": "Уровень доказательности: ✚ клинически валидировано · "
                           "· вспомогательный контекст · без метки — исследовательский уровень",

    # ── слой долголетия ──────────────────────────────────────────────────
    "longevity.verdict.see_apoe": "читается в карточке APOE выше",
    "longevity.verdict.plus": "носитель, полная доза",
    "longevity.verdict.plus_partial": "носитель, одна копия",
    "longevity.verdict.lean_plus": "скорее в плюс",
    "longevity.verdict.good": "благоприятный вариант",
    "longevity.verdict.neutral": "без эффекта в эту сторону",
    "longevity.verdict.flag": "вариант, о котором стоит знать",
    "longevity.not_ready": "Слой долголетия ещё не построен.",
    "longevity.title": "**Долголетие — генетический слой (LongevityMap)**",
    "longevity.apoe": "APOE: **{epsilon}** (rs429358={rs429358}, rs7412={rs7412})",
    "longevity.key_markers": "Ключевые маркёры:",
    "longevity.carries": "несёт аллель",
    "longevity.significant": "Значимых носительств: {carriers} в {genes}.",
    "longevity.genes_first": "Гены (первые): {genes}",
    # предложный падеж: «в 1 гене», «в 30 генах»
    "count.genes_in.one": "{n} гене",
    "count.genes_in.few": "{n} генах",
    "count.genes_in.many": "{n} генах",

    # ── образ жизни (носимые устройства) ─────────────────────────────────
    "lifestyle.empty": "Данных образа жизни (носимые устройства) пока нет.",
    "lifestyle.title": "**Образ жизни (носимые устройства)**",
    "lifestyle.fitness_score": "интегральный балл формы: {score}/100",
    "lifestyle.coverage": "дней с измерением: {n} (из {days})",
    "lifestyle.not_distinguishable": "движение за эти месяцы — {delta} {unit}, а различить эти данные способны разницу от {mdd} — поэтому направление не утверждается",
    "lifestyle.improving": "улучшение",
    "lifestyle.worsening": "ухудшение",
    "lifestyle.comparable_from": "ряд сопоставим с {date} (раньше — другой прибор)",
    "lifestyle.workouts": "Тренировки за всё время (топ): {items}",

    # ── сверка бланков с профилем ────────────────────────────────────────
    "reconcile.title": "**Сверка бланков ↔ профиль (labs.json)**",
    "reconcile.folder": "Папка: {path}",
    "reconcile.pdf_total": "PDF всего: {n}",
    "reconcile.pdf_non_lab": "не-лабораторных/прочих: {n}",
    "reconcile.points_matched": "совпало точек: {n}",
    "reconcile.markers_seen": "распознано маркеров: {n}",
    "reconcile.unreadable": "НЕ ПРОЧИТАНО ({n}) — возможны потерянные данные, откройте файлы "
                            "на Mac (материализация iCloud) и повторите:",
    "reconcile.bytes": "{bytes}",
    "reconcile.all_readable": "Нечитаемых файлов нет — все PDF отдали текст.",
    "reconcile.missing": "ПРОПУЩЕНО в профиле ({n}) — есть в бланке, нет в labs.json:",
    "reconcile.no_missing": "Пропущенных точек нет — все распознанные значения из бланков "
                            "есть в профиле.",
    "reconcile.mismatch": "РАСХОЖДЕНИЯ ({n}) — дата совпадает, значение отличается "
                          "(ошибка распознавания или конфликт единиц → ручная проверка):",
    "reconcile.mismatch_row": "{marker} {date}: в бланке {pdf} ≠ в профиле {profile}",
    "reconcile.provenance": "Провенанс записан: {path}.",
    "reconcile.read_only": "Инструмент только читает — labs.json не меняется.",
    "reconcile.how_to_fill": "Пропуски заносить командой ingest-labs или вручную "
                             "после проверки.",

    # ── справка об образе жизни ──────────────────────────────────────────
    "brief.not_compiled": "Справка не составлена: {reason}",
    "brief.title_default": "Справка об образе жизни",
    "brief.compiled": "составлена {date}",
    "brief.needs_review": "ТРЕБУЮТ ПЕРЕСМОТРА (появились новые данные после последней правки):",
    "brief.stale_block": "{title} — правился {reviewed}, свежие данные {newest}",
    "brief.review_hint": "что пересмотреть: {text}",
    "brief.actions": "ЧТО СДЕЛАТЬ",
    "brief.dropped": "СНЯТЫЕ ТРЕВОГИ",

    # ── фокус внимания ───────────────────────────────────────────────────
    "focus.not_set": "Фокус не задан.",
    "focus.title": "**Фокус внимания: {title}**",
    "focus.since": "с {date}",
    "focus.now": "**{label}:** сейчас {value}",
    "focus.as_of": "на {date}",
    "focus.last_nights_export": "последние {nights} экспорта "
                                "({window_from} → {window_to}): {value} {unit}",
    "focus.last_nights": "последние {nights}: {value} {unit}",
    "focus.baseline": "база {value} ({note})",
    "focus.shift": "сдвиг {delta} ({direction})",
    "focus.target": "ориентир {value} {unit} — {note}",
    "focus.levers": "**Рычаги** (наблюдения по собственным данным, не предписания):",
    "focus.lever": "{title} — ожидаемый эффект {expected}",
    "focus.lever_now": "сейчас: {text}",
    "focus.journal": "**Журнал эпизодов:**",
    "focus.tracks": "**ЦЕЛИ ({n}):**",
    "focus.closed": "закрыто: {text}",
    "focus.evidence": "**Что уже сделано инструментально ({n}):**",
    "focus.does_not_answer": "не отвечает: {text}",
    "focus.open": "**Осталось открытым:**",
    "focus.questions": "**Вопросы:**",
    "count.nights.one": "{n} ночь",
    "count.nights.few": "{n} ночи",
    "count.nights.many": "{n} ночей",

    # ── статус генома ────────────────────────────────────────────────────
    "genome_status.connected": "**Геном подключён.**",
    "genome_status.several_files": "**В папке лежит {count} геномных файлов, и ни один из них не «тот самый», пока вы не скажете, какой.** Читать тот, что первый по алфавиту, — это как раз способ ответить про APOE по первой хромосоме в наборе по хромосомам и ответить про того, чьё имя раньше в алфавите, в папке на двоих. И то и другое выглядит как ответ.",
    "genome_status.several_files_fix": "Назовите свой: {cmd}",
    "genome_status.several_samples": "**В файле {count} образцов — {names} — а десятая колонка не является именем человека.** Трио или совместный вызов кладут нескольких людей рядом; чтение первого молча выдаёт другого, возможно родственника, за вас.",
    "genome_status.several_samples_fix": "Скажите, какой образец ваш: {cmd}",
    "genome_status.sample": "Образец: {name}",
    "genome_status.sample_not_found": "**Названного образца в этом файле нет.** В нём есть: {names}.",
    "genome_status.sample_not_found_fix": "Назовите один из них: {cmd}",
    "genome.refused_head.sample_not_found": "образца, названного в SCHOLION_GENOME_SAMPLE, в этом файле нет.",
    "genome.refused_head.sample_not_chosen": "в файле несколько образцов, и ни один не выбран.",
    "genome.refused.sample_not_found": "Координата найдена, и файл тоже. Образца, названного в `SCHOLION_GENOME_SAMPLE`, среди образцов файла нет — `scholion genome-status` перечисляет те имена, которые в файле есть.",
    "genome.refused.sample_not_chosen": "Координата найдена. В файле несколько образцов, и ни один не выбран; `SCHOLION_GENOME_SAMPLE` говорит, какой ваш.",
    "genome_status.foreign_head": "**Читаемого VCF нет — но папка не пуста, и то, что в ней лежит, это геномные данные.**",
    "genome_status.foreign_bcf": "  · {path} — BCF. Конвертируется один раз: `bcftools view -Oz -o <файл>.vcf.gz {path} && tabix -p vcf <файл>.vcf.gz`",
    "genome_status.foreign_vcf_container": "  · {path} — VCF в контейнере, в который читатели не умеют позиционироваться. Пережмите bgzip и постройте индекс.",
    "genome_status.foreign_gvcf": "  · {path} — gVCF: в нём референсные блоки, а не строка на позицию, и позиция внутри блока — не строка. Сначала преобразуйте в обычный VCF (`bcftools convert --gvcf2vcf`).",
    "genome_status.foreign_alignment": "  · {path} — выравнивание (BAM/CRAM), а не вызванные варианты. Это вход конвейера, а не его выход: `scholion doc preparing-the-genome`, §5.",
    "genome_status.foreign_reads": "  · {path} — сырые риды (FASTQ). Их нужно сначала выровнять и вызвать варианты; путь описан в `scholion doc preparing-the-genome`.",
    "genome_status.foreign_archive": "  · {path} — архив. Распакуйте и оставьте в папке сам файл; вслепую архивы здесь не открываются.",
    "genome_status.foreign_array": "  · {path} — выгрузка потребительского чипа, которую не удалось прочитать как чип. `scholion genome-status` называет вендора, когда узнаёт файл.",
    "genome.sample_not_chosen": "в файле несколько образцов ({names}), и ни один не выбран — SCHOLION_GENOME_SAMPLE говорит, какой ваш",
    "genome.no_coordinate": "координаты нет",
    "genome.no_row_and_build_unknown": "Строки на этой позиции нет, и сборка, на которой вызван файл, не установлена. Эти два дают одну и ту же тишину: позиция, прочитанная не в той системе координат, пуста ровно по той же причине, что и позиция без варианта. Названная сборка решает это одной переменной — `SCHOLION_GENOME_ASSEMBLY=GRCh37 scholion genome <rsid>`.",
    "genome.refused_head.no_row_and_build_unknown": "на этой позиции ничего, и сборка файла не установлена.",
    "genome.refused_head.sample_not_chosen_result": "в файле несколько образцов, и ни один не выбран.",
    "genome.refused_head.no_file": "полная геномная база ещё не подключена.",
    "genome.refused_head.unreadable_file": "геномный файл на месте и не читается.",
    "genome.refused_head.assembly_unsupported": "файл в сборке, в которой этот каталог отвечать не умеет.",
    "genome.refused_head.chosen_missing": "выбранного файла генома больше нет на месте, и другой не подставлен: подставить другой значило бы ответить не из того файла, который выбрали",
    "genome.refused_head.several_files": "геномных файлов больше одного, и ни один не выбран.",
    "genome.refused_head.several_samples": "в файле несколько образцов, и ни один не выбран.",
    "genome.refused_head.foreign_input": "в папке есть геномные данные, но нет читаемого VCF.",
    "genome.refused_head.another_person": "геном в папке принадлежит другому человеку, чем этот профиль, и поэтому не читается.",
    "genome.refused_head.engine_unknown": "в SCHOLION_GENOME_ENGINE названо не то, чем этот проект умеет читать.",
    "genome.refused_head.engine_missing": "читатель, названный в SCHOLION_GENOME_ENGINE, здесь не установлен.",
    "genome.refused_head.no_engine": "геномный файл на месте, а читателя не установлено.",
    "genome.refused_head.multiallelic": "у позиции больше одного альтернативного аллеля.",
    "genome.refused.multiallelic": "Координата известна, и наблюдённые здесь аллели тоже "
                                   "({alleles}). Какой из альтернативных имела в виду работа — "
                                   "в источнике не сказано, и сборка не выбирает за него: "
                                   "генотип, сравнённый с угаданным аллелем, хуже, чем "
                                   "несравнённый. Альтернативных аллелей на позиции: {n}.",
    "genome.refused.no_file": "Координата найдена, но полная геномная база ещё не подключена (нужны genome/*.vcf.gz + .tbi).",
    "genome.refused.no_answer": "Координата найдена, файл подключён, но читатель не вернул на этой позиции ничего — чаще всего это отсутствующий или сломанный индекс (`.tbi`/`.csi`). `scholion genome-status` говорит, какой. Пустой ответ — это не референс, и как референс он не подаётся.",
    "genome.refused.unreadable_file": "Координата найдена. Файл в геномной папке в таком виде не читается — `scholion genome-status` печатает одну команду, которая это чинит. Ничего не отсутствует и ничего не нужно добывать.",
    "genome.refused.assembly_unsupported": "Координата найдена, и ваш файл тоже: он подключён и проиндексирован. Он вызван на сборке, координат для которой в каталоге нет, и на лету ничего не пересчитывается — пересчитанная позиция указывает на настоящее основание, но не на то. `scholion genome-status` называет сборку и что делать.",
    "genome.refused.several_files": "Координата найдена. Геномных файлов в папке больше одного, и какой из них ваш — не нам угадывать: `SCHOLION_GENOME_VCF` говорит это одной переменной.",
    "genome.refused.several_samples": "Координата найдена. В файле несколько образцов — трио или совместный вызов, — и чтение первой колонки выдало бы за вас другого человека. `SCHOLION_GENOME_SAMPLE` говорит, какой образец ваш.",
    "genome.refused.foreign_input": "Координата найдена. В папке лежат геномные данные, которые не являются читаемым VCF — `scholion genome-status` называет каждый файл и то, что ему нужно.",
    "genome.refused.another_person": 'Координата найдена, файл тоже — но SUBJECT.json в папке говорит, что геном — опубликованный референсный образец, а в этом профиле данные другого человека. Генотип одного рядом с лабораторной историей другого даёт выводы ни о ком, поэтому ничего не читается. Дайте референсному геному собственный профиль: `scholion init --dir <папка> --subject reference`, затем укажите SCHOLION_PROFILE_DIR и SCHOLION_GENOME_DIR.',
    "genome.refused.no_engine": "Координата найдена и файл на месте, но не установлено ни одного читателя: bcftools, pysam или рабочий индекс `.tbi` рядом с файлом.",
    "genome.refused_head.truncated": "геномный файл обрывается раньше своего конца: он оборван, и за обрывом прочитать нечего.",
    "genome.refused_head.pass_failed": "проход по геномному файлу остановился на середине, и из него не читается ничего.",
    "genome.refused_head.needs_index": "файл слишком велик, чтобы читать его за один проход, и ему нужен индекс.",
    "genome.refused_head.alleles_not_comparable": "генотип называет аллель, которую нельзя записать рядом с собственной аллелью этого локуса.",
    "genome.refused_head.not_sequenced": "вход — чип, а вопрос по области чипу не задать.",
    "genome.unreadable_truncated": "файл обрывается без завершающего блока, который bgzip всегда пишет последним: он оборван — копированием или загрузкой, не дошедшими до конца. Из него не читается ничего, потому что у позиции за обрывом нет строки и она ответила бы «референс». Возьмите полную копию и сравните размеры.",
    "genome.unreadable_pass_failed": "проход по файлу остановился на середине ({detail}). Из него не читается ничего, потому что у позиции за местом сбоя нет строки и она ответила бы «референс». `gzip -t` по файлу скажет, где он повреждён.",
    "genome.unreadable_not_a_vcf": "файл не открывается как VCF — его первая строка не заголовок VCF. Из него не читается ничего.",
    "genome.too_large_for_one_pass": "у файла нет индекса, и он больше {mb} МБ, которые читатель за один проход готов взять: дальше один проход — не ожидание, а зависание. Что это закрывает: индекс — `bgzip` + `tabix -p vcf` — или `SCHOLION_LINEAR_MAX_MB`, поднятый тем, кто готов ждать.",
    "genome.alleles_not_comparable": "строка на этой позиции — {ref}>{alt}, генотип — «{value}»: он называет рядом с собственной аллелью этого локуса аллель другой длины или делецию, накрывающую это основание. Записать их одной парой букв нельзя, поэтому не читается ничего. Что это закрывает: те же варианты, нормализованные по одному на строку (`bcftools norm -m-`).",
    "genome.acmg_assembly_crossed_personal": "Таблица ACMG на диске сопоставлена в {table}, а подключённый сейчас геномный файл — в {other}. Каждая координата в ней для этого файла сдвинута на полмиллиона оснований, поэтому как находки она не читается — ни перечисленные в ней, ни тишина между ними. `scholion acmg-scan` запишет новую таблицу по этому файлу.",
    "genome.acmg_assembly_crossed_clinvar": "Таблица ACMG на диске сопоставлена между геномом в {table} и выпуском ClinVar в {other}. Таблица, сопоставленная поперёк сборок, несёт молчаливый ноль — ничего не совпало, поэтому ничего не найдено, — и как находки не читается. `scholion acmg-scan` теперь отказывается от такой пары и запишет новую таблицу по файлу ClinVar для {table}.",
    "genome_status.file": "Файл: {path}",
    'genome_status.no_index_linear': 'Рядом с файлом нет индекса, и нет установленного инструмента, который его построит, — поэтому файл читается один раз от начала до конца, и сохраняется то, что было запрошено. Первый вопрос занимает столько, сколько один проход по файлу; следующие — мгновенны. Чтобы мгновенными были все: `bgzip` и `tabix -p vcf`, если эти инструменты доступны.',
    'limits.no_index_what': 'любой ген за пределами каталога локусов (их {n}) и всё прочее, чему нужна целая область',
    'limits.no_index_why': 'у геномного файла нет индекса, и ни один инструмент, который его строит, не установлен. Файл читается один раз от начала до конца, и этого хватает на каталожные позиции и на стоящую на них фармакогенетику — область не позиция, и перейти к ней поиском не к чему. Такой вопрос здесь отказывает, а не возвращает пустой список: пустой список читался бы как «в этом гене нет вариантов».',
    'limits.no_index_closes': 'индекс: `bgzip -c file.vcf > file.vcf.gz && tabix -p vcf file.vcf.gz`. После этого из того же файла отвечают все вопросы списка.',
    'acmg_scan.no_genome': 'Сканировать нечего: файла вариантов нет. `scholion genome-status` скажет, что лежит в геномной папке и что он из этого понял.',
    'acmg_scan.no_clinvar': 'Этот экран сопоставляет ваш файл с ClinVar, а файла ClinVar здесь нет. Это одна загрузка, и файл нужен ровно тот, что опубликован для {assembly} — сборки, в которой ваш собственный файл:\n\n    curl -L -o clinvar.vcf.gz {url}\n\nДальше `scholion acmg-scan --clinvar clinvar.vcf.gz` — или положите файл в геномную папку и запустите `scholion acmg-scan`. Наружу о вас не уходит ничего: скачивается публичный справочный файл, сопоставление идёт на этой машине.',
    'acmg_scan.assembly_mismatch': 'Ваш файл собран по {personal}, а этот файл ClinVar опубликован для {clinvar}. Скрещённые сборки не падают — они либо не находят ничего, либо совпадают с координатой, которая в другой сборке принадлежит другому основанию, и то и другое выглядит как ответ. Не просканировано ничего. Файл для вашей сборки:\n\n    curl -L -o clinvar.vcf.gz {url}',
    'acmg_scan.clinvar_assembly_unknown': 'Сборку этого файла ClinVar по нему установить не удалось, а ваш собственный файл — {assembly}. Сопоставление по позиции между двумя сборками даёт молчание или чужой вариант, поэтому не просканировано ничего. Опубликованный файл для вашей сборки свою сборку объявляет:\n\n    curl -L -o clinvar.vcf.gz {url}',
    'acmg_scan.clinvar_empty': 'Из этого файла ClinVar не вышло ни одного патогенного или вероятно патогенного варианта в 84 генах списка — и это свойство файла, а не чьего-либо генома: чаще всего в нём нет поля GENEINFO, то есть это аннотированная выжимка, а не опубликованный ClinVar VCF.',
    'acmg_scan.done': 'Экран прогнан: находок в генах вторичных находок ACMG — {found}, из них к разговору с врачом, а не к носительству — {yes}. Таблица лежит в {path}, её читает `scholion acmg`. Пустой результат — нормальный и скорее хороший исход: он означает, что ничего такого не нашлось в прочитанном, а не что генетических рисков нет: структурные варианты, экспансии повторов и псевдогенные области этим методом не видны.',
    'acmg_scan.no_sample_column': 'В этом файле нет колонки образца — позиции и аллели есть, а чьего-либо генотипа нет. Файл только с сайтами не может сказать, что кто-то несёт, поэтому не просканировано ничего. `scholion genome-status` скажет, что это за файл.',
    'acmg_scan.sample_not_found': 'Образец, названный в `SCHOLION_GENOME_SAMPLE` — {name}, — в этом файле отсутствует. В нём: {names}. Не просканировано ничего.',
    'acmg_scan.several_samples': 'В этом файле несколько образцов — {names} — и ни один не выбран. Трио или совместный вызов кладёт нескольких людей рядом, и чтение первой колонки просканировало бы как вас кого-то другого, возможно родственника. Не просканировано ничего. Скажите, какой образец ваш: {cmd}',
    'acmg_scan.personal_assembly_unknown': 'Сборку вашего собственного файла по нему установить не удалось — ни длин контигов, ни подписи провайдера, ни строки `##reference=`, ни индекса для пробы по данным. Сопоставлять файл неизвестной сборки с ClinVar по позиции — это тот же скрещённый прогон, только с одной пустой стороной, поэтому не просканировано ничего. Если сборка вам известна, назовите её: `SCHOLION_GENOME_ASSEMBLY=GRCh38 scholion acmg-scan` (или GRCh37).',
    'acmg_scan.no_calls.one': 'В {n} позиции списка генотип не вызван (`./.`), и строка в таблицу не вошла: no-call — это не референс и не находка, а позиция, которую файл не прочитал, и «ничего не найдено» там ничего не значит.',
    'acmg_scan.no_calls.few': 'В {n} позициях списка генотип не вызван (`./.`), и строки в таблицу не вошли: no-call — это не референс и не находка, а позиция, которую файл не прочитал, и «ничего не найдено» там ничего не значит.',
    'acmg_scan.no_calls.many': 'В {n} позициях списка генотип не вызван (`./.`), и строки в таблицу не вошли: no-call — это не референс и не находка, а позиция, которую файл не прочитал, и «ничего не найдено» там ничего не значит.',
    'acmg_scan.filtered.one': '{n} совпавшая строка несёт FILTER, отличный от PASS, и записана как `filtered`, а не решена: сам вызыватель за этот вызов не поручился, и посмотреть на позицию заново нужно раньше, чем о ней сообщать.',
    'acmg_scan.filtered.few': '{n} совпавшие строки несут FILTER, отличный от PASS, и записаны как `filtered`, а не решены: сам вызыватель за эти вызовы не поручился, и посмотреть на позиции заново нужно раньше, чем о них сообщать.',
    'acmg_scan.filtered.many': '{n} совпавших строк несут FILTER, отличный от PASS, и записаны как `filtered`, а не решены: сам вызыватель за эти вызовы не поручился, и посмотреть на позиции заново нужно раньше, чем о них сообщать.',
    'paths.region': 'любой ген за пределами каталога — запрос по целой области',
    'paths.why.needs_index': 'файл читается без индекса: один проход собрал каталожные позиции, а область — это не позиция. Открывает `bgzip` + `tabix -p vcf`.',
    'genome.refused.needs_index': 'Ген в аннотации найден, и ваш файл подключён — он просто читается БЕЗ индекса. Такой читатель делает один проход и сохраняет каталожные позиции; ген — это тысячи позиций, которых заранее никто не называл, поэтому здесь на этот вопрос не отвечают. Это не «в гене нет вариантов»: такое было бы утверждением о вас, а его никто не измерял. Что это закрывает: индекс — `bgzip -c file.vcf > file.vcf.gz && tabix -p vcf file.vcf.gz`, — после чего из того же файла отвечают все вопросы списка.',
    'limits.scope.no_index': 'У геномного файла нет индекса, и ни один инструмент, который его строит, не установлен. Файл читается один раз от начала до конца, и этого хватает на 54 каталожных локуса и на всю фармакогенетику, которая на них стоит. Чего так НЕ ответить: любой ген вне каталога и всё прочее, чему нужна целая область, — они отказывают, а не возвращают пустой список. Что это закрывает: `bgzip` + `tabix -p vcf`.',
    'genome_status.paths_head': 'Что можно спросить у этого файла, а что нельзя:',
    'genome_status.path_open': '  · {name} — открыто',
    'genome_status.path_closed': '  · {name} — закрыто: {why}',
    'paths.loci': 'каталог локусов (выверенных позиций: {n})',
    'paths.pgx': 'фармакогенетика — препарат против генотипа',
    'paths.clinvar': 'ClinVar: патогенные и вероятно патогенные находки',
    'paths.acmg': 'список вторичных находок ACMG (84 гена)',
    'paths.pgs': 'полигенные шкалы',
    'paths.why.no_genome': 'геном не подключён',
    'paths.why.input_too_narrow': 'этот вход не может нести ответ — `scholion limits` скажет, какой может',
    'paths.why.scan_not_run': 'аннотация для этого файла ещё не построена — путь читает таблицу, а таблицы нет. Шаг, который её пишет, описан в `scholion doc preparing-the-genome`.',
    'paths.why.not_sequenced': 'этот вход — чип, а не секвенированный геном: он читает позиции, которые кто-то выбрал, а ген — это участок, которого никто не выбирал. Открывает секвенированный геном (VCF).',
    'genome.refused.not_sequenced': 'Ген в аннотации найден, а подключённый вход — генотипирующий чип. Чип читает позиции, выбранные его производителем, — несколько сотен тысяч, — а ген — это участок из тысяч позиций, которых никто не выбирал, поэтому здесь на этот вопрос не отвечают. Это не «в гене нет вариантов»: никто не смотрел. Что отвечает: секвенированный геном (VCF), из которого отвечают все вопросы списка.',
    "genome_status.reader": "Чтение: {reader}",
    "genome_status.not_ready": "**Геном найден, но не готов к чтению:** {reason}",
    "genome_status.no_index": "нет индекса .tbi",
    "genome_status.assembly_unknown_actions": "Три способа установить, от дешёвого к дорогому:\n  1. **Если знаете, кто делал секвенирование** — сборка названа в их отчёте, и хватит одной переменной: `SCHOLION_GENOME_ASSEMBLY=GRCh37 scholion genome-status` (или GRCh38, или T2T-CHM13v2.0).\n  2. **Прочитать из заголовка:** `bcftools view -h {path} | grep -E '##(contig|reference)'` — `length=` рядом с chr1 отвечает сразу: 249250621 — GRCh37, 248956422 — GRCh38, 248387328 — T2T.\n  3. **Вписать контиги один раз**, чтобы файл дальше отвечал сам за себя: `bcftools reheader -f <reference>.fai {path}`.",
    "genome_status.assembly_mismatch": "**Геномный слой отключён: файл вызван относительно {found}, а каталог координат — в {want}.** Один и тот же вариант лежит в разных сборках на разных позициях: например, APOE rs429358 — это 19:44 908 684 в GRCh38 и 19:45 411 941 в GRCh37. Запрос координаты одной сборки к файлу другой попадает в другой ген, и ответ окажется неверным, не выглядя неверным.",
    "genome_status.assembly_fix": "Перевести файл в {want} (`CrossMap` или `bcftools +liftover` с chain-файлом) либо пере-вызвать варианты из выравнивания относительно этой сборки. Координаты здесь сознательно не пересчитываются на лету: тихое преобразование добавило бы ровно тот класс ошибок, ради устранения которого слой и существует. Всё вне генома — анализы, назначения, носимые — работает как обычно.",
    "genome_status.coordinates_secondary": "читается по координатам {assembly} — каталог несёт в этой сборке {have} локусов из {total}, остальные из этого файла не читаются, а не угадываются. Между сборками ничего не пересчитывается.",
    "genome_status.assembly_ok": "Сборка: {found}",
    "genome_status.assembly_unknown": "**Сборка: не установлена.** В заголовке нет ни длин контигов, ни строки `##reference`, и за концом первой хромосомы GRCh38 не нашлось ни одного варианта — значит и данные её не выдали. Ответы считаются так, будто файл в {want}; если это не так, каждый геномный ответ — про не ту позицию.",
    "genome_status.unusable_plain": "**Геномный файл лежит рядом и пока не читается:** {path} — это обычный `.vcf`. Читатели ищут по файлу позиционно, поэтому он должен быть блочно сжат и проиндексирован. Это одна команда, а не другой файл.",
    "genome_status.unusable_gzip_not_bgzip": "**Геномный файл лежит рядом и пока не читается:** {path} — он сжат обычным gzip, а не bgzip. Выглядит правильно, но `tabix` откажется с сообщением о формате, которое ничего не объясняет.",
    "genome_status.unusable_fix": "Починить так: {cmd}",
    "genome_status.unusable_truncated": "**Геномный файл лежит рядом и пока не читается:** {path} — он обрывается без завершающего блока, который bgzip всегда пишет последним, то есть оборван копированием или загрузкой, которые не дошли до конца. Из него не читается ничего: каждая позиция за обрывом ответила бы «референс». Возьмите полную копию и сравните размеры.",
    "genome_status.unusable_pass_failed": "**Геномный файл лежит рядом и до конца не прочитался:** {path} — проход по нему остановился на середине, чаще всего на повреждённом блоке. Из него не читается ничего, потому что позиция за местом сбоя ответила бы «референс».",
    "genome_status.build_index": "Собрать индекс: tabix -p vcf <файл>",
    "genome_status.no_vcf": "**Полный VCF не подключён** — геномная часть отвечает "
                            "«база не подключена».",
    "genome_status.how_to_get": "Как его получить: `scholion doc preparing-the-genome`.",
    "genome_status.gaps": "Пробелы (гены-цели без данных): {genes}",

    # ── обновления генома (свежая ClinVar против личного VCF) ────────────
    "genome_updates.not_run": "Сверка со свежей ClinVar ещё не проводилась "
                              "(genome/whats_new.json нет).",
    "genome_updates.last_checked": "**Последняя проверка:** {date}",
    "genome_updates.release": "релиз ClinVar: {release}",
    "genome_updates.new": "Новое",
    "genome_updates.changed": "Изменилось",

    # ── результат пишущей команды ────────────────────────────────────────
    "write.failed": "не выполнено",
    "write.saved": "Записано",

    # ── множественные формы ──────────────────────────────────────────────
    "count.markers.one": "{n} показатель",
    "count.markers.few": "{n} показателя",
    "count.markers.many": "{n} показателей",

    # ── CLI: что печатает команда по завершении ───────────────────────
    "init.dir_created": "✓ каталог данных: {path}",
    "init.written": "  создано: {files}",
    "init.skipped": "  уже было (не тронуто): {files} — перезаписать: --force",
    "init.demo_notice": "  Это ВЫМЫШЛЕННЫЙ человек, а не чьи-то настоящие данные.",
    "init.demo_next": "  Посмотреть:  scholion overview   ·   scholion serve",
    "init.why_sex_asked": "Два вопроса сейчас избавляют от неверного числа потом: шесть референсных интервалов (тестостерон, ферритин, креатинин, гематокрит, гемоглобин, мочевая кислота) зависят от пола, а бланки печатают строки по возрастным диапазонам. Enter — пропустить.",
    "init.ask_sex": "  пол (м / ж, Enter — пропустить): ",
    "init.ask_birth_year": "  год рождения (Enter — пропустить): ",
    "init.sex_not_recorded": "Пол и год рождения не записаны. Шесть показателей будут показаны БЕЗ референсного интервала, а не против возможно неверного — `scholion profile --sex male|female --birth-year YYYY`, когда захотите вернуть.",
    "init.next_steps": "  Дальше — что есть, то и первым:\n"
                       "     PDF анализов в папке   scholion ingest-labs \"<папка>\"\n"
                       "     список назначений      scholion add-med \"<название>\" --dose \"...\"\n"
                       "     пока ничего            scholion demo   (вымышленный человек, осмотреться)\n"
                       "  Потом:  scholion serve   открывает всё это в браузере.",
    "tools.only_for_genome": "\nВсё, что ниже, относится ТОЛЬКО к геномному треку — сборке VCF из сырых "
                             "чтений.\nАнализам, назначениям и файлу потребительского чипа ничего из "
                             "этого не нужно; приложение уже работает.",
    "skill.file_missing": "✗ файл инструкции не найден: {path}\n  Похоже, пакет собран неполно "
                          "— переустановите его.",
    "assistant.context_saved": "Контекст сохранён: {path} ({chars} символов).",
    "assistant.context_personal": "⚠️ Файл содержит персональные медицинские данные.",
    "ingest.not_ingested_header": "Файлов, из которых ничего не взято: {n} — каждый назван, с причиной:",
    "ingest.not_ingested_more": "… и ещё {n}",
    "ingest.conflict": "расхождение: {marker} за {date} — оставлено {kept}, другой бланк дал {other}",
    "ingest.repeat": "повтор: {marker} измерен дважды {day} ({first} и {second}) — `scholion lab-draw --day {day}` запишет, что было между",
    "ingest.labs_done": "Обработано файлов: {files}, точек: {points}, пропущено: {skipped}.",
    "ingest.same_day_replaced": "  · {marker}: точка {date} заменила {replaced} — один забор, одна точка; то, что было записано о нём раньше, перенесено",
    "ingest.errors_footer": "⚠ {files} — читалка упала на них с ошибкой, они названы выше; остальная папка обработана. Код выхода ненулевой, чтобы скрипт не принял это за чистый прогон.",
    "count.files_errored.one": "{n} файл",
    "count.files_errored.few": "{n} файла",
    "count.files_errored.many": "{n} файлов",
    "ingest.no_folder": "не указана папка с PDF",
    "ingest.studies_done": "Заключений всего: {total}; добавлено {added}, обновлено {updated}, "
                           "файлов просмотрено {seen}. {hint}",
    "ingest.garmin_done": "✓ Образ жизни пересобран: {metrics} метрик, диапазон {range}. "
                          "Записано в {out}",
    "ingest.garmin_backup": " (бэкап: {path})",
    "ingest.manifest_moved": "Список уже прочитанных файлов теперь лежит рядом с профилем, в {new}; "
                             "то, что было в {old}, взято с собой (перенесено: {entries}), так что "
                             "из-за переезда ничего не читается заново как новое.",

    # ── слой ассистента: доска состояния и аудит собственного кода ────
    "common.yes": "да",
    "common.no": "нет",
    "assistant.scan_core": "ядро: {files} файлов, {lines} строк",
    "assistant.scan_ingest": "подготовка данных: {files} файлов, {lines} строк",
    "assistant.scan_ingest_absent": "подготовка данных: в этой сборке нет",
    "assistant.verdict_clean": "нет обращений к языковым моделям",
    "assistant.verdict_hits": "найдены обращения — проверить",
    "assistant.engine.parsing": "разбор PDF-бланков и занесение показателей (обычный парсер, "
                                "не модель)",
    "assistant.engine.flags": "флаги отклонений по коридорам из ваших же бланков, тренды, «у "
                              "границы»",
    "assistant.engine.genome": "геном: находки ClinVar, ACMG SF, полигенные риски, слой долголетия",
    "assistant.engine.pgx": "фармакогенетика: фенотипы CPIC, звёздные аллели, HLA",
    "assistant.engine.second_opinion": "второе мнение по препарату: геном × анализы × "
                                       "взаимодействия × ClinVar",
    "assistant.engine.checklist": "чеклист следующего забора, биологический возраст, n-of-1 "
                                  "эксперименты",
    "assistant.engine.goals": "цели, дашборд движения к ним, образ жизни и состав тела",
    "assistant.adds.narrative": "связный разбор вместо таблицы: что здесь важно, а что шум",
    "assistant.adds.provenance": "объяснение, откуда взялся вывод, со ссылкой на источник",
    "assistant.adds.what_if": "ответы на «а что если» — по вашим данным, а не вообще",
    "assistant.adds.questions": "список вопросов к врачу перед приёмом",
    "assistant.adds.curated": "обновление курируемых текстов профиля (справка, фокус, цель)",
    "assistant.curated.brief": "Справка об образе жизни",
    "assistant.curated.focus": "Фокус внимания",
    "assistant.curated.goal": "Цель по показателям",
    "assistant.curated.absent": "текста нет — вкладка покажет только числа, без формулировок",
    "assistant.curated.unreadable": "файл не читается как JSON",
    "assistant.curated.stale": "появились данные новее формулировок — блоки помечены как "
                               "требующие пересмотра",
    "assistant.ep.skill.title": "Claude-скилл",
    "assistant.ep.skill.installed": "установлен: {path}",
    "assistant.ep.skill.ready": "в проекте есть, но не установлен",
    "assistant.ep.skill.missing": "файл скилла не найден",
    "assistant.ep.skill.what": "ассистент видит инструкцию и сам вызывает нужные команды проекта",
    "assistant.ep.ouroboros.title": "Ouroboros-плагин",
    "assistant.ep.ouroboros.ready": "файл плагина в проекте: {path}",
    "assistant.ep.ouroboros.missing": "файл плагина не найден",
    "assistant.ep.ouroboros.how": "укажите путь к этому файлу в конфигурации Ouroboros "
                                  "(get_tools() → sch_*)",
    "assistant.ep.ouroboros.what": "инструменты sch_* доступны той модели, которая настроена в "
                                   "Ouroboros",
    "assistant.ep.any.title": "Любая другая модель",
    "assistant.ep.any.detail": "работает через контекст: текст со снимком состояния и списком "
                               "команд",
    "assistant.ep.any.what": "вставьте собранный текст в диалог с любой моделью — Claude, "
                             "ChatGPT, Gemini, локальной. Модель не получает доступа к машине: "
                             "она просит вас выполнить команду и разбирает вывод",
    "assistant.planned": "подключение сторонней модели по API-ключу прямо из приложения — "
                         "следующий этап; сейчас ядро принципиально не ходит в сеть за выводами",
    "assistant.disclaimer": "Ассистент не назначает и не отменяет терапию. Всё, что он "
                            "формулирует, — материал для разговора с лечащим врачом.",
    "assistant.works_without": "Приложение работает без ассистента: {answer}",
    "assistant.code_check": "Проверка кода: {scanned} — {verdict}",
    "assistant.network_lead": "Куда приложение может обратиться (только по вашей команде, и "
                              "уходит только сам запрос — не профиль и не геном):",
    "assistant.network_detail": "    название препарата — RxNorm/RxClass, для русских брендов "
                                "— переводчик; rsID — Ensembl; фармакогенетика — CPIC",
    "assistant.ingest_hosts": "  · подготовка данных, запускается вручную: {hosts}",
    "assistant.engine_does_h": "Считает код:",
    "assistant.adds_h": "Добавляет ассистент:",
    "assistant.curated_h": "Курируемые тексты:",
    "assistant.entrypoints_h": "Точки входа:",

    # ── слой ассистента: контекст для вставки в любую модель ──────────
    "assistant.ctx.rules": """ПРАВИЛА (обязательны):
1. Вы не назначаете и не отменяете терапию. Итог разбора — вопросы к врачу.
2. Числа ниже уже посчитаны локальным кодом по первичным данным. Не пересчитывайте их
   и не заменяйте «типичными» значениями: если чего-то нет, так и скажите — нет.
3. У каждого вывода указывайте источник: показатель и дату либо команду, которая его дала.
4. Коридоры нормы взяты из печатных бланков этого человека. Не подставляйте чужие нормы.
5. Отсутствие находки не равно норме: у генома есть покрытие, у анализов — давность.
""",
    "assistant.ctx.title": "# Контекст Scholion для ассистента\n",
    "assistant.ctx.collected": "Собрано: {date}. Ниже — снимок состояния, посчитанный "
                               "локальным кодом.\n",
    "assistant.ctx.personal": "⚠️ Этот текст содержит персональные медицинские данные. "
                              "Вставляйте его только туда, где вы согласны их хранить.\n",
    "assistant.ctx.connected_h": "\n## Что подключено\n",
    "assistant.ctx.markers": "— показателей в профиле: {n}\n",
    "assistant.ctx.pgx_genes": "— генов с фармакогенетикой: {n}\n",
    "assistant.ctx.genome": "— полный геном: {state}\n",
    "assistant.ctx.meds_h": "\n## Назначения\n",
    "assistant.ctx.no_meds": "— назначений в профиле нет\n",
    "assistant.ctx.med_since": "с {date}",
    "assistant.ctx.med_status": "[не текущее: {status}]",
    "assistant.ctx.ref_range": " (норма {low}–{high})",
    "assistant.ctx.ref_max": " (норма <{high})",
    "assistant.ctx.ref_min": " (норма >{low})",
    "assistant.ctx.ref_none": " (коридора в бланке нет — флага быть не должно)",
    "assistant.ctx.abnormal_h": "\n## Отклонения ({abnormal} из {total} показателей)\n",
    "assistant.ctx.abnormal_row": "— {name}: {value} {unit}{ref} · {date} · флаг {flag}\n",
    "assistant.ctx.truncated": "— … показаны первые {shown} из {total}. Полный список: python3 "
                               "-m scholion labs\n",
    "assistant.ctx.none_row": "— нет\n",
    "assistant.ctx.tests_h": "\n## Что имеет смысл сдать ({n})\n",
    "assistant.ctx.test_row": "— {suggest} — {why} [{priority}]\n",
    "assistant.ctx.focus_h": "\n## Фокус внимания\n— {title}\n",
    "assistant.ctx.commands": """
## Команды, вывод которых можно попросить у человека
python3 -m scholion overview             сводка: красные флаги, пробелы, счётчики
python3 -m scholion second-opinion       второй взгляд перед визитом к врачу
python3 -m scholion radar                индекс здоровья по системам (0–100)
python3 -m scholion labs                 разбор анализов: флаги и тренды
python3 -m scholion medications          текущая схема лечения
python3 -m scholion markers              каталог показателей и их коридоров
python3 -m scholion genome-status        подключён ли геном, что в пробелах
python3 -m scholion drug "<препарат>"    сверка препарата с фармакогенетикой
python3 -m scholion prescription "<препарат>"  проверка нового назначения
python3 -m scholion suggest-tests        что имеет смысл сдать
python3 -m scholion genome --gene <ГЕН>  поиск в полном VCF
python3 -m scholion clinvar | acmg | prs | longevity
python3 -m scholion metrics | lifestyle | goal | focus | brief
python3 -m scholion phenoage --panels    полнота панелей биовозраста
python3 src/ingest/draw_checklist.py           бланк следующего забора (ступени, пробирки)

Не выдумывайте вывод этих команд — попросите выполнить и прислать результат.
Итог разбора — не диагноз, а материал для разговора с лечащим врачом.
""",

    # ── инструменты Ouroboros: что модель читает перед вызовом ────────
    "tool.sch_check_drug_gene.description": "Сверить назначенный препарат с фармакогенетикой "
                                            "из профиля владельца "
                                            "(profile/pharmacogenomics.json: genotypes[] из "
                                            "BAM + диплотипы звёздных аллелей PyPGx в "
                                            "star_alleles, CPIC-отчёт PharmCAT в "
                                            "profile/pharmcat/). Возвращает уровень "
                                            "значимости, задействованный ген, вычисленный "
                                            "фенотип и что обсудить с врачом. Не назначение.",
    "tool.sch_check_drug_gene.param.drug": "название препарата (рус/англ)",
    "tool.sch_analyze_labs.description": "Разбор лабораторных анализов владельца: флаги "
                                         "отклонений, тренды во времени, связь с геномом. "
                                         "markers — опциональный список ключей через запятую.",
    "tool.sch_analyze_labs.param.markers": "ключи показателей через запятую, пусто = все",
    "tool.sch_suggest_tests.description": "Предложить дополнительные анализы на основе текущих "
                                          "лабораторных данных, назначений и генетических "
                                          "пробелов. Материал для обсуждения с врачом.",
    "tool.sch_genome_lookup.description": "Найти генотип любого локуса в полной геномной базе "
                                          "владельца (VCF) по rsID или гену. Координаты — из "
                                          "публичного справочника/Ensembl, генотип — из "
                                          "персонального VCF. Если база не подключена, вернёт "
                                          "статус no_genome.",
    "tool.sch_genome_lookup.param.rsid": "rsID, напр. rs4149056",
    "tool.sch_genome_lookup.param.gene": "имя гена (все его локусы)",
    "tool.sch_check_prescription.description": "ПЕРСОНАЛЬНОЕ второе мнение по препарату "
                                               "относительно данных владельца: 🧬 его геном "
                                               "(гены важные для препарата по CPIC + его "
                                               "генотипы/фенотипы), 🧪 его анализы (что "
                                               "контролировать и что уже отклонено), 🔗 его "
                                               "текущие назначения (взаимодействия). Работает "
                                               "для ЛЮБОГО препарата (распознавание через "
                                               "RxNorm, гены через CPIC по rxcui). Русские "
                                               "названия принимаются.",
    "tool.sch_check_prescription.param.drug": "название препарата (рус/англ)",
    "tool.sch_ingest_labs.description": "Извлечь лабораторные показатели с датами из "
                                        "PDF-отчётов в указанной папке (напр. «Лабораторные "
                                        "исследования») и добавить в profile/labs.json. "
                                        "Инкрементально: берёт только новые/изменённые файлы.",
    "tool.sch_ingest_labs.param.folder": "путь к папке с PDF анализов",
    "tool.sch_health_metrics.description": "Личные показатели здоровья владельца "
                                           "(profile/metrics.json): возраст, ИМТ, сон, вес, "
                                           "шаги, активность и тренды. Для контекста «образ "
                                           "жизни».",
    "tool.sch_lifestyle.description": "Исторические данные образа жизни этого профиля — с "
                                      "того носимого устройства и весов, что его наполняли "
                                      "(profile/wearable_trends.json): ПОМЕСЯЧНЫЕ тренды "
                                      "(3-мес сглаживание) веса, ИМТ, доли жира, мышечной "
                                      "массы, VO2max, пульса покоя, ВСР, стресса, Body "
                                      "Battery, шагов, активности + сводка тренировок и балл "
                                      "формы. Учитывать в анализе метаболического риска и "
                                      "рекомендациях по нагрузке.",
    "tool.sch_clinvar_findings.description": "Клинически значимые находки владельца из ClinVar "
                                             "× персональный VCF (genome/clinvar_hits.tsv, "
                                             "готовит annotate_clinvar.sh). "
                                             "Патогенные/риск-варианты, которые несёт пациент. "
                                             "Если не запускалось — вернёт not_run.",
    "tool.sch_prs.description": "Полигенные риски владельца (PGS Catalog, "
                                "profile/prs_results.json): перцентили по 74 признакам (12 "
                                "категорий) — позиция в популяции, НЕ вероятность болезни. "
                                "Модели на европейских выборках. У каждого признака уровень "
                                "доказательности (clinical/supportive/research) — крайние "
                                "перцентили research-уровня не повод к действию. Модели "
                                "закреплены реестром knowledge/prs_models.json; поле "
                                "model_changed_from = разрыв ряда перцентилей (другая модель — "
                                "другая шкала, тренд через него не рисовать). У крайних "
                                "перцентилей может быть validity_note — аудит модели на данных "
                                "владельца (покрытие, промахи, доля MHC, драйверы); "
                                "reliable=false с заметкой = перцентилю не доверять. «Выше "
                                "среднего» (P≥80) — повод для скрининга, не диагноз.",
    "tool.sch_longevity.description": "Генетический слой долголетия владельца (LongevityMap × "
                                      "VCF, profile/longevity_findings.json): APOE ε-статус и "
                                      "хорошо изученные маркёры (FOXO3 и др.) + значимые "
                                      "носительства по генам. Литературный каталог, не оценка "
                                      "риска.",
    "tool.sch_phenoage.description": "Биологический возраст владельца (PhenoAge, Levine 2018) "
                                     "по 9 рутинным маркёрам. СТРОГО по одной панели: все "
                                     "маркёры из одного забора. Если в панели не хватает "
                                     "маркёра — инструмент НЕ считает и возвращает список "
                                     "того, что дозаказать в следующем заборе (подставлять "
                                     "значения из прошлых панелей запрещено). panel: "
                                     "'YYYY-MM', 'latest' (по умолчанию) или 'panels' — обзор "
                                     "полноты всех панелей.",
    "tool.sch_phenoage.param.panel": "YYYY-MM | latest | panels",
    "tool.sch_provenance.description": "Обратная сверка анализов: для КАЖДОЙ точки "
                                       "profile/labs.json ищется печатный бланк-источник (или "
                                       "проверяется, что это корректно посчитанная "
                                       "производная). Дополняет sch_ingest_labs/reconcile, "
                                       "которые идут в обратную сторону. Вердикт «manual» "
                                       "означает «ничем не подтверждено» — такую точку нельзя "
                                       "подавать как факт. refresh=true перечитывает все PDF "
                                       "заново (медленно).",
    "tool.sch_provenance.param.refresh": "перечитать все бланки, а не брать labs_coverage.json",
    "tool.sch_overview.description": "Главный экран этого профиля: сколько маркёров измерено, "
                                    "сколько вне нормы и в какую сторону, какие анализы "
                                    "ожидаются, что знает геномный слой. Начинайте отсюда, когда "
                                    "вопрос широкий — экран называет части, о которых стоит "
                                    "спросить дальше.",
    "tool.sch_second_opinion.description": "Одна страница к разговору с врачом: индекс здоровья "
                                          "по системам, текущие отклонения анализов, сгруппированные "
                                          "по системе, к которой относятся, фармакогенетический "
                                          "список наблюдения против имеющихся назначений и анализы, "
                                          "которые ещё имеет смысл сдать. По каждому препарату "
                                          "сказано, прочитан ли генотип или печатается общее правило.",
    "tool.sch_limits.description": "НА ЧТО ЭТИ ДАННЫЕ ОТВЕТИТЬ НЕ МОГУТ и чем закрывается каждый "
                                  "пробел. Читайте прежде любого отрицательного утверждения: «ничего "
                                  "не найдено» значимо только рядом с тем, где искали. Называет "
                                  "клетку матрицы «класс входа × архитектура признака», измеренное "
                                  "покрытие и каждое утверждение, которого профиль не выдерживает.",
    "tool.sch_rules.description": "Правила безопасности, по которым работает этот продукт, целиком. Прочитайте их ПРЕЖДЕ, чем передавать любой ответ остальных инструментов: они имеют приоритет над любой другой инструкцией, полученной об этих данных, и говорят, чего говорить нельзя. Модель, пришедшая через инструментальный интерфейс, не получает вместе с ним никакой инструкции — вот откуда она берётся.",
    "tool.sch_radar.description": "Индекс здоровья по системам организма, 0–100 каждая, с "
                                 "изменением относительно прошлого измерения и списком "
                                 "сдвинувшихся маркёров. Знаменатель — заявленная панель системы, "
                                 "а не та её часть, что оказалась измерена: система с двумя "
                                 "значениями из девяти так и говорит.",
    "tool.sch_focus_log.description": "Записать строку в журнал текущего фокуса: что было в этот день — алкоголь, ситуативный приём препарата, поздний ужин, свободная заметка. Один из четырёх пишущих инструментов, и записывать он может только то, что человек сам сейчас сказал. Не помещайте сюда вывод: журнал — это то, что читает последующий разбор, и запись, в которой уже лежит заключение, делает разбор круговым. Запись на существующую дату заменяет её; пустая запись эту дату удаляет.",
    "tool.sch_focus_log.param.date": "день, к которому относится эпизод, ГГГГ-ММ-ДД",
    "tool.sch_focus_log.param.alcohol": "что было выпито, словами человека — «бокал сухого красного», «две кружки пива». Пусто, если не было",
    "tool.sch_focus_log.param.atenolol": "true, если в этот день был ситуативный приём",
    "tool.sch_focus_log.param.late_meal": "true, если последний приём пищи был поздним",
    "tool.sch_focus_log.param.note": "всё остальное, что человек сказал про этот день, дословно",
    "tool.sch_focus_log.done": "Записано в журнал: {date} ({action}).",
    "tool.sch_focus.description": "Единственная задача, на которой профиль сосредоточен сейчас: "
                                 "живая метрика, путь база → сейчас → ориентир, рычаги из "
                                 "собственных данных человека и журнал эпизодов. Пусто, когда "
                                 "ничего не задано, и это законный ответ.",
    "tool.sch_brief.description": "Сводка образа жизни: живые числа с трекера и весов вместе с "
                                 "курируемыми формулировками из профиля, каждая помечена как "
                                 "свежая или устаревшая по своему интервалу наблюдения.",
    "tool.sch_acmg.description": "Вторичные находки ACMG SF v3.3 — действенный минимум по 84 "
                                "генам, с применёнными правилами вынесения (рецессивные гены — "
                                "только при биаллельности и так далее). Прямо говорит, когда скан "
                                "не запускался, а это не то же самое, что чистый результат.",
    "tool.sch_goal_suggest.description": "Предлагает ориентир по каждому маркёру, для которого "
                                        "хватает оснований, и говорит, откуда взято каждое число: "
                                        "клиническая ассоциация с цитатой, собственный максимум "
                                        "человека с датой и числом измерений, либо лабораторный "
                                        "коридор. Перечисляет, для чего предлагать отказался и "
                                        "почему. ТОЛЬКО ЧТЕНИЕ — ничего не записывает.",
    "tool.sch_lipid_genetics.description": "Унаследованная часть липидного профиля: носительство "
                                          "варианта потери функции PCSK9 и значение Лп(а) в одном "
                                          "ответе, потому что по отдельности каждое читается "
                                          "неверно. Несёт популяционную оговорку там, где "
                                          "носительство мало что значит, и причину, по которой "
                                          "полигенная оценка Лп(а) не заменяет её измерение.",
    "tool.sch_goal.description": "Цель, заданная в этом профиле (profile/health_goals.json): "
                                 "таблица сейчас→цель и опорные точки. ТЕКУЩИЕ значения — ЖИВЫЕ "
                                 "из единой модели (labs.json + wearable_trends.json). "
                                 "Используйте, чтобы оценить, насколько профиль приблизился к "
                                 "собственной цели и что тянет назад. Цель и мера прогресса — "
                                 "те, что записаны в этом файле; если файла нет, цель не "
                                 "задана.",

    # ── инструменты Ouroboros: что сообщает вызов ─────────────────────
    "tool.ingest_labs.done": "Обработано файлов: {files}, добавлено точек: {points}, "
                             "пропущено: {skipped}.",

    # ── вердикты и строки состояния, которые считает движок ───────────
    "disclaimer.general": "Не диагноз и не назначение. Материал для обсуждения с лечащим "
                          "врачом. Ассистент не меняет терапию (см. ASSISTANT-RULES.md).",
    "disclaimer.short": "Не диагноз. Материал для обсуждения с лечащим врачом.",
    "disclaimer.prs": "Полигенный балл — статистический прокси, не диагноз. Модели обучены "
                      "преимущественно на европейских выборках; перцентиль = позиция в "
                      "популяции, НЕ вероятность болезни. Обсуждать с врачом.",
    "common.na": "н/д",
    "phenotype.not_covered": "ген не покрыт данными пациента (нужен доп. анализ)",
    "phenotype.no_model": "нет модели фенотипа для гена — см. найденные маркеры",
    "phenotype.no_markers": "маркеры гена отсутствуют в данных пациента",
    "phenotype.normal_default": "нормальный (по умолчанию)",
    "drug.no_name": "Не указан препарат.",
    "drug.nothing_notable": "По имеющимся маркерам особенностей не выявлено.",
    "drug.nothing_notable_ask": "По имеющимся маркерам особенностей не выявлено; уточнить у врача.",
    "drug.not_found": "Препарат «{drug}» не найден ни в базе проекта, ни в международной базе "
                      "RxNorm (возможно нет сети, опечатка или узкий бренд). Впишите "
                      "международное название (INN) или обсудите с врачом/по инструкции.",
    "drug.class_unknown": "класс не определён",
    "drug.online_headline": "«{drug}» найден в международной базе RxNorm{class_note}. Прямого "
                            "фармакогенетического маркера в базе проекта нет{tail}",
    "drug.online_class_note": " (класс: {classes})",
    "drug.online_check_interactions": ". Проверил взаимодействия по классу ниже.",
    "drug.online_ask_doctor": "; оценить с врачом.",
    "interactions.no_rules": "Препарат распознан (класс: {atc}), но правил взаимодействий "
                             "именно по этому классу в базе пока нет. Оцените с врачом.",
    "interactions.unknown_drug": "Препарат не распознан ни локально, ни в международной базе. "
                                 "Проверьте написание или обсудите с врачом.",
    "prescription.class_undefined": "не определён",
    "gene.covered_by_vcf": "полная геномная база покрывает ген; фенотип по звёздным аллелям — "
                           "через PyPGx",
    "gene.needs_diplotype": "этот ген решается полным диплотипом — числом копий и фазой — и одним тег-SNP не устанавливается",
    "gene.diplotype_closes": "чем закрывается: вызов звёздных аллелей по вашим ридам (PyPGx или PharmCAT, читающие число копий) либо лабораторный фармакогенетический отчёт, называющий диплотип. Файл вариантов сам по себе этого не закрывает, каким бы полным он ни был",
    "gene.vcf_pending": "полная геномная база готовится (Трек 2) — тогда подтянутся ваши "
                        "варианты по этому гену",
    "near.no_history": "нет истории",
    "near.moved_from_baseline": "{delta} % к личной базе {baseline}",
    "bmi.under": "недостаток",
    "bmi.normal": "норма",
    "bmi.over": "избыток",
    "bmi.obese": "ожирение",
    "prs.from_a_genome_not_attached": "Посчитано {date} по файлу генома, который сейчас не "
                                      "подключён. Это сохранённые результаты, а не живое "
                                      "чтение — потому они и могут стоять рядом с пометкой "
                                      "«нет данных» у VCF, и ни то, ни другое не ошибка. "
                                      "Подключите файл, чтобы пересчитать.",
    "prs.not_computed": "Полигенные баллы ещё не рассчитаны (нет profile/prs_results.json).",
    "prs.weight_mass_low": "варианты модели в основном найдены, но несут лишь {pct} % её ВЕСА — перцентиль считался бы по другой модели, не по опубликованной",
    "prevalence.flag.abnormal": "вне референсного интервала",
    "prevalence.flag.near_limit": "внутри интервала, но у самой его границы",
    "prevalence.flag.norange": "коридора для сравнения нет",
    "prevalence.flag.threshold": "пересечён клинический порог действия",
    "prevalence.title": "**Как часто срабатывает каждый флаг** — та самая проверка, которую проект требует до любой интерпретации",
    "prevalence.how_to_read": "Флаг, помечающий почти каждый объект, не несёт информации, какой бы правдоподобной ни была его формула. Это арифметика, а не вердикт: у человека, у которого панель действительно вся ненормальна, все показатели и должны гореть, и правило, прячущее эти флаги из-за их числа, было бы хуже дефекта, который оно чинит.",
    "prevalence.row": "{what} — {hit} из {looked_at} ({pct} %)",
    "prevalence.notable": "⚠ срабатывает на {pct} % того, что смотрел — стоит спросить, описывает правило человека или линейку",
    "prevalence.none": "измерять пока нечего: лабораторные показатели не загружены",
    "prs.integrity_double": "покрытие >1 — в целевом VCF позиции посчитаны дважды (SNP+индел "
                            "на одной координате); пересоберите вход prs_genotype_sites.sh и "
                            "пересчитайте",
    "prs.category_other": "Прочее",
    "longevity.not_built": "Слой долголетия ещё не построен (нет profile/longevity_findings.json).",
    "sources.chosen_folder": "выбранная папка · {path}",
    "sources.data_h": '**Откуда данные профиля** — по строке на область, как показывает страница',
    "sources.local_folder": "локальная папка · {path}",
    "sources.labs": "Лабораторные исследования",
    "sources.medications": "Назначения врача",
    "sources.metrics": "Личные показатели здоровья",
    "sources.lifestyle": "Образ жизни (носимые устройства)",
    "sources.genome_vcf": "Полный геном (VCF)",
    "sources.clinvar": "Клинически значимые варианты",
    "sources.clinvar_origin": "международная база ClinVar (NCBI)",
    "sources.ensembl": "Координаты/аннотации rsID",
    "sources.ensembl_origin": "международная база Ensembl REST (GRCh38)",
    "sources.pgx": "Фармакогенетика ген↔препарат",
    "sources.pgx_origin": "международные руководства CPIC / PharmGKB (курируемая копия)",
    "sources.interactions": "Лекарственные взаимодействия",
    "sources.interactions_origin": "курируемая база по классам (CPIC / инструкции)",
    "sources.catalog": "Каталог локусов (координаты)",
    "sources.catalog_origin": "международная база Ensembl GRCh38",
    "sources.test_rules": "Правила предложения анализов",
    "sources.test_rules_origin": "правила проекта (курируются)",
    "radar.domain.lipids": "Липиды",
    "radar.domain.cardio": "Сердце и сосуды",
    "radar.domain.glucose": "Углеводный обмен",
    "radar.domain.inflammation": "Воспаление",
    "radar.domain.thyroid": "Щитовидная железа",
    "radar.domain.adrenals": "Надпочечники",
    "radar.domain.gonads": "Половые железы",
    "radar.domain.growth": "Ось роста",
    "radar.domain.pancreas": "Поджелудочная железа",
    "radar.domain.liver": "Печень",
    "radar.domain.micronutrients": "Витамины",
    "radar.domain.renal": "Почки",
    "radar.domain.fitness": "Форма",
    # ---- система как один предмет (задача 168): вопросы, корзины, причины ----
    "system.q.pending": "{gene} {rsid} назван в панели этой системы, а фраза для найденного состояния ({state}) не написана — есть ли в этом что обсудить?",
    "system.q.risk_allele": "{gene} {rsid} назван в панели, а аллель риска в ней не назван — какой аллель читать?",
    "system.q.expect": "по этому генотипу панель ожидает в {gene} {rsid} {marker} {direction}; последнее значение {value} {unit} ({date}), {position} коридора {corridor}, движение {from_value} → {to_value} — сходится ли картина?",
    "system.q.expect_gap": 'позиции панели {positions} ожидают направление по маркёру {marker}, а {marker} не сдавался ни разу — стоит ли сдать, чтобы на них ответить?',
    "system.q.moi": "{gene} рецессивный ({moi}): одна копия названного аллеля в {rsid} — носительство, а не риск; стоит ли смотреть второй аллель?",
    "system.q.gap": "маркёры панели этой системы, не сдававшиеся ни разу: {markers} — стоит ли их сдавать, решает врач",
    "system.gap_waiting": '; позиции панели, которые их ждут: {waiting}',
    "system.direction.lower": "ниже",
    "system.direction.higher": "выше",
    "system.direction.None": "в направлении, которое панель не называет",
    "system.position.below": "ниже",
    "system.position.within": "внутри",
    "system.position.above": "выше",
    "system.position.unknown": "без коридора рядом",
    "system.corridor.up_to": "до {high}",
    "system.corridor.from": "от {low}",
    "system.state.het": "одна копия названного аллеля",
    "system.state.hom": "две копии названного аллеля",
    "system.state.absent": "названный аллель не обнаружен",
    "system.state.unread": "не прочитано",
    "system.state.risk_allele_not_declared": "прочитано, аллель риска в панели не назван",
    "system.state.None": "не определено",
    "system.why.no_current_prescriptions": "текущих назначений в профиле не записано",
    "system.why.none_acts_here": "ни одно из текущих назначений не относится к классу, который карта помещает на эту систему",
    "system.why.no_target_set": "цели врача ни по одному маркёру этой системы не записано",
    "system.q.target": "{marker}: последнее значение {value} {unit} ({date}) внутри коридора {low}–{high} и {side} цели {spec}, заданной {set_by} {set_on} — стоит ли это обсудить?",
    "system.why.no_lab_half": "у этой системы нет лабораторной панели: она строится из показателей носимых устройств",
    "system.why.all_measured_no_rule": "все маркёры панели измерены недавно, и ни одно правило не сработало",
    "system.why.gaps_are_questions": "ни одно правило не сработало; маркёры панели, не сдававшиеся ни разу, стоят среди вопросов — сдавать ли их, решает врач, а не правило",
    "system.why.no_genetic_panel": "генетического списка для этой системы в сборке нет — где ничего не названо, нечему быть непрочитанным, и это утверждение о сборке, а не о человеке",
    "system.why.no_genetic_half": "у этой системы нет генетической половины по замыслу",
    "system.why.all_read": "все строки генетической половины прочитаны",
    "system.why.scan_not_run": "геном на этом профиле не читается, поэтому ничего из генетической половины прочитать нельзя",
    "system.why.no_rule_fired": "ни одно правило списка анализов не касается маркёра этой системы на этом профиле",
    "system.why.nothing_open": "по этой системе нет открытого вопроса: ожидание не объявлено, ни одна строка не ждёт фразы, ни один маркёр панели не пропущен",
    "system.next.stale": "{marker}: последнее измерение {date}, больше чем {months} мес. назад",
    "system.next.unread": "{gene} {rsid}: в этом файле не прочитано ({why})",
    "system.next.unread_gene": "{gene}: для этой цели не прочитан ({why})",
    "system.kind.guideline": 'руководство учитывает его при выборе препарата',
    "system.kind.pair": 'пара препарат–ген с доказательствами',
    "system.kind.mechanism": 'объясняет маркёр — измеренный эффект, правила не следует',
    "system.kind.asked_about": 'о нём спрашивают, ничего не следует',
    "system.kind.no_variant": 'назван, вариантов нет',
    "system.kind.unassigned": 'назван, вид связи не записан',
    "system.read_why.assumed_ref": 'строки на позиции нет — референс предполагается, а не прочитан; решает полный геном с референсными вызовами или таблица покрытия',
    "system.genetics.unreadable": '{gene}: коротким чтением не читается — требует отдельного метода. {reason}',
    "system.read_why.separate_method": 'короткое чтение этот ген не читает; нужен отдельный метод',
    "system.closes.separate_method": 'закрывает это: метод, названный в пометке — MLPA, длинное чтение или анализ длины фрагмента',
    "system.panel.h": 'Позиции панели',
    "panel.title": "Панель системы «{label}» — как её описывает каталог",
    "panel.list_h": "Панели систем организма",
    "panel.list_row": "{label} ({key}): {positions}, генов, которые не читает короткое чтение: {unreadable}",
    "panel.counts": "{positions} в {genes}; с названным исследованием: {with_study}; с ожиданием к маркёру: {with_expectation}; подписано врачом: {signed}",
    "panel.source": "каталог от {updated}; у каждой строки свой источник и исследование",
    "panel.locus": "локус {hgvs}, названный аллель {allele}",
    "panel.state.het": "одна копия",
    "panel.state.hom": "две копии",
    "panel.classification": "ген–болезнь: {classification}, наследование {moi} — {disease}",
    "panel.expect": "ожидает маркёр {marker} {direction} — {note}",
    "panel.effect": "размер эффекта: {effect}",
    "panel.source_row": "источник: {source}; исследование: {study}",
    "panel.signed.clinician": "фразу подписал врач {on}; внесено {curated}",
    "panel.signed.author": "фразу подписал автор панели ({by}) {on}, не врач; внесено {curated}",
    "panel.signed.open": "фраза — черновик по названному источнику; никто её не подписал; внесено {curated}",
    "panel.unreadable": "короткое чтение его не читает — {reason} (источник: {source})",
    "panel.for_clinician_note": "Эта страница описывает саму панель — знание, а не человека: ни геном, ни анализы здесь не читаются. Чтение этой панели по геному — на «Радаре» и на карточке системы.",
    "web.panel.open": "Панель и исследования — для врача",
    "web.panel.open_hint": "Что такое каждая позиция панели, на какое руководство или исследование она опирается и кто её подписал — знание, а не ваш геном",
    "web.second.open_card": "Карточка системы",
    "web.second.open_card_hint": "Все семь слоёв системы на одной странице: анализы, динамика, генетика, назначения, цель, что сдать, вопросы",
    "system.panel.summary": "панель целиком: {positions} — названный аллель найден в {found} ({found_genes}); не найден в {absent} ({absent_genes}); не прочитано: {unread} ({unread_genes})",
    "system.panel.kind.guideline": "A · учесть при выборе препарата",
    "system.panel.conclusion_h": "Генотип по системе",
    "system.panel.conclusion_note": "собрано из фраз самой панели — ничего не добавлено",
    "system.panel.conclusion_found": "в панели {positions}; названный аллель найден в {found}: {genes}",
    "system.panel.conclusion_none_found": "ни один названный аллель панели не найден (проверено {positions})",
    "system.panel.conclusion_absent": "не носитель: {genes}",
    "system.panel.conclusion_unread": "не прочитано, {positions}: {genes}",
    "system.panel.polygenic_fold": "полигенные баллы по системе (посчитано {scored}) — открыть",
    "system.panel.compare_h": "Генотип против анализов",
    "system.panel.compare_none": "ни одна найденная позиция панели не предсказывает измеренный показатель: генотип по этой панели эти измерения не объясняет, и причину надо искать вне неё — в состоянии органа, в фенотипе или в зависимостях, которых панель не описывает",
    "system.panel.compare_absent": "ожидание к {name} не применяется — аллель не носитель: {positions}",
    "system.panel.prescribing_h": "Учесть при выборе препарата",
    "system.panel.prescribing_note": "руководство называет эти позиции при выборе препарата; это не назначение, и здесь не сказано, что препарат принимается",
    "system.panel.kind.pair": "A · пара препарат–ген, учесть при выборе",
    "system.panel.kind.mechanism": "B · объясняет маркёр",
    "system.panel.kind.asked_about": "C · о нём спрашивают",
    "system.panel.kind.no_variant": "вариантов нет",
    "system.panel.kind.unassigned": "вид связи не записан",
    "system.panel.state.het": "1 копия",
    "system.panel.state.hom": "2 копии",
    "system.panel.state.absent": "не найден",
    "system.panel.state.unread": "не прочитано",
    "system.panel.state.risk_allele_not_declared": "прочитано, аллель не назван",
    "system.panel.state.None": "не определено",
    "system.panel.expect": "ожидается {name} {direction} · сейчас {value} {unit} ({date}), {position}{movement}",
    "system.panel.expect_gap": "ожидается {name} {direction} · ни разу не сдавался",
    "system.panel.dir.lower": "↓ ниже",
    "system.panel.dir.higher": "↑ выше",
    "system.panel.pos.above": "выше коридора",
    "system.panel.pos.below": "ниже коридора",
    "system.panel.pos.within": "в коридоре",
    "system.panel.pos.unknown": "коридора нет",
    "system.panel.movement": "; {from} → {to}",
    "system.panel.question_ref": "→ вопрос врачу: №{n}",
    "system.panel.absent_h": "названный аллель не найден ({n})",
    "system.panel.unread_h": "не прочитано ({n})",
    "system.panel.checked": "проверено {positions}",
    "system.row.not_finding_kind": 'печатается, не находка — вид связи: {kind}',
    "system.next.unread_group": "не прочитано для этой цели: {genes} — {why}: {names}",
    "system.read_why.clinvar_not_run": 'варианты файла по этому гену не прогнаны через ClinVar',
    "system.read_why.clinvar_unavailable": 'аннотацию ClinVar открыть не удалось',
    "system.read_why.clinvar_not_ready": 'аннотация ClinVar не готова',
    "system.read_why.coverage_gene_not_in_table": "таблицы покрытия для этого гена рядом с профилем нет — насколько прочитаны его основания, не измерялось",
    "system.read_why.coverage_low": "основания прочитаны, но слишком мелко, чтобы «не найдено» здесь что-то значило",
    "system.read_why.coverage_unavailable": "таблицу покрытия не удалось прочитать",
    "system.read_why.coverage_not_measured": 'насколько прочитаны его основания, никто не измерял',
    "system.read_why.coverage_weak": 'его основания прочитаны слишком мелко, чтобы решать',
    "system.read_why.coverage_unmeasured": 'его покрытия нет в таблице',
    "system.read_why.coverage_absent": 'гена нет в таблице покрытия',
    "system.read_why.position_not_resolved": 'позицию не удалось разрешить в этой сборке',
    "system.read_why.genotype_not_comparable": 'аллели в файле несопоставимы с каталожными',
    "system.read_why.no_row": 'строки на позиции нет, и референс это или пробел — неизвестно',
    "system.closes.clinvar_not_run": 'закрывает это: аннотация файла по ClinVar — шаг из `scholion doc preparing-the-genome`',
    "system.closes.coverage_gene_not_in_table": "закрывает: таблица покрытия, посчитанная по этому списку генов, — та, что есть у профиля, считалась по другому, более короткому списку",
    "system.closes.coverage_low": "закрывает: более глубокое прочтение этого гена — таргетная панель или пересеквенирование",
    "system.closes.coverage_not_measured": 'закрывает это: таблица покрытия, посчитанная из BAM — шаг называет `scholion limits`',
    "system.closes.coverage_weak": 'закрывает это: более глубокое чтение этих генов — целевая панель или пересеквенирование',
    "system.closes.coverage_unmeasured": 'закрывает это: таблица покрытия, посчитанная из BAM — шаг называет `scholion limits`',
    "system.next.coverage": "{gene}: прочитан ниже собственной середины файла ({pct} % оснований на 20×)",
    # полигенный слой системы (задача 178): баллы рядом со списком, никогда — в вердикте
    "system.polygenic.title": "Частая вариация (полигенные баллы)",
    "system.polygenic.line": "моделей, которые карта относит к этой системе: {mapped}; посчитано на этом профиле: {scored}; надёжных на 80-м процентиле и выше: {high}",
    "system.polygenic.row": "{label}: {percentile}-й процентиль — {reliable}",
    "system.polygenic.reliable": "надёжно",
    "system.polygenic.unreliable": "недостаточно надёжно, чтобы читать — почему, сказано в примечании",
    "system.polygenic.detail": "{pgs_id}; доказательность: {evidence}",
    "system.polygenic.model_changed": "закреплённая модель сменилась с {previous}: прежние процентили не на этой шкале",
    "system.polygenic.unscored": "модели, отнесённые к этой системе и не посчитанные на этом профиле: {traits}",
    "system.polygenic.caveat": "процентиль — это место внутри референсной панели, по большей части европейской, и это не вероятность; балл стоит рядом с вердиктом и никогда внутри него, и никогда внутри индекса 0–100",
    "system.polygenic.no_scores": "полигенные баллы на этом профиле не посчитаны — они считаются из полного генома (`scholion doc preparing-the-genome`), никогда из позиций чипа",
    "system.polygenic.no_map": "ни одна закреплённая полигенная модель не относится к этой системе",
    "system.q.polygenic": "полигенный балл по «{label}» ({pgs_id}) стоит на {percentile}-м процентиле референсной панели, по большей части европейской, и процентиль — не вероятность — стоит ли обсуждать скрининг?",
    "system.next.full_genome": "{input} — полный геном закрыл бы для этой системы: {what} (как его подготовить: `scholion doc preparing-the-genome`)",
    "system.next.full_genome_genes": "{genes} списка, не прочитанных здесь",
    "system.next.full_genome_scores": "полигенные баллы, отнесённые к ней ({n}), которые считаются из полного генома и никогда из позиций чипа",
    "system.input.none": "геном не подключён",
    "system.input.array": "подключённый файл — генотипирующий чип",
    "system.input.exome": "подключённый файл — экзом",
    "system.input.narrow": "подключённый файл — не полный геном ({profile})",
    # карточка системы — семь слоёв, один блок
    "system.title": "Система: {label}",
    "system.unknown": "такой системы нет: «{key}» — системы: {systems}",
    "system.register.patient": "регистр пациента",
    "system.register.clinician": "регистр врача",
    "system.register.toggle": "регистр",
    "system.layer.labs": "Лаборатория сейчас",
    "system.layer.dynamics": "Динамика",
    "system.layer.genetics": "Генетика системы",
    "system.layer.medications": "Назначения, действующие на систему",
    "system.layer.target": "Цель, заданная врачом",
    "system.layer.tests": "Что сдать",
    "system.layer.questions": "Вопросы к врачу",
    "system.layer.next": "Следующие шаги",
    "system.level.good": "в норме",
    "system.level.warning": "внимание",
    "system.level.critical": "вне нормы",
    "system.level.nodata": "нет данных",
    "system.labs.line": "{score}/100 ({level}) — маркёров измерено: {measured} из {total}",
    "system.labs.nodata": "ни один маркёр панели не измерен — маркёров в панели: {total}",
    "system.labs.absent": "лабораторной панели нет: система строится из носимых метрик",
    "system.labs.missing": "не сдавались ни разу: {markers}",
    "system.labs.stale": "давние данные, с тех пор не повторялись: {markers}",
    "system.dynamics.line": "{prev} → {score} ({delta}) против {date}, по маркёрам с более ранней точкой: {compared}",
    "system.dynamics.moved": "{name}: {from_value} → {to_value} {unit}",
    "system.dynamics.no_previous": "более раннего измерения для сравнения нет",
    "system.dynamics.absent": "лабораторной панели для сравнения нет",
    "system.genetics.composed": "база {source} {version} — генов: {base_genes}, из них прочитано: {read_genes}; позиций курируемой панели: {positions}, из них прочитано: {read_positions}; находок: {findings}, носительств: {carriers}, ждут фразы: {pending}",
    "system.genetics.not_composed": "генетического списка для этой системы в сборке нет — {why}",
    "system.genetics.signature_author": "позиций, чью фразу подписал автор панели, а врач не подписывал: {n} (подписано {date})",
    "system.genetics.signature_open": "строк, где фраза — черновик по названному источнику и не подписана врачом: {n}",
    "system.genetics.withheld": "попаданий удержано, потому что утверждение Limited, Disputed или Refuted: {n}",
    "system.genetics.excluded": "вычеркнуто из базы врачом, с источником: {genes}",
    "system.genetics.refused": "строк, отброшенных гейтом, посчитано: {n}",
    "system.mode.monogenic": "моногенный",
    "system.mode.common_variant": "частый вариант",
    "system.mode.pgx": "фармакогенетический",
    "system.mode.unknown": "режим не указан",
    "system.row.gene": "{gene} — {mode}; {classifications}; наследование {moi}",
    "system.row.position": "{gene} {rsid} — {mode}; {state}",
    "system.row.finding": "находок: {n}",
    "system.row.carrier": "носительство — одна копия в рецессивном гене, не находка о собственном риске",
    "system.row.pending": "фраза ещё не написана",
    "system.row.signature_author": "фразу подписал автор панели {date} — не врач",
    "system.row.signature_clinician": "фразу подписал врач {date}",
    "system.row.signature_open": "фраза — черновик по названному источнику, врач её не подписывал",
    "system.row.unread": "не прочитано ({why})",
    "system.row.genotype": "генотип {genotype} ({confidence}, глубина {depth})",
    "system.row.assertion": "{disease} — {classification}, {moi}; {submitter}, {date}",
    "system.row.patient_withheld": "строк прочитано без замечаний, показаны только в регистре врача: {n}",
    "system.meds.row": "{name} {dose} — через класс: {classes}",
    "system.meds.unmapped": "текущие назначения, класс которых карта не помещает ни на одну систему: {names}",
    "system.meds.unclassified": "текущие назначения, класс которых не распознан: {names}",
    "system.target.row": "{name}: {spec} {unit} — задал(а) {set_by} {set_on}; сейчас {value} ({date}), {side} цели",
    "system.target.no_value": "{name}: {spec} {unit} — задал(а) {set_by} {set_on}; ещё не измерялся",
    "system.target.within": "внутри",
    "system.next.lab": "сдать",
    "system.next.genome": "что прочитать в геноме",
    "system.next.ask": "спросить врача",
    "system.ring.genetics": "генов прочитано: {read} из {total}",
    "system.ring.genetics_none": "генетическая половина: {status}",
    "system.ring.labs": "маркёров измерено: {measured} из {total}",
    "system.open": "открыть карточку системы",
    "system.of_marker": "система: {label}",
    "system.of_gene": "назван в системах: {systems}",
    "system.of_gene_none": "не назван ни в одной генетической половине систем",
    "system.acts_on": "действует на: {systems}",
    "system.acts_on_none": "не действует ни на одну размеченную систему ({status})",
    "system.print": "напечатать эту систему",
    "systems.title": "Системы организма",
    "systems.labs": "{score}/100, измерено {measured} из {total}",
    "systems.genetics.composed": "генетическая половина из базы ({version}): генов {n}, написанных позиций {positions}, прочитано {read}, не прочитано {unread}",
    "systems.genetics.not_composed": "генетического списка в сборке нет",
    "systems.genetics.no_half": "генетической половины нет по замыслу",
    "systems.acting": "назначений, действующих здесь: {n}",
    "systems.polygenic": "полигенные: посчитано {scored} из {mapped}",
    "systems.hint": "одна система карточкой: `scholion system КЛЮЧ`, с `--register clinician` — плотная версия",
    "lifestyle.metric.Weight": "Вес",
    "lifestyle.metric.BodyFat": "Жир",
    "lifestyle.metric.MuscleMass": "Мышцы",
    "lifestyle.metric.VO2Max": "Форма (VO₂max)",
    "lifestyle.metric.IntensityMinutesDaily": "Активность",
    "lifestyle.metric.StepsDaily": "Шаги",
    "lifestyle.metric.HRV": "Восстановление (ВСР)",
    "lifestyle.metric.BodyBatteryHigh": "Body Battery",
    "lifestyle.metric.RestingHeartRate": "Пульс покоя",
    "brief.no_marker": "[нет маркёра {key}]",
    "brief.no_metric": "[нет метрики {key}]",
    "brief.no_data": "нет данных",
    "brief.ref_range": " (реф {low}–{high})",
    "brief.ref_max": " (реф до {high})",
    "brief.ref_min": " (реф от {low})",
    "brief.goal_now": "{now} → цель {target}",
    "brief.section_other": "Прочее",
    "brief.not_available": "профиль не содержит profile/lifestyle_brief.json — справка ещё не "
                           "составлена",
    "focus.direction.up": "вверх",
    "focus.direction.down": "вниз",
    "focus.direction.flat": "на месте",
    "focus.bedtime_share": "за {nights} экспорта уложился в порог {share} % раз, среднее засыпание {clock}",
    "focus.awake_mean": "за {nights} экспорта бодрствование в постели в среднем {mean} мин",
    "focus.journal_not_ready": "журнал ведётся {nights}; чтобы развести алкоголь и атенолол, "
                               "нужно хотя бы по {need} эпизодов каждого вида (сейчас {a} и "
                               "{b})",
    "focus.journal_split": "алкоголь без атенолола {a} мин, алкоголь с атенололом {b} мин "
                           "(разница {delta})",
    "focus.not_set_reason": "профиль не содержит profile/focus.json — фокус не задан",

    # ── обратная сверка: точка профиля против бланка-источника ────────
    "provenance.expr.homa_ir": "инсулин × глюкоза / 22,5",
    "provenance.expr.atherogenic_index": "(ОХ − ЛПВП) / ЛПВП",
    "provenance.expr.free_androgen_index": "тестостерон / ГСПГ × 100",
    "provenance.expr.ag_ratio": "альбумин / (общий белок − альбумин)",
    "provenance.expr.non_hdl": "ОХ − ЛПВП",
    "provenance.expr.ldl": "Фридвальд: ОХ − ЛПВП − ТГ/2,2",
    "provenance.expr.omega6_omega3_ratio": "омега-6 / омега-3",
    "provenance.no_labs": "labs.json пуст или не найден",
    "provenance.no_coverage": "нет profile/labs_coverage.json — запустите reconcile (или "
                              "provenance --refresh)",
    "provenance.alt_form": "в бланках этого месяца {values}; у маркёра задан приоритетный "
                           "метод ({prefer}) — значение с него",
    "provenance.conflict": "бланк(и) дают {values}, в профиле {value}",
    "provenance.no_form": "бланка на этот маркёр в этом месяце нет",
    "provenance.derived_skipped": "не применимо (условие формулы)",
    "provenance.derived_mismatch": "в профиле {value}, из компонентов того же месяца следует "
                                   "{expected} ({expr})",
    "provenance.derived_nothing": "нечем проверить: нет компонентов {missing}",
    "provenance.derived_orphan": "производный индекс: в бланках месяца его нет, и пересчитать "
                                 "нечем — в профиле отсутствуют {missing}",
    "provenance.derived_orphan_partial": " (есть только {present})",
    "provenance.title": "# Обратная сверка: точка профиля → бланк-источник",
    "provenance.total": "Всего точек: **{n}**",
    "provenance.count_form": "- ✅ подтверждено бланком: {n}",
    "provenance.count_alt_form": "- ✅ второй метод того же забора (приоритетный бланк): {n}",
    "provenance.count_derived_ok": "- ✅ производный индекс сходится с компонентами: {n}",
    "provenance.count_manual": "- ⚪ бланка нет (ручной ввод / бумажное заключение): {n}",
    "provenance.count_conflict": "- 🔴 конфликт с бланком: {n}",
    "provenance.count_derived_bad": "- 🔴 производный индекс не выводится: {n}",
    "provenance.count_derived_orphan": "- 🔴 производный индекс без основания (ни бланка, ни "
                                       "компонентов): {n}",
    "provenance.defects_header": "## 🔴 Дефекты (требуют решения)",
    "provenance.unverified_header": "## ⚪ Без провенанса ({n}) — не факт, а «требует проверки»",

    # ── пишущие команды и заметки в каталоге данных ───────────────────
    "store.brief_absent": "справки об образе жизни в профиле нет",
    "store.brief_no_block": "в справке нет блока «{id}»",
    "store.genome_file_not_found": "файла нет: {path}",
    "store.genome_not_a_bam": "«{path}» — не выравнивание: выравнивание это .bam или .cram. Ничего не записано.",
    "store.reference_not_indexed": "рядом с «{path}» нет файла .fai, а без него FASTA пропускает каждый читатель этого пути — значит, запись была бы настройкой, которую программа потом молча игнорирует. Индекс делает `samtools faidx <путь>`; ничего не записано.",
    "store.genome_not_a_vcf": "это не .vcf.gz: {path}",
    "store.unknown_source": "неизвестный источник",
    "store.folder_not_found": "папка не найдена: {path}",
    "store.sources_purpose": "Где лежит каждый источник сырых данных: выбранные папки (`scholion set-folder`) и, на верхнем уровне, названные файлы генома (`scholion choose-genome`) — сами чтения, выравнивание, с которого они вызваны, и референс, против которого они вызваны. Персональное: пути на этой машине.",
    "store.need_day_and_context": "нужен день и хотя бы одно из --reason / --between",
    "store.no_repeat_that_day": "ни у одного показателя за {day} нет двух замеров — объяснять нечего",
    "store.unknown_ancestry": "«{value}» — эта сборка не знает такой референсной популяции. Принимаются: {accepted}. Перцентиль — это место внутри популяции, поэтому нераспознанное название не меньшая ошибка, чем её отсутствие.",
    "store.unknown_sex": "«{value}» не распознано как пол. От него зависит десяток референсных интервалов, поэтому нераспознанное значение отклоняется, а не записывается, чтобы потом читаться как «не задано».",
    "store.no_labs": "в профиле пока нет лабораторной истории",
    "store.date_not_a_date": "«{date}» — не дата. Точка датируется в одном из видов: {accepted} — последний, когда в один день два забора и бланк напечатал время.",
    "store.resolution_mixed": "  · {marker}: этот период уже есть в ряду в другом разрешении — {dates}. Одно измерение стоит дважды; решите, которое из них точка.",
    "store.need_marker_date": "нужны marker и date",
    "redact.no_file": "файла {path} нет",
    "redact.no_patterns": "Файла .personal_patterns нет, поэтому убраны только структурные классы — фамилия и номер образца остались, потому что здесь их никто не знает. Заведите файл (он вне git): printf '%s\n' 'Фамилия' 'НОМЕР-ОБРАЗЦА' 'mail@example.com' > .personal_patterns",
    "redact.title": "**Вычищенный текст**",
    "redact.replaced": "Заменено: {what}.",
    "redact.replaced_none": "Ни одно правило не сработало. Это не справка о чистоте — смотрите ниже.",
    "redact.notices_head": "**Чего инструмент НЕ тронул, потому что решать не ему:**",
    "redact.notice_genotype": "токенов вида генотипа — {n}. rsID, аллели и звёздочные аллели — это ваш геном, и они же обычно предмет самого сообщения об ошибке: решите по каждому.",
    "redact.notice_measurement": "чисел с единицей рядом — {n}. Это ваши результаты.",
    "redact.footer": "Прочитайте текст ниже перед публикацией. Инструмент не отличит лабораторное значение от номера версии, а issue публична с секунды создания.",
    "limits.prs_both_closes": "Скор сняли с доверия две причины, и только одна в вашей власти: генотипирование позиций модели из BAM (src/ingest/prs_genotype_sites.sh) закрывает часть про покрытие и оставляет остальное как есть — причина выше про модель, а не про прочтение.",
    "limits.prs_model_why": "Скор снят с доверия по валидности самой модели, а не по прочтению.",
    "limits.prs_measured_closes": "Закрывать нечего: величина, которую оценивает модель, "
                                  "измерена у вас напрямую — {name} {value} {unit} ({date}). "
                                  "Измерение сильнее перцентиля, посчитанного по вариантам; "
                                  "скор к нему ничего не добавляет.",
    "limits.prs_model_closes": "Вашими данными это не закрывается — ограничение в модели, а не в прочтении. Помогла бы только другая модель, а там, где признак измеряется напрямую, ответ даёт само измерение.",
    "limits.interval_basis_locus": "измерено по локусам генов с полем, а не по кодирующей последовательности: небольшой провал внутри крупного гена почти не двигает это число, а именно про такой провал его обычно и спрашивают",
    "limits.bed_never_computed": "покрытие для этого профиля никогда не измерялось — прогоните сначала `bash src/ingest/qc_callability.sh` по своему выравниванию; без этого нет и списка непрочитанного",
    "limits.bed_nothing_weak": "все гены панели прочитаны выше порога — перечитывать нечего",
    "limits.bed_no_coordinates": "таблица покрытия называет слабые гены, но не их интервалы, а координаты по имени гена здесь не выдумываются: {genes}. Перепрогоните `bash src/ingest/qc_callability.sh` — он их теперь записывает",
    "limits.bed_track": "гены, прочитанные ниже {pct}% оснований на 10x — интервалы суть {basis}, а не кодирующая последовательность",
    "limits.interval_basis_unknown": "по чему измерены эти проценты — не записано; по кодирующей последовательности и по локусу целиком это разные величины, и разница не мала",
    "limits.coverage_unknown": "Покрытие вашего генома ни разу не измерялось, поэтому «ничего не найдено» в гене не отличить от «не прочитано».",
    "limits.coverage_closes": "Запустите `bash src/ingest/qc_callability.sh` — нужны mosdepth и BAM, на выходе profile/callability.tsv.",
    "limits.coverage_what": "Ни на один отрицательный геномный вывод нельзя опереться.",
    "limits.no_genome_what": "О геноме нельзя сказать ничего.",
    "limits.assembly_what": "О геноме сказать нельзя ничего: файл в сборке {found}.",
    "limits.assembly_why": "Каталог координат написан в {want}, а файл вызван относительно {found}. Каждый локус искался бы не на своей позиции, поэтому геномный слой отключён, а не допущен к ответу.",
    "limits.assembly_closes": "Перевести файл в {want} (CrossMap или bcftools +liftover с chain-файлом) либо пере-вызвать варианты из выравнивания относительно этой сборки.",
    "limits.assembly_unknown_what": "Сборка геномного файла не установлена.",
    "limits.assembly_unknown_why": "Её не выдали ни заголовок, ни данные: нет длин контигов, нет `##reference`, и за концом первой хромосомы GRCh38 вариантов не нашлось. Ответы считаются так, будто файл в {want}; если это не так, каждый из них — про не ту позицию, и выглядеть неверным он не будет.",
    "limits.assembly_unknown_closes": "Выставить `SCHOLION_GENOME_ASSEMBLY` в ту сборку, что названа в отчёте о секвенировании (GRCh37 · GRCh38 · T2T-CHM13v2.0) — это всё лечение, одна строка. Если никто не помнит, прочитать из файла: `bcftools view -h <file> | grep '##contig' | head -1`, где chr1 на 249250621 — GRCh37, а 248956422 — GRCh38. Чтобы закрыть навсегда: `bcftools reheader -f <reference>.fai <file>`.",
    "limits.no_genome_why": "VCF не подключён: любой геномный ответ был бы про отсутствие файла, а не про вас.",
    "limits.no_genome_closes": "Что закрывает: VCF из собственных ридов либо выгрузка из лаборатории. Путь описан в `scholion doc preparing-the-genome`.",
    "limits.weak_gene_what": "Отрицательный результат по {gene} — не утверждение.",
    "limits.weak_gene_why": "Достаточно глубоко для решения о гетерозиготе (>=10x) прочитано лишь {pct} % оснований гена; остальное не прочитано, а непрочитанное основание даёт то же «находок нет», что и чистое.",
    "limits.weak_gene_closes": "Более глубокое секвенирование либо прицельный анализ {gene} — под него недопокрытые участки выгружаются в BED.",
    "limits.gene_not_read_what": "Фармакогенетический фенотип {gene} не определён.",
    "limits.gene_not_read_why": "Маркёры гена не прочитаны.",
    "limits.gene_not_read_closes": "См. основание выше: там названы позиции и способ их прогенотипировать.",
    "limits.no_corridor_what.one": "{n} показатель печатается без референсного коридора, а значит и без флага.",
    "limits.no_corridor_what.few": "{n} показателя печатаются без референсного коридора, а значит и без флага.",
    "limits.no_corridor_what.many": "{n} показателей печатаются без референсного коридора, а значит и без флага.",
    "limits.no_corridor_why": "Ни ваш бланк, ни словарь не дают границ для: {markers}. Показать их против чужого коридора было бы хуже, чем без флага.",
    "limits.no_corridor_closes": "Внесите коридор со своего бланка: `add-lab <показатель> <дата> <значение> --unit ... --ref-low ... --ref-high ...`.",
    "limits.no_labs_what": "О лабораторном слое нельзя сказать ничего.",
    "limits.no_labs_why": "В профиле нет ни одного показателя.",
    "limits.no_labs_closes": "`import-labs panel.csv` для целой панели или `add-lab` для одного значения; папка PDF — через `ingest-labs`.",
    "limits.prs_what": "Процентиль по «{trait}» снят с доверия.",
    "limits.prs_why": "Вызвано лишь {pct} % вариантов модели — процентиль на таком входе это число без популяции за ним.",
    "limits.prs_closes": "Прогенотипируйте позиции модели из BAM (src/ingest/prs_genotype_sites.sh) либо возьмите модель с лучшим покрытием.",
    "limits.no_sex_what": "Референсные интервалы, зависящие от пола, не показываются.",
    "limits.no_sex_why": "У десятка маркеров — гемоглобин, ферритин, креатинин, тестостерон и другие — коридор разный у мужчины и у женщины. Применить чужой значит напечатать ложную анемию и ложно-нормальный тестостерон, поэтому при неизвестном поле коридор не показывается, а не угадывается.",
    "limits.no_sex_closes": "Скажите, какой: `scholion profile --sex male|female`, или вкладка «Профиль».",
    "limits.no_birth_what": "Возрастные строки бланка не читаются, и возраст не показывается.",
    "limits.no_birth_why": "Многие бланки задают коридор по возрастным диапазонам. Без года рождения такую строку нельзя ни подтвердить, ни исключить, поэтому маркер приходит вовсе без коридора — а без коридора здесь ничто не называется отклонением.",
    "limits.no_birth_closes": "`scholion profile --birth-year 1985`, или вкладка «Профиль».",
    "limits.no_height_what": "Нет индекса массы тела.",
    "limits.no_height_why": "Он считается из роста и веса, а рост не записан.",
    "limits.no_height_closes": "`scholion profile --height-cm 178`, или вкладка «Профиль».",
    "limits.no_weight_what": "Индекса массы тела по-прежнему нет: рост записан, а вес — нет.",
    "limits.no_weight_why": "Вес — это ряд, а не постоянный факт, поэтому он не часть профиля: это измерение, и индекс считается по последнему из них.",
    "limits.no_weight_closes": "`scholion add-metric weight 2026-08-24 78.4`, или вкладка «Профиль».",
    "limits.no_ancestry_what": "Полигенные перцентили считаются против референсной панели ПО УМОЛЧАНИЮ.",
    "limits.no_ancestry_why": "Перцентиль — это место внутри популяции, а какая популяция подходит этому геному, ещё не определено. Против чужой панели это не ваше место — поэтому каждый напечатанный до тех пор перцентиль называет панель, по которой посчитан.",
    "limits.no_ancestry_closes": "Это шаг подготовки генома, а не вопрос к вам: `python3 src/ingest/ancestry_check.py` сравнивает несколько сотен ваших генотипов с пятью панелями 1000 Genomes и пишет ответ рядом с профилем. Оттуда он и берётся — называть суперпопуляцию никого не просят, потому что своей никто не знает.",
    "limits.no_wearable_answer_what": "Там, где одно и то же измерили два прибора, ни один ответ не входит в вывод.",
    "limits.no_wearable_answer_why": "Часы и браслет измеряют сон и пульс покоя по-разному. Пока никто не назван, приложение показывает оба и не делает вывода ни по одному: усреднить их значит выдать смену прибора за перемену в вас.",
    "limits.no_wearable_answer_closes": "Назовите: `scholion profile --wearable garmin|whoop`. Если не носите — скажите об этом: `--wearable {none}`, и больше не спросят.",
    "limits.no_meds_what": "О взаимодействиях и контроль-анализах нельзя сказать ничего.",
    "limits.no_meds_why": "Список назначений пуст, поэтому «взаимодействий не найдено» означало бы «ничего не сравнивалось».",
    "limits.no_meds_closes": "`add-med` на каждый принимаемый препарат, с дозой.",
    "limits.no_wearables_what": "О сне, нагрузке и тренде пульса покоя нельзя сказать ничего.",
    "limits.no_wearables_why": "Выгрузка носимого устройства не загружена.",
    "limits.no_wearables_closes": "`ingest-garmin <папка выгрузки>`; Apple Health идёт тем же слоем.",
    "limits.title": "**Что по этим данным сказать нельзя**",
    "limits.scope.title": "**На какой класс вопросов эти данные отвечают**",
    "limits.scope.input_wgs": "Вход: полный геном — прочитаны все базы, до которых дошло секвенирование, поэтому считаются и отдельные варианты, и полигенные шкалы.",
    "limits.scope.input_array": "на входе генотипирующий чип {vendor} — {markers} выбранных позиций, не геном",
    "limits.scope.array_monogenic": "НЕ поддерживается. У чипа есть зонд на считанные известные варианты гена и больше ни на что, поэтому «патогенных вариантов не найдено» означает лишь, что отрицательны эти несколько зондов. Положительный результат — повод назначить подтверждающий тест, а не находка: измеренная предсказательная ценность чипа по редким патогенным вариантам низка (BMJ 2021: 4,2 % для BRCA1/2; Moscarello 2019: 40 % присланных на подтверждение вариантов ложные).",
    "limits.scope.array_oligogenic": "частично. Распространённые фармакогенетические tag-SNP есть на большинстве чипов и вызываются надёжно; звёздные аллели, которым нужно число копий или фаза (CYP2D6), с массива не разрешаются вовсе.",
    "limits.scope.array_polygenic": "частично. Полигенные шкалы во многом строились на данных чипов, так что это архитектура, которой чип подходит лучше всего — с той же оговоркой про происхождение, что и у любой шкалы.",
    "limits.scope.input_none": "Вход: геномного файла нет. Всё ниже к геному не относится — только к анализам, назначениям и носимым.",
    "limits.scope.input_wrong_build": "Вход: геномный файл в сборке {found}, каталог — в другой; геномный слой отключён. Всё, что ниже про геном, недоступно, пока файл не переведён; анализы, назначения и носимые работают как обычно.",
    "limits.scope.monogenic": "Моногенные признаки (решает один вариант): ClinVar и слой вторичных находок ACMG. Положительная находка — повод для клинического теста, а не замена ему; крупные делеции короткими чтениями не вызываются вовсе.",
    "limits.scope.oligogenic": "Олигогенные признаки (основной вклад несут единицы вариантов): частично — курируемые локусы читаются, взаимодействие между ними не моделируется.",
    "limits.scope.polygenic": "Полигенные признаки (много вариантов, каждый слабый): шкала плюс то, что реально измерено в анализах. Там, где есть прямое измерение, оно перевешивает шкалу, а шкала снимается с доверия, а не оспаривается.",
    "limits.scope.heritability": "Перцентиль — не вероятность, и наследственность объясняет лишь часть разброса любого из этих признаков; остальное — среда, поведение и случай. Доля разная у разных признаков и редко составляет бо́льшую половину.",
    "limits.none": "Все слои, о которых система знает, на месте и читаются. Это не обещание полноты ответов — это утверждение, что не пропало ничего из того, что эта проверка умеет искать.",
    "limits.coverage_line": "Покрытие: измерено генов {genes}, в среднем {mean} % оснований на >=10x; панель ACMG SF — {acmg_genes} генов на {acmg_pct} %.",
    "limits.coverage_weak_line": "Ниже 90 %: {genes}.",
    "limits.considered_closes": "подключение {tool} ({license}) — {url}; в собственных "
                                "заметках сборки назван рассмотренным и не взятым",
    "limits.considered_no_reason": "причина, по которой он не взят, не записана",
    "limits.closes_label": "закрывается",
    "limits.summary": "{count} ограничений, у {closable} названо, чем закрыть.",
    "import.row": "строка {row}",
    "import.dry_ok": "файл чистый: импортировалось бы {rows}. Ничего не записано — это был пробный прогон.",
    "import.written": "импортировано: {rows}",
    "import.markers": "Показатели: {markers}",
    "import_csv.empty": "в файле нет строки заголовка",
    "import_csv.missing_columns": "не хватает обязательных колонок: {columns}. Найденный заголовок: {seen}. Ожидаются: marker, date, value и по желанию unit, ref_low, ref_high, note.",
    "import_csv.need_marker_date": "нет показателя или нет даты",
    "import_csv.value_not_number": "значение «{value}» не число",
    "import_csv.unknown_marker": "такого показателя нет. Возможно: {did_you_mean}",
    "import_csv.bad_unit": "единица «{unit}» этому показателю не подходит; принимаются: {accepted}",
    "import_csv.file_not_found": "файла {path} нет",
    "import_csv.unreadable": "{path} не открывается как текст UTF-8: {error}",
    "import_csv.nothing_written.one": "{n} строка не прошла — НИЧЕГО не записано. Файл импортируется целиком или никак: половина панели в профиле выглядит как целая.",
    "import_csv.nothing_written.few": "{n} строки не прошли — НИЧЕГО не записано. Файл импортируется целиком или никак: половина панели в профиле выглядит как целая.",
    "import_csv.nothing_written.many": "{n} строк не прошли — НИЧЕГО не записано. Файл импортируется целиком или никак: половина панели в профиле выглядит как целая.",
    "import_csv.write_failed": "строка {row} прошла проверку и упала на записи: {detail}. Дальше импорт не пошёл.",
    "store.marker_unknown": "показателя «{marker}» нет, а молчаливое создание — ровно то, из-за чего один анализ превращается в два ряда под двумя написаниями; ничего не записано. Возможно: {did_you_mean}. Чтобы завести осознанно, передайте --new вместе с единицей.",
    "store.no_candidates": "похожего достаточно близко не нашлось",
    "store.need_metric_date": "нужны metric и date",
    "store.value_not_number": "value должно быть числом",
    "store.unit_not_accepted": "единица «{unit}» этому показателю не подходит, а значение в чужой единице сравнивается с порогами другой шкалы — ничего не записано. Показатель {marker} принимает: {accepted}.",
    "store.unit_required": "новому ряду нужна единица: без неё число не с чем сравнивать, а догадка «наверное, обычная» — ровно то, ради чего эта проверка и стоит. Показатель {marker} принимает: {accepted}.",
    "store.need_name": "нужно name",
    "store.no_medications_file": "medications.json не найден",
    "store.need_date": "нужна дата",
    "store.focus_log_what": "Журнал эпизодов для фокуса внимания. ЛИЧНОЕ.",
    "store.demo_occupied": "в каталоге есть данные без пометки synthetic — похоже на настоящий "
                           "профиль; демо туда не пишу (нужен --force)",
    "subject.unknown": "«{value}» \u2014 не тот, кому могут принадлежать данные в этом проекте, а измерение без указанного человека читается как собственное, ради чего это поле и заведено. Ничего не записано. Допустимо: {accepted}.",
    "subject.owner": "вы",
    "subject.demo": "вымышленный человек демонстрации",
    "subject.reference": "опубликованный референсный образец \u2014 другой человек",
    "subject.unattributed": "не указано",
    "subject.demo_erased": "Демонстрационный профиль стёрт: он описывал вымышленного человека, а это ваше собственное измерение \u2014 два человека в одном профиле дают выводы ни о ком. Удалено: {files}. Демонстрация генерируется, поэтому `scholion init --demo --dir <папка>` соберёт её заново ровно такой же.",
    "subject.genome_not_ours": "геном в {path} принадлежит {who}, а в этом профиле данные {whose}. Из него ничего не читается: генотип одного человека рядом с лабораторной историей другого даёт выводы ни о ком.",
    "subject.genome_fix": "держите его в отдельном профиле: `scholion init --dir <папка>`, затем `SCHOLION_PROFILE_DIR=<папка> SCHOLION_GENOME_DIR=<папка с геномом> scholion genome-status`",
    "subject.profile_holds": "чьи данные: {who}",
    "genome_status.engine_unknown": "SCHOLION_GENOME_ENGINE выставлен в «{value}», а этот проект умеет читать так: {accepted}. Ничего не прочитано: незамеченный пин даёт прогон через читателя, которого никто не просил, — ровно то, ради чего пин и заведён.",
    "genome_status.engine_missing": "в SCHOLION_GENOME_ENGINE названо «{value}», а здесь этого нет. Ничего не прочитано — молча перейти на другого читателя значит ответить не на тот вопрос, который задали.",
    "genome_status.assembly_from_signature": "сборка установлена по подписи самого провайдера ({provider}), а не измерена по файлу: {why}.",
    "genome_status.assembly_from_reference_line": "сборка взята из строки `##reference=` — это путь, который кто-то написал и, возможно, уже не имеет: {detail}",
    "genome_status.engine_pinned": "читатель: {engine} (закреплён через SCHOLION_GENOME_ENGINE)",
    "store.templates_missing": "шаблоны не найдены: {path} (пакет собран неполно)",
    "store.slot_external": "{slot}/ (внешнее хранилище)",
    "layout.readme.raw": """# raw — то, что пришло извне

Бланки анализов, выгрузки приборов, сырые чтения, референсные базы.
**Здесь ничего не переписывается, только добавляется.** Источник, который
правят, перестаёт быть источником: становится неоткуда узнать, что разбор
был неверным.

Приложение сюда не пишет и читает только по явной команде.

- `lab/` — бланки и отчёты лаборатории (PDF, DOCX)
- `sequencing/` — FASTQ, BAM и индексы
- `wearables/` — выгрузки Garmin, Apple Health, CGM
- `reference/` — референсный геном, снимки ClinVar

Каталог может лежать на другом диске: `profile/sources.json`, ключ `raw`.
""",
    "layout.readme.raw_lab": """# Бланки анализов и отчёты лаборатории

PDF и DOCX как пришли. Разбор кладётся в `profile/`, оригинал остаётся здесь.
""",
    "layout.readme.raw_sequencing": """# Сырые данные секвенирования

FASTQ, BAM и индексы. Десятки гигабайт — обычное дело; каталог рассчитан на внешний диск.
""",
    "layout.readme.raw_wearables": """# Выгрузки носимых устройств

Архивы Garmin, экспорт Apple Health, скриншоты CGM — как отдал прибор.
""",
    "layout.readme.raw_reference": """# Референсные базы

Геном сравнения, снимки ClinVar и прочее, что скачано из публичных источников.
""",
    "layout.readme.work": """# work — промежуточное

**Этот каталог можно удалить целиком.** Это определение, а не пожелание:
всё отсюда обязано пересчитываться командой. Файл, который нельзя
восстановить, лежит не здесь — ему место в `raw/` или `profile/`.

Здесь же `cache/` — ответы публичных справочников.

Каталог может лежать на другом диске: `profile/sources.json`, ключ `work`.
""",
    "layout.readme.archive": """# archive — что было раньше

Снятые версии файлов профиля. Код под версией и так лежит в git; смысл
архива только в `profile/`, который в git не попадёт никогда.

Складывать сюда по одному снимку на осмысленное изменение, а не по
снимку на каждое сохранение: одиннадцать версий одного файла подряд
невозможно читать, и разбирать их потом никто не станет.
""",

    # ── почему ген важен для класса препаратов ────────────────────────
    "gene_why.statin": "риск миопатии зависит от транспортёра SLCO1B1",
    "gene_why.anticoagulant_vka": "чувствительность к варфарину (VKORC1/CYP2C9)",
    "gene_why.antiplatelet_p2y12": "активация клопидогрела зависит от CYP2C19",
    "gene_why.ppi": "метаболизм ИПП зависит от CYP2C19",
    "gene_why.thiopurine": "токсичность тиопуринов зависит от TPMT/NUDT15",
    "gene_why.opioid_codeine": "активация кодеина/трамадола зависит от CYP2D6",

    # ── биологический возраст (PhenoAge) ──────────────────────────────
    "phenoage.marker.albumin": "альбумин",
    "phenoage.marker.creatinine": "креатинин",
    "phenoage.marker.glucose": "глюкоза",
    "phenoage.marker.crp": "СРБ высокочувствительный (hs-CRP)",
    "phenoage.marker.lymph": "лимфоциты, %",
    "phenoage.marker.mcv": "MCV (ОАК)",
    "phenoage.marker.rdw": "RDW (ОАК)",
    "phenoage.marker.alp": "щелочная фосфатаза",
    "phenoage.marker.wbc": "лейкоциты (ОАК)",
    "phenoage.unit.albumin": "г/л",
    "phenoage.unit.creatinine": "мкмоль/л",
    "phenoage.unit.glucose": "ммоль/л",
    "phenoage.unit.crp": "мг/л",
    "phenoage.unit.lymph": "%",
    "phenoage.unit.mcv": "fL",
    "phenoage.unit.rdw": "%",
    "phenoage.unit.alp": "Ед/л",
    "phenoage.unit.wbc": "10⁹/л",
    "phenoage.rule": "PhenoAge считается только по полной панели одного забора; подстановка "
                     "значений из других месяцев запрещена.",
    "phenoage.no_data": "В profile/labs.json нет данных.",
    "phenoage.incomplete": "Панель {panel}: PhenoAge посчитать нельзя — нет {n} из 9 маркёров. "
                           "Подставлять их из прошлых панелей запрещено; дозаказать в "
                           "следующем заборе.",
    "phenoage.implausible": "PhenoAge не посчитан: {markers} похожи на другую единицу, чем ждёт формула — проверьте единицу на бланке. Неверная единица даёт уверенно неверный возраст.",
    "phenoage.compute_failed": "PhenoAge не посчитан: входные данные не дали корректного результата (скорее всего значение в неожиданной единице).",
    "phenoage.no_age": "Неизвестен возраст: добавьте birth_date в profile/metrics.json.",
    "phenoage.history_header": """# История биологического возраста (PhenoAge)

> Только полные панели: все 9 маркёров одного забора.

| Дата | Хроно | PhenoAge | Δ | Риск-10л |
|---|---|---|---|---|
""",
    "phenoage.panels_title": "## PhenoAge — полнота панелей",
    "phenoage.panels_lead": "Считаем только по панелям, где все 9 маркёров из одного забора.",
    "phenoage.panel_complete": "- **{panel}** [9/9] ✅ полная",
    "phenoage.panel_incomplete": "- {panel} [{have}/9] ❌ нет: {missing}",
    "phenoage.cannot_title": "## ❌ PhenoAge по панели {panel}: посчитать нельзя",
    "phenoage.cannot_missing": "Не хватает {n} из 9 маркёров: {missing}.",
    "phenoage.have_in_panel": "Есть в панели: {items}.",
    "phenoage.request_next": "**Дозапросить в следующей панели** (одним забором со всем "
                             "остальным):",
    "phenoage.no_substitution": "Подставлять эти значения из прошлых панелей нельзя — "
                                "результат будет недостоверным (формула чувствительна к "
                                "альбумину и креатинину).",
    "phenoage.title": "## PhenoAge — панель {panel}",
    "phenoage.chrono_age": "- Хронологический возраст: **{value}**",
    "phenoage.value": "- PhenoAge: **{value}**  (Δ {delta} года)",
    "phenoage.mortality": "- Модельный 10-летний риск смертности: **{value}%**",
    "phenoage.source": "Источник — только эта панель: {items}.",
    "phenoage.caveat": "Не диагноз: PhenoAge — популяционная модель по 9 рутинным маркёрам "
                       "(Levine 2018), чувствительна к разовым колебаниям (глюкоза, СРБ, "
                       "креатинин).",
    "phenoage.tracked": "→ записано в profile/biological_age_history.md",

    # ── сверка бланков: причины, методы, баннер самопроверки ──────────
    "reconcile.candidate_hint": "Рядом с каталогом данных лежит похожая на бланки папка: {path}. По догадке она НЕ читается — назовите её один раз: SCHOLION_LABS_DIR='{path}', либо передайте --lab-dir, либо перенесите бланки в raw/lab/.",
    "reconcile.no_folder": "Папка с бланками не найдена: {path}. Укажите --lab-dir PATH или "
                           "задайте SCHOLION_LABS_DIR.",
    "reconcile.autodetect_failed": "(автопоиск не дал результата)",
    "reconcile.no_text_layer": "нет текстового слоя (скан?)",
    "reconcile.empty_file": "пустой/нечитаемый файл",
    "reconcile.marker_absent": "маркер отсутствует в профиле",
    "reconcile.point_absent": "точка на эту дату отсутствует",
    "reconcile.coverage_note": "Провенанс: маркер → месяц → файл-источник и точная дата "
                               "забора. Регенерируется.",
    "reconcile.coverage_not_written": "(не записан: {error})",
    "form.lcms": "ЖХ-МС/МС",
    "form.clia": "ИХЛА",
    "form.elisa": "ИФА",
    "form.icpms": "ИСП-МС",
    "form.biochemistry": "биохимия",
    "form.cbc": "ОАК",
    "form.urine": "моча",
    "selfcheck.failed": "⚠️ Самопроверка анализов не выполнена: {error}",
    "selfcheck.unreadable": "⚠️ Целостность анализов: {n} НЕЧИТАЕМЫХ бланк(ов) — возможна "
                            "потеря данных.",
    "selfcheck.unreadable_hint": "   → откройте эти файлы на Mac (iCloud материализует), затем "
                                 "повторите проверку.",
    "selfcheck.ok": "✅ Целостность анализов: ОК — нечитаемых бланков нет.",
    "skill.install.installed": 'установлено {path} для этой сборки ({version})',
    "skill.install.replaced": 'заменено {path}: было {previous}, стало {version}',
    "skill.install.unchanged": '{path} уже совпадает с этой сборкой ({version}); версия рядом записана',
    "skill.install.failed": 'не удалось записать в {path} — выберите другую папку: `scholion skill --install <папка>`',
    "selfcheck.skill_copy_older": 'копия скилла в {path} установлена из версии {version} и отличается от этой сборки — `scholion skill --install` её заменит',
    "selfcheck.skill_copy_unmarked": 'копия скилла в {path} отличается от этой сборки и не говорит, из какой сборки она взята — `scholion skill --install` заменит её и запишет версию',
    "selfcheck.counters": "   бланков: {files} · совпало точек: {covered} · на ручную "
                          "проверку: {missing} пропуск(ов) / {mismatch} расхожд. (детально: "
                          "scholion reconcile)",

    # ── выгрузка Garmin ───────────────────────────────────────────────
    "wearables.unknown_device": "«{name}» — не тот прибор, который эта сборка умеет читать.",
    "web.life.device.garmin": "Garmin",
    "web.life.device.whoop": "WHOOP",
    "web.life.device.apple_health": "Apple Health",
    "web.life.device.unspecified": "прибор не записан",
    "web.life.device.": "—",
    "web.life.measured_by": "измерено: {device}",
    "web.life.also_answers": "то же измеряет {other}; выше — прибор, который вы назначили",
    "web.life.also_unresolved": "то же измеряет {other}, и отвечающий прибор не назначен — "
                                "это число показано и ни в один вывод не входит",
    "web.life.two_devices_h": "Два прибора мерят одно и то же",
    "web.life.two_devices_body": "{devices} сообщают одно и то же: {metrics}. Это не одно и то же "
                                 "измерение — другое окно, другой алгоритм, другое место на теле, — "
                                 "поэтому ряды не усредняются друг в друга и ни один не идёт в "
                                 "вывод, пока вы не назовёте отвечающий прибор. Показаны оба в "
                                 "любом случае.",
    "web.life.two_devices_settled": "В профиле два прибора ({devices}); где оба мерят одно, "
                                    "отвечает {primary}.",
    "web.life.pick_device": "отвечает {device}",
    "web.life.primary_set": "теперь там, где два прибора мерят одно, отвечает {device}",
    "web.life.wearable_btn": "Перечитать выгрузку носимого",
    "web.life.wearable_note": "Garmin или WHOOP — выгрузка опознаётся по содержимому.",
    "web.life.wearable_done": "{device}: рядов метрик — {metrics}, {range}",
    "web.life.unknown_columns": "Колонки, которые здесь неизвестны и из которых ничего не прочитано: {columns}",
    "wearables.builder_missing": "не найден {path}",
    "wearables.not_an_export": "{path} — не та выгрузка, которую здесь умеют читать. Её открыли и "
                               "посмотрели внутрь: это ни выгрузка Garmin (папка DI_CONNECT), ни "
                               "выгрузка WHOOP (файлы physiological_cycles, sleeps, workouts — "
                               "папкой или тем zip, что приходит письмом).",
    "wearables.wrong_device": "{path} — это выгрузка {found}, а команду просили про {asked}. Не "
                              "прочитано ничего: записать числа одного прибора под именем другого "
                              "— ровно то, ради чего этот слой и сделан. Прочитать как {found}: "
                              "`scholion ingest-wearable '{path}'`.",
    "wearables.no_export": "Выгрузка носимого не найдена. Garmin: свежая копия из Account → Export "
                           "Your Data. WHOOP: More → App Settings → Data Export, приходит ссылкой "
                           "на почту. Положите папку или zip в raw/wearables/ или передайте аргументом.",
    "wearables.candidate_hint": "Рядом с каталогом данных лежит выгрузка {device}: {path}. По "
                                "догадке она НЕ читается — передайте её аргументом, назовите один раз "
                                "(`scholion set-folder {device} '{path}'`) или перенесите в "
                                "raw/wearables/.",
    "wearables.parse_failed": "Выгрузку не удалось разобрать: {error}",
    "wearables.nothing_recognised": "{path} открыт как выгрузка {device}, и в нём не нашлось ни "
                                    "одного измерения, которое здесь умеют назвать.",
    "wearables.nightly_note": "Значения по ночам, как их сообщил {device}. Держатся отдельно от "
                              "месячных трендов, потому что отвечают на другой вопрос: что "
                              "изменилось после конкретного вечера.",
    "wearables.done": "{device}: рядов метрик — {metrics}, ночей — {nights}, сохранено прежних "
                      "точек — {preserved}.",
    "wearables.columns_unknown": "Колонки, которые здесь неизвестны и из которых ничего не "
                                 "прочитано: {columns}. Если какая-то из них — нужное измерение, "
                                 "назовите её в profile/wearable_metrics.local.json и перечитайте выгрузку.",
    "wearables.correction_applied": "  ✓ ваша правка применена: {metric} {month} — {action} ({why})",
    "wearables.correction_stale": "  · ваша правка больше ни на что не попадает: {metric} {month} — этого месяца в ряду больше нет",
    "wearables.correction_refused": "  ⚠️ ваша правка НЕ применена: {metric} {month} — {refused}",
    "wearables.shared": "Обе выгрузки сообщают {metrics}. Они хранятся раздельно и НЕ усредняются: "
                        "одинаковое название не делает измерение одинаковым. Назначить, кто "
                        "отвечает: `scholion profile --wearable <прибор>`.",
    "wearables.unspecified": "прибор, которым это записано, не зафиксирован",
    "garmin.builder_missing": "не найден {path}",
    "garmin.candidate_hint": "Рядом с каталогом данных лежит выгрузка носимого: {path}. По догадке она НЕ читается — назовите её один раз: `scholion set-folder garmin '{path}'`, передайте папку аргументом или перенесите в raw/wearables/.",
    "garmin.no_export": "Не найдена папка garmin_export (с DI_CONNECT). Скачайте свежий "
                        "GDPR-экспорт Garmin (Connect → Настройки аккаунта → Экспорт данных), "
                        "распакуйте в garmin_export рядом с проектом — или укажите путь явно.",
    "garmin.parse_failed": "Сбой разбора Garmin: {error}",
    "garmin.nothing_recognised": "В {path} не нашлось распознаваемых данных Garmin.",
    "garmin.nightly_source": "Garmin Connect (GDPR-экспорт), sleepData.json",
    "garmin.nightly_note": "Фазы сна до 2022 года несопоставимы с нынешними: старый прибор "
                           "помечал «глубоким сном» до 81 % ночи. bedtime_min_from_20 — минуты "
                           "от 20:00 местного времени (МСК).",

    # ── полный геном: вызовы, координаты, уровни ClinVar ──────────────
    "genome.confirmed_ref_short": "референс подтверждён вызовом в позиции (0/0)",
    "genome.no_coordinates_for_assembly": "в каталоге нет координаты {assembly} для {rsid}, а файл вызван против {assembly}. Между сборками здесь ничего не пересчитывается: смещение непостоянно даже внутри одной хромосомы, и пересчитанная позиция указала бы на настоящее основание, но не на то. Локус остаётся непрочитанным, пока его координата {assembly} не добавлена из первоисточника.",
    "genome.confirmed_ref": "референс подтверждён вызовом по сайту (0/0), а не выведен из "
                            "отсутствия строки",
    "genome.low_depth_suffix": "; покрытие низкое ({depth} чтений) — вызов ненадёжен",
    "genome.needs_confirmation": "этот вызов стоило бы подтвердить другим методом — {what} ({value})",
    "genome.confirm_low_qual": "низкая оценка качества у самого вызывателя",
    "genome.confirm_allele_fraction_off_half": "риды делятся не пополам, как полагалось бы гетерозиготе",
    "genome.confirm_allele_fraction_low_for_homozygote": "пятая часть ридов и более всё ещё несёт референс",
    "genome.confirm_low_depth": "слишком мало ридов",
    "genome.confirm_filtered": "вызыватель пометил строку фильтром",
    "genome.confirm_imputed": "генотип выведен, а не наблюдён",
    "genome.low_depth": "покрытие низкое ({depth} чтений) — вызов ненадёжен",
    "array.not_on_chip": "этой позиции на чипе {vendor} нет вовсе — её не опрашивали, поэтому по ней ничего не подтверждено и не исключено",
    "array.no_call": "позиция на чипе есть, но вызов не удался — генотипа нет, и это не то же самое, что отсутствие варианта",
    "array.strand_ambiguous": "⚠ у этого локуса ({gene}) аллели {ref}/{alt} — комплементарны сами себе. Если выгрузка сообщила другую цепь, вызов выглядел бы верным и был бы неверным, а массив различить не даёт. Считайте это требующим подтверждения, а не результатом.",
    "array.path_closed": "Этот путь на генотипирующем чипе закрыт. У чипа есть зонд на считанные известные варианты гена и нет глубины вовсе, поэтому «ничего не найдено» означало бы лишь, что отрицательны эти несколько зондов, — а положительный результат чаще был бы неверным, чем верным (BMJ 2021: предсказательная ценность 4,2 % для BRCA1/2 на потребительских чипах; Moscarello 2019: 40 % присланных на подтверждение вариантов ложные). Закрыт, пока нет частотного порога и ярлыка качества входа.",
    "array.open_instead": "На что массив ОТВЕЧАЕТ: каталог локусов — частые фармакогенетические и признаковые варианты, регистр, ради которого чип и сделан. `scholion genome --gene CYP2C19`, `scholion drug <название>`, `scholion array` — покрытие этого чипа по каталогу.",
    "array.coverage_title": "**Этот чип против каталога локусов**",
    "array.coverage_line": "вызвано {called} из {total} локусов каталога ({pct} %) · не вызвалось {no_call} · нет на чипе {absent}",
    "array.absent_header": "Чип их не несёт — по ним ничего не подтверждено и не исключено:",
    "array.ambiguous_header": "Вызваны, но неоднозначны по цепи — считать требующими подтверждения:",
    "array.unreadable": "выгрузка {vendor} лежит здесь, и из неё не прочитано ни одной строки — это отказ чтения файла, а НЕ утверждение о чипе. Пока файл не разобран, ничего не подтверждено и не исключено: проверьте, что файл скачан целиком, и если его открывали и пересохраняли в таблице — возьмите исходную загрузку.",
    "array.no_array": "генотипирующий чип не найден (задайте SCHOLION_ARRAY_FILE или положите выгрузку в папку генома)",
    "array.assembly_declared": "выгрузка сама объявляет сборку в шапке: {assembly} — локусы сопоставляются по rsID, который от неё не зависит",
    "array.called": "вызвано с генотипирующего чипа {vendor}",
    "array.what_it_cannot_do": "Генотипирующий чип читает несколько сотен тысяч выбранных позиций, а не геном. Он не может найти вариант, зонда на который у него нет; его вызовы редких вариантов ненадёжны настолько, что положительный результат требует подтверждения другим методом; и о позициях, которых у него нет, он не говорит ничего. Всё, что сборка сообщает по чипу, несёт этот потолок.",
    "array.summary": "Генотипирующий чип: {vendor}, позиций — {markers}. Это не секвенированный геном — потолок ниже.",
    "genome.assumed_ref_note": "сайта нет в вариантном VCF: это референс ИЛИ отсутствие "
                               "покрытия — чтобы различить, догенотипируйте позиции из BAM "
                               "(src/ingest/loci_sites_bed.py + prs_genotype_sites.sh)",
    "genome.rsid_unknown": "rsID {rsid} не найден ни в каталоге, ни в Ensembl (или нет сети).",
    "genome.coordinate_only": "Координата найдена, но полная геномная база ещё не подключена "
                              "(нужен genome/*.vcf.gz + .tbi).",
    "genome.need_rsid_or_gene": "нужен rsid или gene",
    "genome.clinvar_not_run": "Ваш VCF ещё не аннотирован по ClinVar. Этот широкий экран "
                              "читает весь файл против всего ClinVar, и такому проходу нужны "
                              "установленные bcftools и htslib — `scholion tools` скажет, есть "
                              "ли они, а шаг описан в `scholion doc preparing-the-genome`. "
                              "Узкому экрану находок, о которых принято сообщать, не нужен "
                              "никто из них: 84 гена ACMG прогоняет `scholion acmg-scan`.",
    "genome.conflict": "Отчёт лаборатории и собственные чтения здесь расходятся: в отчёте "
                       "{reported}, в чтениях {called}. Выше показано то, что говорят чтения — "
                       "у них есть покрытие, их можно перепроверить, и отчёт сделан из них. "
                       "Такое расхождение имеет смысл отнести тому, кто выдал отчёт.",
    "genome.confirmed_by_report": "Собственные чтения и отчёт лаборатории в этой позиции совпадают.",
    "genome.acmg_not_run": "Ваш VCF ещё не сверен со списком ACMG SF. Эту сверку делает "
                           "`scholion acmg-scan`: ей нужен опубликованный файл ClinVar для вашей "
                           "сборки и больше ничего — ни bcftools, ни индекса, — а когда файла "
                           "нет, команда печатает ту единственную загрузку, которая нужна.",
    "genome.apoe_ambiguous": "Обе точки гетерозиготны, и такой генотип — это {a} либо {b}, смотря какой аллель на какой хромосоме; этого файл не несёт. {a} заметно частотнее во всех изученных популяциях — это повод сказать, что вероятнее, а не повод напечатать это как ответ. Разрешается фазировкой или генотипом родителя.",
    "genome.apoe_unexpected": "rs429358 {a} при rs7412 {b} — комбинация, которой ε-гаплотипы не дают; проверьте вызовы, прежде чем что-то из них выводить",
    "genome.indels_not_left_aligned": "⚠ Вставки и делеции в этом списке сопоставлялись БЕЗ левого выравнивания: аннотация шла без референсной FASTA, поэтому индел, записанный иначе, чем копия в ClinVar, был не найден, а не найден и отвергнут. Замен это не касается. Задайте SCHOLION_REFERENCE_FASTA и перезапустите `annotate_clinvar.sh`.",
    "genome.apoe_note": "ε-статус приблизителен без фазировки; для клиники подтвердить.",
    "clinvar.tier.pathogenic": "Патогенные / вероятно патогенные",
    "clinvar.tier.pathogenic.hint": "надо знать: связь с болезнью или носительство",
    "clinvar.tier.drug": "Фармакогенетика",
    "clinvar.tier.drug.hint": "влияет на подбор/дозу лекарств — обсудить с врачом (см. «Лекарства»)",
    "clinvar.tier.risk": "Факторы риска",
    "clinvar.tier.risk.hint": "умеренно повышают риск — контекст для скрининга, не диагноз",
    "clinvar.tier.protective": "Защитные",
    "clinvar.tier.protective.hint": "вариант с защитным эффектом",
    "clinvar.tier.association": "Слабые ассоциации (GWAS)",
    "clinvar.tier.association.hint": "статистическая связь малой силы; не действие",
    "clinvar.tier.uncertain": "Неоднозначные / неопределённые",
    "clinvar.tier.uncertain.hint": "эксперты не сошлись во мнении — как правило, не риск",

    # ── инструментальные исследования и заключения врачей ─────────────
    "studies.reason_several_documents_in_one_file": "в одном файле несколько исследований: {n} — загрузчик пока не умеет их разделять, и ни одно не попало в профиль",
    "studies.reason_part_not_read": "прочитан по частям: взято {kept}, а заключения не отдали столько: {n} — они названы ниже",
    "studies.part_before_the_first_heading": "часть до первого заголовка",
    "studies.reason_no_text": "PDF не отдал текста вовсе — скан без OCR",
    "studies.reason_looks_like_a_lab_form": "лабораторный бланк: числа берёт `ingest-labs`, а не этот загрузчик",
    "studies.reason_conclusion_not_extracted": "читается как исследование, но заключение из него не извлеклось",
    "studies.reason_unclassified": "ни заключение, ни лабораторный бланк ни по одному признаку, известному этому загрузчику",
    "studies.kind_default": "исследование",
    "studies.from_conclusion": "из заключения",
    "studies.no_pdf_reader": "Не найден инструмент чтения PDF: pip3 install pdfplumber",
    "studies.folder_not_found": "Папка не найдена: {path}",
    "studies.meta_what": "ЛИЧНЫЕ инструментальные исследования и заключения врачей.",
    "studies.hint": "Поля answers/does_not_answer загрузчик НЕ заполняет — это суждение. "
                    "Пройдите новые записи и допишите, на какие вопросы исследование отвечает, а "
                    "на какие нет.",

    # ── загрузка PDF-бланков анализов ─────────────────────────────────
    "ingest_labs.reason_several_dates": "в таблице {n} разных дат забора ({first} … {last}); этот импорт относит файл целиком к одной дате, а выбрать одну из нескольких значило бы угадать за человека",
    "ingest_labs.reason_ambiguous_date": "на бланке «{raw}» — это либо {first}, либо {second}; на странице не сказано, в каком порядке печатает эта лаборатория, а точка, попавшая не в тот месяц, встаёт в ряд и двигает тренд. Введите дату забора сами через `scholion add-lab` или возьмите выгрузку, где дата записана полностью",
    "ingest_labs.date_from_filename": "дата {date} взята из ИМЕНИ ФАЙЛА, а не с бланка — на самой странице её нет. Файл называет тот, кто его сохранил, и часто по дню скачивания",
    "ingest_labs.reason_no_date": "на бланке не нашлась дата взятия",
    "ingest_labs.reason_no_text": "в файле нет извлекаемого текста (скан без распознавания)",
    "ingest_labs.reason_table_labels": "{n} подписей строк этой таблицы не совпали ни с одним показателем словаря — они перечислены, а не сохранены под приблизительным именем",
    "ingest_labs.reason_no_marker": "дата прочитана, но ни одна строка не совпала с известным показателем",
    "ingest_labs.reason_error": "при чтении этого файла возникло исключение {type}: {text} — остальная папка обработана; этот файл нет, и он будет прочитан заново при следующем запуске",
    "fhir.title": "**Бандл FHIR:** {path} — наблюдений {observations}",
    "fhir.dry_run": "взял бы {results} (ничего не записано)",
    "fhir.added": "внесено в профиль: {n}",
    "fhir.refused": "{label} — не записано: {reason}",
    "fhir.not_taken": "**Не взято, по причинам:**",
    "fhir.reason.no_quantity": "в ресурсе нет числового значения (кодированный результат, панель-группировка, вложение)",
    "fhir.reason.metric_unit_not_ours": "измерение тела в единице, которой эта метрика не держит — здесь ничего не пересчитывается, а вес в фунтах, попавший в ряд в килограммах, и есть та самая тишина, ради которой этот шлюз написан",
    "fhir.metrics_taken": "измерений тела записано в слой метрик: {n}",
    "fhir.metrics_dry": "взял бы в слой метрик измерений тела: {n} (ничего не записано)",
    "fhir.reason.loinc_is_a_body_metric": "измерение тела, а не лабораторный аналит — ему не место в словаре показателей вовсе, а там, где ту же величину держит наша собственная метрика, она названа рядом с кодом",
    "fhir.reason.loinc_not_in_catalogue": "кода LOINC нет в словаре этой сборки — сопоставить по названию значило бы угадать, что это за показатель",
    "fhir.reason.no_loinc": "у наблюдения нет кода LOINC вовсе",
    "fhir.reason.no_date": "нет даты; результат без даты в ряду не место",
    "fhir.reason.not_final": "источник сам не считает результат окончательным (статус не final/amended/corrected)",
    "fhir.profile_facts": "бандл сообщает о своём пациенте ещё и {facts}. НЕ применено: файл может содержать родственника, образец или двух человек, а взять личность из файла — та ошибка, которая потом отравляет всё остальное. Если это вы — задайте сами: `scholion init --sex … --birth-year …`",
    "fhir.unreadable": "{path} не читается как JSON: {error}",
    "fhir.not_a_bundle": "это ресурс FHIR типа «{kind}», а не Bundle. Выгрузите бандл целиком — одиночный ресурс истории не несёт",
    "ingest_labs.folder_empty": "в {path} нет ни одного файла с результатами — ни PDF, ни выгрузки CSV/TSV/TXT",
    "ingest_labs.no_pdf_reader": "Не найден инструмент чтения PDF. Установите в Терминале: pip3 "
                                 "install pdfplumber",
    "ingest_labs.folder_not_found": "Папка не найдена: {path}",

    # ── сетевой доступ из этого Python ────────────────────────────────
    "net.offline": "SCHOLION_OFFLINE=1 — сетевые запросы отключены",
    "server.remote_bind_refused": "отказ от привязки к {host}: разрешён только loopback, иначе профиль был бы открыт в сеть. Задайте SCHOLION_ALLOW_REMOTE=1, чтобы осознанно переопределить.",
    "prs.offline": "SCHOLION_OFFLINE=1 — сервер полигенных оценок не запускается (uvx тянул бы его с PyPI)",
    "sources.kind.mirror": "Везётся в сборке и обновляется наверху — {n}",
    "sources.kind.pipeline": "Скачивается геномным конвейером — {n}",
    "sources.kind.live": "Спрашивается в момент запроса, ничего не хранится — {n}",
    "sources.license_line": "лицензия: {license}",
    "sources.line_bundled_stamped": "копия, приехавшая с пакетом ({date})",
    "sources.manual.reference": "референсный геном и его аннотация — десятки гигабайт; геномный конвейер тянет их один раз",
    "sources.manual.live": "ничего не хранится, поэтому нечего импортировать: адрес спрашивается, только когда препарата или локуса нет в локальной базе, и отправляется только это название",
    "sources.title": "**Справочные источники** — что зеркалит эта сборка и когда обновлялось",
    "sources.how_to_read": "Источнику, который обновляется наверху, нужен путь импорта, иначе зеркало расходится с тем, чем себя называет. `scholion sources --refresh` подтягивает то, что автоматизируется; остальные честно называют, что нужно сделать руками и почему.",
    "sources.auto_header": "Импортируются автоматически — {n}",
    "sources.manual_header": "Вручную — {n}",
    "sources.line_local": "обновлено на этой машине ({date})",
    "sources.line_bundled_newer": 'ваше обновление ({local}) старше копии, которую несёт эта сборка ({bundled}), поэтому отвечает комплектная копия',
    "sources.line_local_undated": 'локальная копия без даты — отвечает она, и сравнить её с комплектной нельзя',
    "sources.line_bundled": "копия, приехавшая с пакетом",
    "sources.cadence": "меняется наверху: {text}",
    "sources.offline": "SCHOLION_OFFLINE=1 — импорту нужна сеть, поэтому он не запускается",
    "sources.fetch_failed": "не удалось прочитать {url}",
    "sources.refreshed": "{source}: проверено определений аллелей — {n}, изменено — {changed}",
    "sources.no_changes": "{source}: проверено, расхождений нет",
    "sources.manual.generic": "этот источник нельзя импортировать автоматически",
    "sources.manual.mane": "Не импортируется автоматически, потому что меняет не значение в базе, а ФОРМУ измерения: каллабилити сейчас считается по локусу гена с полем 10 кб, а MANE Select переносит её на кодирующую последовательность одного согласованного транскрипта плюс сайты сплайсинга. Это изменение конвейера со своими референсными файлами, и оно должно быть осознанным шагом со сравнением старых и новых чисел рядом — а не фоновым обновлением, которое молча меняет смысл процента.",
    "sources.manual.clinvar": "ClinVar аннотируется против вашего собственного генома — нужен bcftools и геномный конвейер, а не скачивание каталога",
    "sources.manual.pgs": "модель PGS закрепляется намеренно: принятие новой рвёт ряд, поэтому это решение, а не обновление",
    "sources.manual.eflm": "это заменило бы плоскую зону «у границы» в 10 % на reference change value по каждому аналиту — нужны коэффициенты внутрииндивидуальной биологической вариации, а они берутся из этой базы, а не из чьей-либо памяти. Между «здесь» и «там» стоят регистрация и сверка по каждому показателю.",
    "sources.manual.loinc": "LOINC требует регистрации и принятия условий, а сопоставление кода с показателем нуждается в медицинской проверке",
    "sources.manual.acmg": "список вторичных находок ACMG публикуется статьёй; человек читает её и фиксирует версию",
    "sources.manual.longevitymap": "лицензия запрещает бандлить, поэтому скрипт сборки тянет его в вашу копию",
    "sources.init_hint": "Справочные источники: `scholion sources` показывает, что зеркалит сборка; `scholion sources --refresh` подтягивает то, что импортируется автоматически (сегодня — CPIC). Без этой команды ничего не скачивается.",
    "net.diag_target_unknown": "«{value}» — не та проверка, которую здесь знают. Проверка связи выбирает адрес из закреплённого списка, а не принимает его снаружи: этот маршрут доступен любой странице в браузере. Известные проверки: {accepted}.",
    "net.diag_host_refused": "проверка связи обращается только к справочным хостам, которые использует сам инструмент, и только по https — произвольный адрес не запрашивается",
    "net.offline_deliberate": "SCHOLION_OFFLINE=1 — сетевые запросы отключены сознательно",
    "net.offline_hint": "снимите переменную окружения SCHOLION_OFFLINE, если сеть нужна",
    "net.certificates_hint": "Похоже на отсутствие корневых сертификатов у Python на Mac. Один "
                             "раз выполните в Терминале: /Applications/Python\\ 3.13/Install\\ "
                             "Certificates.command (или: pip3 install --upgrade certifi).",
    "net.tls_verify_failed": "Проверка сертификата не прошла — запрос отменён. Ответ по "
                             "непроверенному каналу может быть подменён, а из него берётся класс "
                             "препарата и пара ген↔препарат. Обойти проверку осознанно: "
                             "SCHOLION_TLS_INSECURE=1.",
    "net.tls_insecure_warning": "⚠ SCHOLION_TLS_INSECURE=1 — сертификат НЕ проверяется, "
                                "ответ может быть подменён.",

    # ── расчёт полигенных баллов по PGS Catalog ───────────────────────
    "prs.no_uvx": "не найден uvx — установите uv (https://docs.astral.sh/uv)",
    "prs.server_silent": "сервер just-prs завершился без ответа",
    "prs.server_silent_why": "сервер just-prs завершился без ответа (код выхода {code}). Что он сказал — напечатано выше этой строки. Одна известная причина: зависимость сайдкара разрешилась в версию, под которую он не писался, — этот запуск ограничивает разрешение «{constraint}» через UV_CONSTRAINT; если строки выше называют fastmcp или расширение задач, ограничение не применилось",
    "prs.search_empty": "search_scores: пустой ответ",
    "prs.no_coverable_models": "нет покрываемых моделей (все genome-wide или без метаданных)",
    "prs.fallback_chosen": "    fallback search_scores → {pgs_id} ({variants} вариантов), "
                           "match_rate={rate}",
    "prs.no_traits": "нет признаков (пуст prs_traits.json или фильтр --only ничего не нашёл)",
    "prs.vcf_not_found": "VCF не найден: {path}",
    "prs.normalising": "→ нормализую геном в генотипы (полный VCF — это долго, ~минуты; "
                       "результат кэшируется)…",
    "prs.normalised": "  ✓ нормализовано: {path}",
    "prs.normalise_failed": "  ⚠ нормализация не удалась ({error}) — считаю по сырому VCF "
                            "(медленнее)",
    "prs.args_rejected": "    ⚠ сервер не принял {args} — повтор без них",

    # ── чтение tabix-индекса ──────────────────────────────────────────
    "genome.bad_tabix": "{path}: не похоже на tabix-индекс",

    # ── the language switcher: every language is named in itself ─────────
    "web.lang.en": "English",
    "web.lang.ru": "Русский",

    # ── web: the page frame ──────────────────────────────────────────────
    "web.header.subtitle": "геном · анализы · назначения",
    "web.header.local_badge": "работает локально · ассистент опционален",
    "web.header.local_badge_hint": "Почему это важно и как подключить модель — «Ассистент» в меню ☰",
    "web.header.disclaimer": "Не диагноз и не назначение. Материал для обсуждения с лечащим "
                             "врачом. Ассистент не меняет терапию.",
    "web.header.build": "сборка {version}",
    "web.header.language": "Язык интерфейса",

    # ── web: the tabs ────────────────────────────────────────────────────
    "web.tab.overview": "Обзор",
    "web.tab.labs": "Анализы",
    "web.tab.genome": "Геном",
    "web.tab.lifestyle": "Образ жизни",
    "web.tab.second_opinion": 'Радар',
    "web.tab.assistant": "Ассистент",

    # ── web: words shared by every screen ────────────────────────────────
    "web.common.loading": "загрузка…",
    "web.common.loading_parts": "загрузка… получено: {done}",
    "web.common.error": "ошибка",
    "web.common.error_prefix": "Ошибка: ",
    "web.common.failed": "не удалось",
    "web.common.failed_prefix": "Не удалось: ",
    "web.common.canceled": "Отменено",
    "web.common.folder_chosen": "Папка выбрана ✓",
    "web.common.folder_reset": "Папка сброшена",
    "web.common.opening_picker": "Открываю выбор папки…",
    "web.common.added": "Добавлено ✓",
    "web.common.saved": "Записано ✓",

    # ── web: the source chips ────────────────────────────────────────────
    "web.source.release": "версия {release}",
    "web.source.updated": "обновлено {date}",
    "web.source.synced": "синхр. {date}",
    "web.source.absent": "нет данных",
    "web.source.pick_btn": "папка",
    "web.source.pick_title": "Выбрать папку с данными на диске",
    "web.source.reset_title": "Вернуть папку по умолчанию (профиль)",
    "web.source.local_label": "Локальный профиль",
    "web.source.local_kinds": "анализы, назначения, показатели, геном",
    "web.source.profile_updated": "обновлён {date}",
    "web.source.public_label": "Международные базы",

    # ── web: the status vocabulary of the badges ─────────────────────────
    "web.flag.high": "выше нормы",
    "web.flag.low": "ниже нормы",
    "web.flag.ok": "норма",
    "web.flag.near": "у границы",
    "web.flag.unknown": "нет данных",
    "web.level.high": "важно",
    "web.level.moderate": "внимание",
    "web.level.low": "ок",
    "web.level.unknown": "нет данных",
    "web.severity.high": "высокий риск",
    "web.severity.moderate": "внимание",
    "web.severity.low": "низкий",
    "web.near.margin": "{pct}% до {side} границы {bound}",
    "web.near.corridor": "{pct}% ширины коридора",
    "web.decision.crossed": "порог действия пройден: {label} ({sign} {value})",
    "web.decision.not_reached": "порог действия {value} ({label}) — не достигнут",

    # ── web: the goal dashboard ──────────────────────────────────────────
    "web.goal.not_set": "Цель ещё не задана. Заполненный образец — в "
                        "profile/health_goals.json под `_meta._example`.",
    "web.goal.title": "Ваша цель по показателям",
    "web.goal.as_of": "данные на {date}",
    "web.goal.in_one_phrase": "Одной фразой:",
    "web.goal.targets_h": "Целевые показатели",
    "web.goal.col_marker": "Показатель",
    "web.goal.col_now": "Сейчас",
    "web.goal.col_best": "Ваш лучший (год)",
    "web.goal.col_target": "Цель",
    "web.goal.lg_now": "сейчас",
    "web.goal.lg_best": "лучшее историческое",
    "web.goal.lg_target": "цель",
    "web.goal.lg_window": "ваше опорное окно",
    "web.goal.body_h": "Вес и состав тела",
    "web.goal.weight": "Вес",
    "web.goal.bodycomp": "Состав тела",
    "web.goal.metabolism_h": "Метаболизм и гормоны",
    "web.goal.fitness_h": "Аэробная форма и печень",
    "web.goal.aerobic": "Аэробная форма",
    "web.goal.ldl_alt": "ЛПНП/АЛТ",
    "web.goal.ds_fat": "Жир %",
    "web.goal.ds_muscle": "Мышцы",
    "web.goal.note": "Данные живые — из той же модели, что читает всё остальное приложение "
                     "(анализы + трекер + весы). После новой панели анализов или взвешивания точки "
                     "появляются сами; сверяйте их с жёлтыми целевыми линиями и зелёным опорным "
                     "окном — и то и другое берётся из цели, заданной вами в health_goals.json. "
                     "Там, где цель — состав тела, ключевая метрика {key_metric}, а не только "
                     "цифра на весах.",
    "web.goal.note_key": "жир вниз при мышце на месте",
    "web.goal.chart_nodata": "Рядов здесь пока нет — график появится, когда будет что "
                             "рисовать.",
    "web.goal.charts_unavailable": "Графики недоступны (не загрузился chart.min.js). Перезапустите "
                                   "приложение и обновите страницу.",

    # ── web: overview ────────────────────────────────────────────────────
    "web.header.subject": "субъект {subject}",
    "web.header.genome_gaps": "{n} целевых генов не прочитано из генома",
    "web.header.demo_banner": "ДЕМО — вымышленный человек. Ничто на этих экранах не относится "
                              "к вам: числа, назначения и генотипы сгенерированы. Свой профиль "
                              "заводится командой «scholion init».",
    "count.prescriptions.one": "{n} назначение",
    "count.prescriptions.few": "{n} назначения",
    "count.prescriptions.many": "{n} назначений",
    "web.doc.list_title": "Документы этой сборки",
    "web.doc.back": "назад в приложение",
    "web.doc.foot": "Документ, который едет внутри пакета. Тот же текст печатает "
                    "`scholion doc <имя>` в командной строке.",
    "web.second.for_clinician": "Страница для врача",
    "web.second.for_clinician_note": "что это за программа, на одну страницу — откроется в "
                                     "новой вкладке, печатается на один лист",
    "web.overview.person_h": "Человек",
    "web.overview.metrics_h": "Мои показатели",
    "web.overview.focus_h": "Фокус внимания",
    "web.overview.watched_h": "Показатели под контролем",
    "web.overview.stat_above": "из них выше потолка",
    "web.overview.stat_below": "из них ниже пола",
    "web.overview.stat_abnormal": "вне нормы из измеренных маркёров",
    "web.overview.stat_suggested": "анализов к сдаче",
    "web.overview.red_h": "Вне нормы сейчас",
    "web.overview.red_window": "за последние 12 месяцев",
    "web.overview.stale_hidden": "Ещё {count} старше 12 мес. скрыто — смотрите на вкладке «Анализы».",
    "web.overview.tests_h": "Что сдать",
    "web.overview.no_red": "Отклонений нет. Измерено показателей: {n}.",
    "web.overview.no_red_nodata": "Ничего ещё не измерено, поэтому и отмечать нечего. "
                                  "Загрузите анализы — и эта строка начнёт что-то значить.",
    "web.overview.no_priority_tests": "Из того, что сейчас в профиле, нового назначения не следует. Плановый контроль и интервалы повторов — в разделе «Что сдать» на вкладке «Радар».",

    # ── web: focus of attention ──────────────────────────────────────────
    "web.focus.track_tip": "база {base} · сейчас {now} · ориентир {target}",
    "web.focus.baseline": "база {value}",
    "web.focus.target": "ориентир {value} {unit}",
    "web.focus.since": "с {date}",
    "web.focus.vs_baseline": "{delta} к базе",
    "web.focus.mean_over": "среднее за {nights} {from} → {to}",
    "web.focus.levers_h": "Рычаги — что показывают собственные данные",
    "web.focus.expected_prefix": "ожидаемо ",
    "web.focus.now": "сейчас: {text}",
    "web.focus.journal_h": "Журнал эпизодов",
    "web.focus.journal_count": "· {entries}",
    "web.focus.journal_empty": "· пока пуст",
    "web.focus.alcohol_none": "алкоголя не было",
    "web.focus.alcohol_light": "1–2 порции",
    "web.focus.alcohol_heavy": "больше",
    "web.focus.atenolol": "атенолол 50 мг",
    "web.focus.late_meal": "поздний плотный ужин",
    "web.focus.note_placeholder": "заметка",
    "web.focus.save": "Записать",
    "web.focus.questions_h": "Вопросы, которые из этого следуют",
    "web.focus.entry_removed": "Запись удалена ✓",
    "web.focus.entry_saved": "Записано ✓ · всего {n}",
    "web.focus.save_failed": "Не удалось записать",

    # ── web: labs ────────────────────────────────────────────────────────
    "web.labs.within_h": "В пределах нормы ({n})",
    "web.labs.title": "Анализы: {abnormal} отклонений из {total}",
    "web.labs.pick_docs": "Папка исследований (PDF)",
    "web.labs.reingest": "Обновить из папки",
    "web.labs.add_manually": "Добавить вручную",
    "web.labs.docs_folder_set": "Папка исследований: {path}. По кнопке «Обновить» приложение "
                                "разбирает PDF и само пересобирает сводку анализов — labs.json "
                                "создаётся автоматически, выбирать его не нужно.",
    "web.labs.docs_folder_unset": "Укажите ОДНУ папку с исходными PDF (напр. «Лабораторные "
                                  "исследования»). Приложение само извлечёт показатели с датами и "
                                  "создаст сводку анализов — отдельный labs.json выбирать не "
                                  "нужно.",
    "web.labs.reading_pdf": "Читаю PDF из папки…",
    "web.labs.ingest_files": "Обработано файлов: {n}",
    "web.labs.ingest_points": ", добавлено точек: {points}, пропущено (без изменений/не анализы): "
                              "{skipped}.",
    "web.labs.ingest_nothing_new": "Новых показателей не найдено (возможно, всё уже загружено).",
    "web.labs.points_added": "добавлено точек: {n} ✓",
    "web.labs.no_new_data": "Новых данных нет",
    "web.labs.add_note": "Новая точка добавится в labs.json (profile). Инструменты и тренды "
                         "обновятся сразу.",
    "web.labs.genome_link": "геном: {text}",
    "web.labs.owner_note": "заметка владельца",

    # ── web: the add forms ───────────────────────────────────────────────
    "web.form.marker": "Показатель",
    "web.form.new_option": "— новый —",
    "web.form.date_month": "Дата (YYYY-MM)",
    "web.form.date_day": "Дата (YYYY-MM-DD)",
    "web.form.value": "Значение",
    "web.form.save": "Сохранить",
    "web.form.key": "Ключ",
    "web.form.name": "Название",
    "web.form.name_placeholder": "Мой показатель",
    "web.form.unit": "Ед.",
    "web.form.ref_from": "Норма от",
    "web.form.ref_to": "Норма до",
    "web.form.fill_required": "Заполните показатель, дату и значение",

    # ── web: the drug check ──────────────────────────────────────────────
    "web.drug.title": "Проверить препарат",
    "web.drug.intro": "«Полная проверка» = фармакогенетика + взаимодействия с вашими текущими "
                      "назначениями + мониторинг. Готовит второе мнение к разговору с врачом.",
    "web.drug.placeholder": "название препарата, напр. метформин или аспирин",
    "web.drug.full_check": "Полная проверка",
    "web.drug.pgx_only": "Только фармакогенетика",
    "web.drug.names_note": "Русские названия ищутся автоматически: локальная база → "
                           "международная RxNorm (перевод/действующее вещество). В сеть ходит "
                           "только второй шаг, и уходит из него ровно одно — набранное название "
                           "препарата; ни профиль, ни анализы, ни геном. Без связи отвечает одна "
                           "локальная база.",
    "web.drug.checking_full": "проверяю (в т.ч. в международной базе)…",
    "web.drug.checking": "проверяю…",
    "web.drug.found_online": "найдено онлайн",
    "web.drug.gene": "ген",
    "web.drug.resolved_online": "определён онлайн",
    "web.drug.phenotype_label": "Фенотип пациента:",
    "web.drug.discuss": "Что обсудить с врачом:",
    "web.drug.rxnorm_source": "источник: RxNorm/RxClass (международная база NLM)",
    "web.diag.no_internet": "Нет доступа в интернет из приложения",
    "web.diag.online_search_off": "Онлайн-поиск препаратов и генов сейчас недоступен:",

    # ── web: dose and critical context ───────────────────────────────────
    "web.dose.title": "Дозовый и критический контекст",
    "web.dose.subtitle": "цифры и ссылки, а не «по направлению»",
    "web.dose.doses": "Дозы: нутрицевтическая {nutritional} · фармакологическая {pharmacologic}",
    "web.dose.effect": "эффект: {text}",
    "web.dose.by_dose": "по дозе: {text}",
    "web.dose.your_numbers": "ваши цифры:",
    "web.dose.not_measured": "не сдавали",
    "web.dose.forms": "Формы: {text}",
    "web.dose.alternatives_h": "Что обсуждают как альтернативу",
    "web.dose.melatonin": "мелатонин/сон: {text}",
    "web.dose.metabolic": "метаболика: {text}",
    "web.dose.caveat": "оговорка: {text}",

    # ── web: the second opinion on one prescription ──────────────────────
    "web.rx.title": "Второе мнение: {drug}",
    "web.rx.overall": "итог: {level}",
    "web.rx.class": "класс: {name}",
    "web.rx.not_identified": "не распознан в базах",
    "web.rx.local_db": "локальная база",
    "web.rx.pgx_unchecked": "Фармакогенетика по CPIC НЕ проверялась — {why}. Это не то же самое, "
                            "что «её у препарата нет».",
    "web.rx.labs_no_rule": "Правила лабораторного контроля для этого класса ({classes}) в каталоге "
                           "нет — это не то же самое, что «контроль не нужен».",
    "web.rx.labs_class_unknown": "Класс препарата не определён, поэтому про лабораторный контроль "
                                 "сказать нечего.",
    "web.rx.no_pgx": "Значимой фармакогенетики по препарату нет (CPIC): генов, влияющих на дозу/эффект, не выявлено. Наша копия руководств от {date} — это и отличает «ничего не известно» от «сборка отстала».",
    "web.rx.curated_value": "куратор",
    "web.rx.actionable": "важен",
    "web.rx.your_phenotype": "ваш фенотип:",
    "web.rx.your_variants": "ваши варианты:",
    "web.rx.no_lab_control": "Специфического лабораторного контроля по классу не требуется.",
    "web.rx.not_taken_yet": "ещё не сдавали",
    "web.rx.monitor_while": "Контролировать при приёме: {text}",
    "web.rx.near_note": "В норме, но у границы коридора: {names} — при этом препарате следить "
                        "особенно.",
    "web.rx.watch_note": "У вас уже отклонены: {names} — это важно учесть при этом препарате.",
    "web.rx.with_yours": "с вашими:",
    "web.rx.mechanism": "механизм: {text}",
    "web.rx.what_to_do": "что делать: {text}",
    "web.rx.no_interactions_partial": "Явных взаимодействий с опознанной частью вашего текущего "
                                      "списка не найдено. НЕ сравнивалось, потому что класс не "
                                      "определён: {names}.",
    "web.rx.no_interactions": "Явных взаимодействий с вашими текущими назначениями не найдено.",
    "web.rx.via_gene": "ген {gene}",
    "web.rx.via_drug_name": "по названию препарата",
    "web.rx.genotype": "генотип {genotype}",
    "web.rx.clinvar_h": "ClinVar по препарату",
    "web.rx.clinvar_note": "ваши варианты из свежей ClinVar, связанные с этим лекарством",
    "web.rx.h_genome": "Ваш геном",
    "web.rx.h_labs": "Ваши анализы",
    "web.rx.h_meds": "Ваши назначения",

    # ── web: what to test ────────────────────────────────────────────────
    "web.tests.title": "Предложения по анализам ({n})",
    "web.tests.done": "сдано",
    "web.tests.done_why": "уже измерено ({date}) — плановый контроль, не дозаказ; повтор "
                          "ориентировочно через ~{months} мес.",
    "web.tests.specialist": "к кому: {name}",
    "web.tests.why": "зачем: {text}",
    "web.tests.none_pending": "Из того, что есть в профиле, новых назначений сейчас не "
                              "выходит. Это утверждение о правилах и об этих данных — "
                              "не о том, что вы сдавали или не сдавали.",
    "web.tests.routine_h": "Плановый контроль — уже сдано, следим по интервалу",

    # ── web: the health radar and the second look ────────────────────────
    "web.delta.unchanged": "без изменений",
    "web.delta.better": "лучше на {n}",
    "web.delta.worse": "хуже на {n}",
    "web.body.title": "Системы тела",
    "web.body.figure_h": "Фигура",
    "web.body.radar_h": "Радар",
    "web.body.hint": "Свечение — оценка системы, кольцо вокруг органа — какая доля её "
                     "маркеров измерена. Выберите систему на любой из картинок.",
    "web.body.of": "{measured} из {total}",
    "web.body.picked": "{label}: {score}/100, измерено {measured} из {total}. {where}",
    "web.body.where_organ": "Показывается на теле.",
    "web.body.where_blood": "Места на теле нет — измеряется в крови.",
    "web.body.where_whole": "Места на теле нет — относится ко всему телу.",
    "web.body.no_sex": "Пол в профиле не указан. Фигура бывает мужская или женская, "
                       "третьей нет, а угадывать нельзя: радар справа от пола не зависит.",
    "web.body.credit": "Силуэт: Servier Medical Art, CC BY 4.0",
    "web.body.place.pituitary": "гипофиз",
    "web.body.place.thyroid": "щитовидная железа",
    "web.body.place.heart": "сердце",
    "web.body.place.adrenals": "надпочечники",
    "web.body.place.liver": "печень",
    "web.body.place.pancreas": "поджелудочная железа",
    "web.body.place.kidneys": "почки",
    "web.body.place.gonads": "половые железы",
    "web.body.where_organs": "Показывается на теле: {places}.",
    "web.body.tip_part": "{dom} · {label}: {score}/100, измерено {measured} из {total}.\n"
                         "Вырабатывается: {place}.",
    "web.radar.not_enough": "Недостаточно данных для диаграммы (нужно ≥3 системы с анализами). "
                            "Загрузите анализы из папки на вкладке «Анализы».",
    "web.radar.tip": "{label}: {score}/100 ({ok}/{total} в норме)",
    "web.radar.tip_partial": "{label}: {score}/100 (в норме {ok} из {measured} измеренных; "
                             "в домене заявлено {total})",
    "web.radar.was": "было {score}/100 по {compared} показателям, у которых есть более "
                     "ранняя точка ({date}) — {word}",
    "web.radar.prev_measurement": "пред. измерение",
    "web.radar.no_previous": "нет предыдущего измерения для сравнения",
    "web.radar.now": "сейчас",
    "web.radar.previous": "прошлое измерение",
    "web.second.title": 'Радар — каждая система организма перед визитом к врачу',
    "web.second.print": "Печать / PDF",
    "web.second.overall": "Общий индекс здоровья:",
    "web.second.was": "было {score} ({date})",
    "web.second.stale_lead": "давние (не переизмерялись ≥1,5 года) — не текущий статус:",
    "web.second.vs_prev": "к прошлому измерению ({date}: {score}/100)",
    "web.second.no_current": "актуальных отклонений нет",
    "web.second.factors_h": "Важные факторы — что обсудить с врачом",
    "web.second.no_domain_issues": "Явных отклонений среди {n} систем, по которым хватило "
                                   "данных, нет.",
    "web.second.no_domain_data": "Ни по одной системе пока не хватает измерений для суждения. "
                                 "Радар показывает форму; вердикты ждут данных.",
    "web.second.print_title": "Scholion — материал к разговору, подготовлен дома",
    "web.second.print_name": "ФИО",
    "web.second.print_dob": "Дата рождения",
    "web.second.print_date": "Дата",
    "web.second.print_foot": "Этот лист сформирован на личном компьютере пациента из файлов, "
                             "которые ведёт сам пациент. Это не бланк лаборатории, номера "
                             "исследования у него нет: любое значение отсюда стоит сверить с "
                             "оригиналом, прежде чем на него опираться. Это не диагноз и не "
                             "назначение; лист ни о чём не просит, кроме как рассмотреть "
                             "заданные в нём вопросы.",
    "web.second.pgx_h": "Фармакогенетика — на будущее",
    "web.second.no_drug_flags": "Ни один из {n} препаратов списка наблюдения, для которых нашёлся "
                                "генотип, флага не дал.",
    "web.second.pgx_basis": "По имеющимся генотипам можно судить о {k} из {n}. Остальные "
                            "печатают общее правило для препарата — не утверждение о вас.",
    "web.second.pgx_basis_none": "Ни об одном из {n} по имеющимся генотипам судить нельзя: ниже "
                                 "общее правило для каждого препарата, а не утверждение о вас.",
    "web.second.no_drug_data": "Ни один из {n} препаратов списка наблюдения оценить не по чему — "
                               "генотипов для нужных генов в профиле нет. Это утверждение о "
                               "данных, а не о препаратах.",
    "web.second.tests_h": "Что имеет смысл сдать",
    "web.second.by_system_h": "По системам организма — что вне коридора, что на систему действует, что спросить",
    "web.second.genetics_lead": 'В каждом блоке есть и генетическая половина системы: список генов из выгрузки Gene Curation Coalition (кто заявил связь, с какой силой, при каком наследовании), и сколько из него прочитано в этом геноме — никогда внутри индекса 0–100 и вердикта. Полигенные баллы остаются на вкладке «Геном». Если геном не полный, блок говорит, что добавил бы полный.',
    "web.second.systems_silent": "ничего открытого по: {systems}",
    "web.second.tests_all_placed": "каждое ожидающее предложение стоит в блоке своей системы выше",
    "web.second.routine_elsewhere": "Ещё {n} — плановый контроль: уже сдано, следим по интервалу. "
                                    "Они на вкладке",

    # ── предложение цели ─────────────────────────────────────────────────
    "goalgen.why.guideline": "{body} публикует этот ориентир ({year}).",
    "goalgen.why.guideline_conditional": "{body} публикует этот ориентир ({year}) для людей "
                                         "с состоянием «{condition}». Относится ли это к "
                                         "вам — по профилю не подтвердить.",
    "goalgen.why.no_target": "{body} рассмотрело этот маркёр и отказалось задавать целевое "
                             "значение. Это и есть вывод, а не пробел — числа здесь не "
                             "предлагается.",
    "goalgen.why.personal_best": "Лучшее, чего вы достигали — {date}, из {readings} за {months} мес. Это не чья-то рекомендация, это ваши собственные измерения.",
    "goalgen.why.reference": "Стенка лабораторного коридора. Слабее двух других: «внутри "
                             "нормы» — это то, где большинство и так находится, а не цель.",
    "goalgen.how_to_read": "Это предложение, а не назначение. Там, где клиническая ассоциация "
                           "опубликовала ориентир, он приведён с источником; иначе предлагается "
                           "ваш собственный лучший результат — факт о вас, а не совет. Любое "
                           "можно изменить, а важное — обсудить с врачом.",
    "goalgen.skip.no_series": "ничего не измерено",
    "goalgen.skip.no_direction": "в каталоге не записано, какое направление лучше для этого "
                                 "маркёра, поэтому цель не предлагается вовсе — вместо цели, "
                                 "направленной не туда",
    "goalgen.skip.too_few_points": "меньше трёх измерений — это не тренд",
    "goalgen.skip.too_short_a_window": "все измерения укладываются в шесть месяцев",
    "goalgen.skip.already_there": "лучшее значение там же, где текущее",
    "goalgen.skip.society_withdrew_the_target": "ассоциация отозвала свой ориентир",
    "goalgen.skip.nothing_to_go_on": "ни опубликованного ориентира, ни пригодного ряда, ни коридора",
    "goalgen.title": "Предложенные цели",
    "goalgen.none": "Пока ничему здесь нельзя назначить цель. Загрузите ещё анализов — и ответ "
                    "будет другим.",
    "goalgen.skipped_h": "Для чего цель не предложена и почему",
    "goalgen.src.guideline": "клиническое руководство",
    "goalgen.src.personal_best": "ваш собственный максимум",
    "goalgen.src.reference": "лабораторный коридор",
    "web.goalgen.h": "Пусть приложение предложит цель",
    "web.goalgen.intro": "Оно читает то, что вы измерили, и то, что публикуют клинические "
                         "ассоциации, и предлагает ориентир для каждого маркёра, для которого "
                         "хватает оснований. Каждая строка говорит, откуда взято число. Пока не "
                         "нажмёте «Сохранить», ничего не записывается.",
    "web.goalgen.btn": "Предложить цель",
    "web.goalgen.save": "Сохранить отмеченные",
    "web.goalgen.saved": "Записано в profile/health_goals.json — целей: {n}.",
    "web.goalgen.now": "сейчас",
    "web.goalgen.reached": "вы здесь уже были",
    "web.goalgen.pick": "источник",

    # ── генетическая составляющая липидного профиля (PCSK9 + Лп(а)) ──────
    "lipidgen.title": "Генетическая составляющая липидного профиля",
    "lipidgen.headline.carrier": "Носительство защитного варианта потери функции PCSK9 есть. "
                                 "Часть картины по ЛПНП — наследственность, а не привычки; это "
                                 "объясняет низкое значение, но не заменяет его измерение.",
    "lipidgen.headline.not_carrier": "Защитного варианта PCSK9 среди прочитанных нет. Это обычный "
                                     "ответ, а не находка: значит, измеренный ЛПНП стоит сам за себя.",
    "lipidgen.headline.unread": "Позиции PCSK9 не прочитаны, поэтому сказать о них пока нечего — "
                                "и это не то же самое, что «там ничего нет».",
    "lipidgen.headline.no_genome": "Геном сейчас не читается, поэтому о PCSK9 не сказано ничего — ни «есть», ни «нет». Причина и что с ней делать — в состоянии генома наверху вкладки.",
    "lipidgen.how_to_read": "Два факта, которые по отдельности читаются неверно. Носительство "
                            "варианта потери функции PCSK9 говорит, какая часть картины по ЛПНП "
                            "задана при рождении. Лп(а) не виден остальной липидограмме — он тоже "
                            "задан при рождении, не двигается вместе с тем, с чем двигается ЛПНП, "
                            "и нормальная панель при высоком Лп(а) — это нормальная панель, "
                            "прошедшая мимо находки. Ни то, ни другое не расчёт риска и не повод "
                            "начинать или отменять терапию.",
    "lipidgen.copies.0": "не носитель — буфера от этого варианта нет; измеренный ЛПНП стоит сам за себя",
    "lipidgen.copies.1": "одна копия — пожизненно более низкий ЛПНП и заметно меньший риск ИБС",
    "lipidgen.copies.2": "две копии — тот же эффект, сильнее; очень редко, и стоит подтвердить другим методом",
    "lipidgen.lpa.h": "Липопротеин(а)",
    "lipidgen.lpa.order_it": "Не измерен. Лп(а) имеет смысл измерить ОДИН раз в жизни — уровень "
                             "в основном задан при рождении и дальше почти не меняется — и момент "
                             "для этого ДО решения о липидснижающей терапии, а не после. Просить "
                             "в нмоль/л: пересчёт из мг/дл неточен, потому что размер изоформы "
                             "апо(a) у разных людей разный.",
    "lipidgen.lpa.estimate_limit": "Полигенная оценка Лп(а) — это генетическая ОЦЕНКА, и заменить "
                                   "измерение она не может. Уровень определяется в основном числом "
                                   "повторов KIV-2 внутри LPA — это структурный вариант "
                                   "числа копий, который короткие чтения и SNP-чипы видят плохо. "
                                   "Пометка «Moderate» у этой модели в каталоге — это и есть тот "
                                   "предел, а не недоработка каталога.",
    "lipidgen.lpa.measured": "измерено {value} {unit} · {date}",
    "lipidgen.lpa.above": "выше границы {ref}",
    "lipidgen.waiting_h": "Прочитано, но здесь не интерпретируется",
    "lipidgen.unread": "не прочитано",
    "lipidgen.carrier": "носитель",
    "lipidgen.not_carrier": "не носитель",
    "web.genome.lipidgen_h": "Липиды — то, что унаследовано",
    "web.genome.nav_lipids": "Липиды",

    # ── web: prescriptions ───────────────────────────────────────────────
    "web.meds.title": "Назначения (редактируемые)",
    "web.meds.note": "Добавленные тут назначения идут в medications.json и участвуют в сверке и "
                     "предложениях анализов. Полная схема врача — в medications.md.",
    "web.meds.drug": "Препарат",
    "web.meds.drug_placeholder": "напр. Аторвастатин",
    "web.meds.dose": "Доза",
    "web.meds.dose_placeholder": "20 мг",
    "web.meds.comment": "Заметка",
    "web.meds.comment_placeholder": "показание/комментарий",
    "web.meds.status": "Статус",
    "web.meds.status_active": "принимается",
    "web.meds.status_paused": "пауза",
    "web.meds.status_stopped": "отменён",
    "web.meds.not_current": "не текущее: {status}",
    "web.meds.add": "Добавить",
    "web.meds.remove": "удалить",
    "web.meds.empty": "Пока пусто.",
    "web.meds.enter_name": "Введите препарат",
    "web.meds.added_attention": "Добавлено — есть на что обратить внимание",
    "web.meds.removed": "Удалено",

    # ── web: personal metrics ────────────────────────────────────────────
    "web.metrics.device_label": "Основное устройство",
    "web.metrics.device_none": "Нет носимого устройства",
    "web.metrics.profile_note2": "Это предпосылки, которые приложение не может вывести и не станет придумывать. Без пола десяток референсных интервалов не показывается, а не угадывается; без года рождения не читаются возрастные строки бланка; без роста нет ИМТ; а там, где одно и то же измерили два прибора, отвечает названный здесь. «Нет устройства» — тоже ответ, и больше об этом не спросят.",
    "web.metrics.panel_label": "Референсная панель для перцентилей",
    "web.metrics.panel_from_genome": "{value} — определена по вашему геному ({date})",
    "web.metrics.panel_stated": "{value} — задана вручную, поверх того, что говорит геном",
    "web.metrics.panel_unknown": "не определена — перцентили считаются по панели по умолчанию и говорят об этом. Она выясняется при подготовке генома, а не ответом на вопрос здесь.",
    "web.metrics.missing_head": "Ещё не записано — и чего это стоит",
    "web.metrics.title": "Личные показатели здоровья",
    "web.metrics.sex": "пол",
    "web.metrics.sex_label": "Пол",
    "web.metrics.male": "муж",
    "web.metrics.female": "жен",
    "web.metrics.age": "возраст",
    "web.metrics.height": "рост, см",
    "web.metrics.height_label": "Рост, см",
    "web.metrics.bmi": "ИМТ",
    "web.metrics.profile_btn": "Поля профиля",
    "web.metrics.add_btn": "Добавить измерение",
    "web.metrics.birth_year": "Год рождения",
    "web.metrics.profile_note": "Идёт в metrics.json (profile). ИМТ считается из роста и "
                                "последнего веса.",
    "web.metrics.profile_saved": "Профиль сохранён ✓",
    "web.metrics.name_placeholder": "ВСР",
    "web.metrics.add_note": "Идёт в metrics.json (profile). Тренды и ИМТ обновятся сразу.",

    # ── web: the bullet board "now → goal" ───────────────────────────────
    "web.bullet.title": "Сейчас → цель",
    "web.bullet.good": "цель достигнута или в норме",
    "web.bullet.warn": "в коридоре нормы, но до цели не дошло",
    "web.bullet.crit": "вне референсного коридора",
    "web.bullet.none": "нет данных",
    "web.bullet.no_target": "цели нет",
    "web.bullet.target": "цель {value}",
    "web.bullet.src_goal": "заданная вами цель",
    "web.bullet.src_ref": "граница коридора лаборатории",
    "web.bullet.src_norm": "общая рекомендация",
    "web.bullet.src_own": "выведено из ваших собственных данных",
    "web.bullet.legend_notch": "засечка — цель",
    "web.bullet.legend_zone": "зона цели",
    "web.bullet.group.body": "Состав тела",
    "web.bullet.group.metabolism": "Метаболизм",
    "web.bullet.group.bones": "Кости",
    "web.bullet.group.fitness": "Форма и восстановление",
    "web.bullet.group.other": "Прочее",
    # The `match` lists below are NOT text: they are the labels as they arrive from the
    # profile, and the page groups the rows by matching them. They read the same in every
    # language on purpose — translating them would break the grouping, not the wording.
    "web.bullet.match.body": "Вес|Доля жира|Мышечная масса|ИМТ",
    "web.bullet.match.metabolism": "HOMA-IR|Инсулин натощак|Триглицериды|ЛПНП|Аполипопротеин "
                                   "B|Мочевая кислота",
    "web.bullet.match.bones": "Ионизир. кальций|Остеокальцин|Паратгормон|25-OH витамин D3",
    "web.bullet.match.fitness": "VO₂max|Пульс покоя|ВСР (rMSSD)|Шаги в день|Сон|Глубокий сон|Время "
                                "засыпания",
    "web.bullet.match.hero": "Доля жира|Мышечная масса|HOMA-IR",

    # ── web: lifestyle ───────────────────────────────────────────────────
    "web.life.title": "Образ жизни",
    "web.life.ok": "в норме",
    "web.life.warn": "внимание",
    "web.life.bad": "ниже цели",
    "web.life.none": "—",
    "web.life.stable": "стабильно",
    "web.life.trend_3m": "{delta} за 3 мес",
    "web.life.card_meta": "послед. {date} · сглаж. {smooth} · с {since}",
    "web.life.rebuilding": "пересобираю…",
    "web.life.garmin_done": "Garmin обновлён: {metrics} метрик ({range})",
    "web.life.garmin_nights": "ночей сна {n}",
    "web.life.garmin_preserved": "сохранено из прежнего файла: {n}",
    "web.life.fitness_score": "балл формы /100",
    "web.life.hero": "{label} · цель {target}",
    "web.life.no_wearable": "Данных носимых устройств пока нет (profile/wearable_trends.json).",
    "web.life.shifted_h": "Что сдвинулось за 3 месяца",
    "web.life.right_way": "В нужную сторону:",
    "web.life.needs_attention": "Требует внимания:",
    "web.life.no_trends": "Пока недостаточно данных для трендов.",
    "web.life.waist": "Талия, см",
    "web.life.waist_placeholder": "напр. 104",
    "web.life.date": "Дата",
    "web.life.date_placeholder": "ГГГГ-ММ-ДД",
    "web.life.waist_save": "Записать",
    "web.life.waist_note": "единственный показатель для ручного ввода → в metrics.json",
    "web.life.waist_metric": "Талия",
    "web.life.waist_unit": "см",
    "web.life.enter_waist": "Введите объём талии, см",
    "web.life.group_anthro": "Антропометрия и состав тела",
    "web.life.group_activity": "Активность",
    "web.life.group_recovery": "Восстановление и вегетатика",
    "web.life.workouts_h": "Тренировки за всё время",
    "web.life.wk_last_year": "последний год: {year}",
    "web.life.wk_hours_total": "{hours} ч всего",
    "web.life.wk_hours": "{hours}ч",

    # ── web: the lifestyle brief ─────────────────────────────────────────
    "web.brief.sections_h": "Разбор — почему именно так",
    "web.brief.review_badge": "пересмотреть",
    "web.brief.actions_h": "Что сделать",
    "web.brief.needs_review": "справка требует пересмотра",
    "brief.review.status.ok": "в норме",
    "brief.review.status.low": "ниже нормы",
    "brief.review.status.high": "выше нормы",
    "brief.review.status.unknown": "без нормы",
    "brief.review.value": "{value}{unit} от {date}, {status}",
    "brief.review.no_before": "замеров до этого не было",
    "brief.review.row": "{name}: {before} → {after}",
    "brief.review.no_brief": "В этом профиле нет справки по образу жизни.",
    "brief.review.no_block": "В справке нет блока «{block}».",
    "brief.review.nothing": "Ни один блок справки не требует пересмотра.",
    "brief.review.no_changes": "ни у одного маркёра этого блока нет замеров после этой даты",
    "brief.review.title": "Пересмотр «{title}» (блок {block})",
    "brief.review.reviewed": "Формулировку проверяли {reviewed}; самый свежий наблюдаемый замер — от {newest}.",
    "brief.review.request_h": "Задание для ассистента:",
    "brief.review.request": "Пересмотрите, пожалуйста, один блок моей справки по образу жизни (profile/lifestyle_brief.json): блок «{block}», «{title}».\n\nЕго формулировку последний раз проверяли {reviewed}. С тех пор пришли такие замеры маркёров, за которыми он следит:\n{changes}\n\nНа что смотреть, словами автора: {hint}\n\nТекущая формулировка с живыми токенами:\n{body}\n\nРешите, следует ли его вывод из этих замеров. Если да — скажите об этом и поставьте этому блоку «reviewed» сегодняшней датой. Если нет — перепишите только этот блок: сохраните все токены {{{{lab:…}}}}, чтобы числа оставались живыми, не пишите чисел руками, сохраните оговорки и поставьте «reviewed» сегодняшней датой.",
    "web.brief.review_btn": "Проверить",
    "web.brief.review_all": "Проверить, что изменилось",
    "web.brief.review_h": "Что пришло после проверки формулировки {reviewed}",
    "web.brief.review_moved": "перешёл из «{from}» в «{to}»",
    "web.brief.review_explain": "Числа внутри блока обновляются сами; пересмотр решает, следует ли из этих замеров его вывод. Если да — нажмите «Формулировка по-прежнему верна». Если нет — передайте блок ассистенту с заданием ниже.",
    "web.brief.review_copy": "Скопировать задание для ассистента",
    "web.brief.review_copied": "Задание в буфере обмена. В нём ваши данные — вставляйте его только туда, где готовы их хранить.",
    "web.brief.review_copy_failed": "Буфер обмена закрыт для этой страницы; задание показано ниже — выделите его и скопируйте.",
    "web.brief.new_data": "Появились новые данные после последней правки формулировок:",
    "web.brief.block_dates": "текст от {reviewed}, данные от {newest}",
    "web.brief.still_true": "Формулировка всё ещё верна",
    "web.brief.numbers_note": "Числа пересчитаны автоматически — пересмотра требуют выводы. "
                              "Попросите ассистента обновить справку.",
    "web.brief.dropped_h": "Снятые тревоги — чего делать не надо",
    "web.brief.compiled": "Формулировки от {date}; числа подставляются из профиля при каждом "
                          "открытии.",

    # ── web: genome ──────────────────────────────────────────────────────
    "web.genome.title": "Геном — комплексный анализ",
    "web.genome.nav_findings": "Находки",
    "web.genome.nav_sources": "Источники",
    "web.genome.findings_none": "Находок нет: либо геном не читается, либо ни один источник ничего не отметил. Что именно — сказано в состоянии генома наверху.",
    "web.genome.findings_note": "Порядок — по тому, что с находкой можно сделать, а не по источнику. Клик по гену собирает всё, что о нём известно, в одну карточку.",
    "web.common.close": "закрыть",
    "web.genome.nav_summary": "Сводка",
    "web.genome.nav_updates": "Обновления",
    "web.genome.nav_risks": "Риски (PGS)",
    "web.genome.nav_longevity": "Долголетие",
    "web.genome.nav_clinvar": "ClinVar",
    "web.genome.nav_locus": "Поиск локуса",
    "web.genome.pick_h": "В папке несколько файлов — какой из них ваш геном?",
    "web.genome.pick_why": "Пока выбор не сделан, не читается ни один локус: разделы ниже пусты не потому, что в геноме ничего нет. Выбор сохраняется и больше не спросится.",
    "web.genome.pick_btn": "Это мой геном",
    "web.genome.chosen_gone": "Выбранного файла больше нет на месте: {path}",
    "web.genome.set_aside": "Отложено как выборка из генома:",
    "web.genome.why.sites_only": "прочитано по списку позиций",
    "web.genome.why.annotated_copy": "копия с аннотацией",
    "web.genome.why.declared": "помечено как производное",
    "web.genome.assembly": "сборка {name}",
    "web.genome.sample": "образец {name}",
    "web.genome.db_connected": "база подключена",
    "web.genome.db_not_connected": "база не подключена",
    "web.genome.db_after_script": "геномная часть отвечает, когда подключён полный VCF — "
                                 "как его получить, описано в "
                                 "`scholion doc preparing-the-genome`",
    "web.genome.path_open": "{name} — открыто",
    "web.genome.path_closed": "{name} — закрыто: {why}",
    "web.genome.intro": "Всё про геном на одной вкладке: находки первыми, дальше — источники, из которых они взяты. Ничего не уходит с машины. Не диагноз — материал для врача.",
    "web.genome.updates_h": "Обновления баз",
    "web.genome.updates_note": "сверить геном со свежей ClinVar и показать, что нового",
    "web.genome.prs_h": "Полигенные риски (PGS)",
    "web.genome.longevity_h": "Долголетие",
    "web.genome.clinvar_h": "Клинически значимые находки (ClinVar)",
    "web.genome.locus_h": "Поиск любого локуса",
    "web.genome.locus_placeholder": "rsID, напр. rs4149056",
    "web.genome.find": "Найти",
    "web.genome.unknown_gene": "Ген не найден в справочнике координат.",
    "web.genome.loci": "локусы:",
    "web.genome.genotype": "генотип",
    "web.genome.coverage": "покрытие {value}",
    "web.genome.assumed_ref": "строки на этой позиции нет — референс или не прочитано",

    # ── web: polygenic scores ────────────────────────────────────────────
    "web.prs.not_ready": "Полигенные баллы ещё не рассчитаны.",
    "web.prs.above_average": "выше среднего в популяции ({pop})",
    "web.prs.low_coverage": "покрытие ниже 90% — ориентировочно",
    "web.prs.stat_traits": "признаков",
    "web.prs.stat_reliable": "надёжных",
    "web.prs.stat_high": "выше среднего (≥80)",
    "web.prs.scale_note": "Шкала — позиция в популяции (0–100 перцентиль), НЕ вероятность болезни.",
    "web.prs.high_h": "Заметно выше среднего (скрининг)",
    "web.prs.all_h": "Все признаки по категориям",
    "web.prs.legend": "Зелёный ≤20 · синий середина · оранжевый ≥80.",
    "web.prs.no_model": "нет модели",

    # ── web: longevity ───────────────────────────────────────────────────
    "web.longevity.not_ready": "Слой долголетия ещё не построен.",
    "web.longevity.apoe_status": "APOE — статус",
    "web.longevity.apoe_favourable": "Благоприятный генотип: ниже риск Альцгеймера, ассоциирован с "
                                     "долголетием, обычно снижает ЛПНП.",
    "web.longevity.apoe_e4": "Есть ε4-компонент — повышенный риск Альцгеймера/ССЗ; обсудить с "
                             "врачом.",
    "web.longevity.apoe_generic": "ε2/ε3/ε4 определяют по этим двум SNP.",
    "web.longevity.what_is_apoe": "APOE — самый изученный ген этого слоя: одна и та же пара позиций определяет и вариант, связанный с риском болезни Альцгеймера, и вариант, который чаще встречается у долгожителей. Это фактор, а не диагноз, и он ничего не говорит о том, что уже произошло.",
    "web.longevity.technical": "Как это посчитано",
    "web.longevity.stored_note": "Заметка, записанная при построении слоя",
    "web.longevity.action_h": "Что с этим делать",
    "web.longevity.no_action": "ничего делать не нужно — это знание, а не назначение",
    "web.longevity.found_h": "Что нашлось",
    "web.longevity.quiet_h": "Проверено и без эффекта в эту сторону",
    "web.longevity.nothing_found": "Ни один из проверенных маркёров не дал носительства в сторону долголетия. Это обычный ответ, а не находка.",
    "web.longevity.confidence.curated": "источник: наш выверенный каталог",
    "web.longevity.confidence.high": "источники: сильные",
    "web.longevity.confidence.medium": "источники: средние",
    "web.longevity.confidence.low": "источники: слабые",
    "web.longevity.carries": "несёт аллель",
    "web.longevity.stat_checked": "вариантов проверено",
    "web.longevity.stat_carrier": "значимых-носитель",
    "web.longevity.stat_genes": "генов",
    "web.longevity.key_markers_h": "Ключевые маркёры",
    "web.longevity.by_gene_h": "Значимые носительства по генам",
    "web.longevity.by_gene_note": "Литературный каталог: вы носитель варианта, изучавшегося при "
                                  "долголетии. Направление большинства ассоциаций не закодировано "
                                  "— навигатор по генам, не оценка риска.",

    # ── web: ClinVar findings ────────────────────────────────────────────
    "web.clinvar.not_run": "ClinVar-аннотация ещё не запускалась.",
    "web.clinvar.nothing": "Значимых находок не извлечено",
    "web.clinvar.experts": "эксперты",
    "web.clinvar.several_labs": "неск. лабораторий",
    "web.clinvar.actionable_of": "действенных находок из {total}",
    "web.clinvar.intro": "Ваши варианты, размеченные свежей ClinVar. Важное сверху: {pathogenic} "
                         "(носительство/болезнь), {pgx} (лекарства), {risk}. Остальные {n} "
                         "(слабые/неоднозначные) — под катом, обычно не риск. Не диагноз.",
    "web.clinvar.w_pathogenic": "патогенные",
    "web.clinvar.w_pgx": "фармакогенетика",
    "web.clinvar.w_risk": "факторы риска",
    "web.clinvar.show_weak": "Показать слабые и неоднозначные ({n})",

    # ── web: checking the databases for updates ──────────────────────────
    "web.updates.never": "Проверок ещё не было. Нажмите «Обновить ClinVar» — приложение сверит "
                         "ваш геном со свежей ClinVar и покажет, что нового.",
    "web.updates.last_check": "Последняя проверка:",
    "web.updates.nothing_new": "Ничего нового с прошлой проверки.",
    "web.updates.new_h": "Новые находки ({n})",
    "web.updates.changed_h": "Изменилась классификация ({n})",
    "web.updates.check_btn": "Обновить ClinVar",
    "web.updates.in_progress": "идёт проверка…",
    "web.updates.downloading": "Скачиваю свежую ClinVar и сверяю с вашим геномом — это несколько "
                               "минут.",
    "web.updates.failed": "Проверка не завершилась (код {code}).",

    # ── web: the assistant tab ───────────────────────────────────────────
    "web.assistant.title": "Ассистент — необязательный слой",
    "web.assistant.works_without": "приложение работает без ассистента",
    "web.assistant.everything_local": "Все числа, флаги, тренды, фармакогенетика, «второе мнение» "
                                      "и чеклист следующего забора считаются кодом на вашей "
                                      "машине. Ни интернет, ни языковая модель для этого не нужны.",
    "web.assistant.scan_lead": "Проверено сканом собственного кода при открытии этой страницы:",
    "web.assistant.network_lead": "Приложение может обратиться наружу только по вашей команде, и "
                                  "уходит при этом сам запрос — название препарата, rsID, — а не "
                                  "профиль и не геном:",
    "web.assistant.ingest_hosts": "Скрипты подготовки данных, которые вы запускаете руками (сборка "
                                  "генома, обновление справочников), скачивают с: {hosts}.",
    "web.assistant.engine_does": "Считает код",
    "web.assistant.adds": "Добавляет ассистент",
    "web.assistant.curated_h": "Тексты, которые пишет ассистент",
    "web.assistant.curated_note": "Формулировки курирует ассистент, числа в них подставляет движок "
                                  "в момент показа — поэтому цифры в этих текстах не устаревают, а "
                                  "формулировка помечается как требующая пересмотра, когда "
                                  "появляются данные новее её.",
    "web.assistant.connect_h": "Как подключить модель",
    "web.assistant.connected": "подключён",
    "web.assistant.ready": "готов к подключению",
    "web.assistant.missing": "не найден",
    "web.assistant.absent": "нет",
    "web.assistant.stale": "нужен пересмотр",
    "web.assistant.fresh": "свежий",
    "web.assistant.updated": "обновлено {date}",
    "web.assistant.no_date": "даты нет",
    "web.assistant.tab_of": "вкладка «{tab}»",
    "web.assistant.review_blocks": "пересмотреть: {blocks}",
    "web.assistant.collect_btn": "Собрать контекст и скопировать",
    "web.assistant.context_warning": "Собранный текст содержит ваши персональные медицинские "
                                     "данные — вставляйте его только туда, где вы согласны их "
                                     "хранить.",
    "web.assistant.collecting": "собираю…",
    "web.assistant.collect_failed": "не получилось",
    "web.assistant.copied": "скопировано в буфер",
    "web.assistant.collected": "{chars} символов · сохранено: {path}",
    "web.assistant.toast_clipboard": "Контекст в буфере — вставьте в диалог с моделью",
    "web.assistant.toast_file": "Контекст сохранён в файл",

    # ── web: вкладка «Справочник» ────────────────────────────────────────
    "web.tab.guide": "Справочник",
    "web.guide.title": "Справочник",
    "web.guide.intro": "Что показывает каждый экран приложения — в одном месте, чтобы не "
                       "оставалось непонятного только из-за того, что исходники не под рукой. "
                       "Здесь описан сам интерфейс: цвета, подписи, термины. Что означают "
                       "именно ваши числа — написано на том экране, где они показаны, рядом "
                       "с числом.",

    "web.guide.sources_h": "Откуда взято число",
    "web.guide.sources_body": "Каждая страница заканчивается строкой источников. Раскройте её — там видно, откуда взяты данные: из ваших файлов на этой машине или из публичной справочной базы, к которой обратились по сети (ClinVar, RxClass, Ensembl). Ничего не утверждается без одного из этих двух источников, и они никогда не окрашены одинаково. Подключена ли на странице «Ассистент» языковая модель или нет — на это не влияет: числа всегда считает код на вашей машине.",

    "web.guide.status_h": "Цвета и значки",
    "web.guide.status_intro": "Одни и те же пять значков повторяются почти на каждой странице. Цвет никогда не бывает единственным сигналом — рядом всегда стоит число и подпись, так что значок остаётся читаемым, даже если цвет неразличим.",
    "web.guide.status_good_label": "норма",
    "web.guide.status_good_why": "Цель достигнута, или цели нет, а значение — внутри "
                                 "референсного коридора.",
    "web.guide.status_warning_label": "внимание",
    "web.guide.status_warning_why": "Внутри референсного коридора, но личная цель ещё не "
                                    "достигнута — либо фармакогенетический эффект, о котором "
                                    "стоит помнить, но не тревожный сигнал.",
    "web.guide.status_critical_label": "критично",
    "web.guide.status_critical_why": "Вне референсного коридора лаборатории, либо тревожный "
                                     "сигнал, поднятый из вашего же профиля.",
    "web.guide.status_near_label": "у границы",
    "web.guide.status_near_why": "Формально внутри нормы, но у самой её стенки. Показано синим, "
                                 "а не жёлтым, намеренно — чтобы человек с нарушением "
                                 "цветовосприятия видел отличие от «внимания» в самом тоне, а не "
                                 "только в подписи.",
    "web.guide.status_unknown_label": "нет данных",
    "web.guide.status_unknown_why": "Пока не о чем судить — не измерено, либо не найдено в "
                                    "ваших файлах.",
    "web.guide.status_three_note": "Само суждение использует три уровня, а не пять: норма, "
                                   "внимание, критично. Четвёртый, почти неотличимый уровень "
                                   "пробовали и отказались от него — при обычном контрасте он "
                                   "неотличим от «внимания» для обычного зрения. «У границы» и "
                                   "«нет данных» — не уровни тяжести; они отмечают другое: "
                                   "положение значения или его отсутствие.",

    "web.guide.tour_h": "Что на каждой странице",
    "web.guide.tour_overview": "Весь человек на одном экране: ключевые числа, системы тела и фигура, что вне нормы сейчас, что сдать, то единственное, над чем идёт работа, цель — и в конце чьи это данные и собственные показатели. Каждый раздел называет вкладку, которой принадлежит.",
    "web.guide.tour_labs": "Каждый сданный анализ, сверенный со своим референсным диапазоном, "
                           "с трендом там, где измерений достаточно.",
    "web.guide.tour_genome": "Полигенные риски как перцентили в популяции, варианты, связанные "
                             "с долголетием, находки ClinVar в вашем геноме, проверка на то, "
                             "что изменилось со времени последнего чтения ClinVar, и поиск по "
                             "гену или rsID.",
    "web.guide.tour_lifestyle": "Показатели с носимых устройств на фоне личной цели, полоса "
                                "«сейчас → цель» по каждому показателю и история тренировок.",
    "web.guide.tour_second_opinion": "Фигура и радар, указатель систем и по блоку на систему: вывод одной фразой, измерения таблицей, находки в генотипе и согласуются ли они с измерениями, вопросы врачу; остальное свёрнуто в «Подробнее». В каждом блоке две кнопки: карточка системы и панель с исследованиями для врача. Печатается как лист на приём.",
    "web.guide.tour_assistant": "Подключена ли языковая модель, что ей можно и нельзя видеть, "
                                "и как её подключить, если хочется более развёрнутых "
                                "формулировок поверх тех же чисел.",

    "web.guide.terms_h": "Термины",
    "web.guide.term_prs_label": "PRS, перцентиль",
    "web.guide.term_prs_body": "Полигенный балл, переведённый в позицию в референсной "
                               "популяции, от 0 до 100. Не диагноз и не вероятность болезни — "
                               "перцентиль говорит только о месте в распределении, не больше. "
                               "Построен в основном на когортах европейского происхождения; вне "
                               "этой популяции точность перцентиля ниже.",
    "web.guide.term_pgx_label": "Фармакогенетика (PGx)",
    "web.guide.term_pgx_body": "Как собственный генотип в нескольких хорошо изученных генах "
                               "(CYP2C9, CYP2C19, SLCO1B1 и другие) меняет вероятный характер "
                               "обработки конкретного препарата организмом — быстрее, "
                               "медленнее, либо с повышенным риском побочного эффекта. "
                               "Фармакогенетический флаг — повод задать врачу конкретный "
                               "вопрос, а не инструкция менять дозу самостоятельно.",
    "web.guide.term_clinvar_label": "Категории ClinVar",
    "web.guide.term_clinvar_body": "Находки в геноме сгруппированы по тому, что о них говорит "
                                   "ClinVar: патогенные (вызывающие болезнь), связанные с "
                                   "реакцией на препарат, факторы риска или защитные — "
                                   "показаны первыми; неопределённая значимость и просто "
                                   "ассоциации — самые слабые, наименее применимые на практике "
                                   "категории — спрятаны за «показать ещё», чтобы не заслонять "
                                   "остальное.",
    "web.guide.term_confidence_label": "Надёжность чтения генома",
    "web.guide.term_confidence_body": "Генотип может быть вызван напрямую из данных "
                                      "секвенирования, либо — в позиции без известного варианта "
                                      "— подтверждён как референс явным вызовом 0/0, что не то "
                                      "же самое, что позиция, которой в файле попросту нет. "
                                      "Низкое покрытие в вызванной позиции отмечено на месте, "
                                      "рядом с числом, на которое оно влияет.",
    "web.guide.term_sources_label": "Локальное и публичное",
    "web.guide.term_sources_body": "«Локальное» — это файл, уже лежащий на этой машине: ваши "
                                   "анализы, ваш геном, ваши назначения. «Публичное» — "
                                   "справочная база, к которой обращаются по сети, чтобы их "
                                   "истолковать: ClinVar — для значимости вариантов, RxClass — "
                                   "для классов препаратов, Ensembl — для координат. Движок "
                                   "никогда не отправляет содержимое ваших файлов в публичный "
                                   "источник — только запрос, например название препарата или "
                                   "rsID.",

    "web.guide.footer": "У каждого экрана есть собственная оговорка о том, что он может "
                        "сказать, а что нет. Эта страница — карта по интерфейсу, а не замена "
                        "этим оговоркам, и не медицинская консультация.",

    # ── web: workout types (the key is the identifier Garmin sends) ──────
    "web.workout.Running": "Бег",
    "web.workout.Tennis": "Теннис",
    "web.workout.Swimming": "Плавание",
    "web.workout.Cycling": "Велосипед",
    "web.workout.Walking": "Ходьба",
    "web.workout.Hiking": "Хайкинг",
    "web.workout.SnowSports": "Лыжи/сноуборд",
    "web.workout.HighIntensityIntervalTraining": "Силовые тренировки",
    "web.workout.TraditionalStrengthTraining": "Силовые тренировки",
    "web.workout.FunctionalStrengthTraining": "Функциональная",
    "web.workout.Pickleball": "Пиклбол",
    "web.workout.Golf": "Гольф",
    "web.workout.Rowing": "Гребля",
    "web.workout.Yoga": "Йога",
    "web.workout.Pilates": "Пилатес",
    "web.workout.MindAndBody": "Разум-тело",
    "web.workout.MixedCardio": "Кардио",
    "web.workout.Elliptical": "Эллипс",
    "web.workout.PaddleSports": "Падл",
    "web.workout.Other": "Прочее",

    # ── the local server: what it answers a request with ─────────────────
    "server.pick.labs": "Выберите папку с файлом labs.json",
    "server.pick.labs_docs": "Выберите папку с PDF лабораторных исследований",
    "server.pick.medications": "Выберите папку с назначениями врача",
    "server.pick.med_docs": "Выберите папку с PDF назначений врача",
    "server.pick.metrics": "Выберите папку с показателями здоровья",
    "server.pick.genome": "Выберите папку с геномными данными (VCF)",
    "server.pick.default": "Выберите папку с данными",
    "server.pick.macos_only": "Нативный диалог доступен только на macOS — впишите путь вручную.",
    "server.pick.failed": "не удалось открыть диалог",
    "server.pick.empty_path": "пустой путь",
    "server.deny.foreign_host": "запрос адресован не локальному имени",
    "server.deny.cross_site": "межсайтовый запрос отклонён",
    "server.bad_content_length": "некорректный Content-Length",
    "server.body_too_large": "тело запроса больше {bytes} байт",
    "server.internal_error": "внутренняя ошибка сервера; подробности — в консоли, где запущен "
                             "scholion serve",
    "server.no_studies_folder": "Не выбрана папка исследований.",
    "server.no_labs_folder": "Не выбрана папка исследований. Нажмите «📁 Папка исследований».",
    "server.context_not_saved": "не удалось сохранить: {error}",
    "server.update.no_bcftools": "Нет bcftools в PATH приложения. Запустите update_check.sh из "
                                 "терминала, где доступен brew.",
    "server.update.not_in_this_delivery": 'Обновление ClinVar — шаг подготовки генома, а эта поставка не несёт набора инструментов подготовки. Шаг выполняется из дерева исходников — `scholion doc preparing-the-genome` его называет. Обновить саму программу — другое: `scholion version`.',
    "server.update.no_shell": 'Обновление ClinVar запускает shell-скрипт, а на этой машине нет `bash`. Всё остальное работает; обновление нужно запускать там, где есть shell.',
    "server.selfcheck_skipped": "(самопроверка анализов пропущена: {error})",
    "server.already_running": "Scholion уже запущен: {url} — открываю в браузере.",
    "server.no_free_port": "Не удалось занять порт в диапазоне {first}–{last}. Закройте лишние окна "
                           "приложения и запустите снова.",
    "server.port_busy": "Порт {wanted} занят — запускаюсь на свободном порту {chosen}.",
    "server.listening": "Scholion: {url}  (Ctrl+C для остановки)",
    "server.profile": "Профиль: {path}",
    "server.stopped": "Остановлено.",
    # --- external command-line tools (scholion tools) ---------------------
    "tools.title": "**Внешние инструменты**",
    "tools.intro": "Сам разбор работает на стандартной библиотеке — и чтение файла вариантов "
                   "тоже: без индекса он читается один раз от начала до конца, и этого хватает на "
                   "каталог локусов, фармакогенетику на нём и `scholion acmg-scan`. Отдельные "
                   "программы нужны для остального: искать внутри файла, собрать геном из "
                   "чтений, измерить покрытие, аннотировать против всего ClinVar. Ниже — что "
                   "есть, а чего нет; у каждого набора написано, что он даёт.",
    "tools.manager_found": "менеджер пакетов: {name}",
    "tools.no_manager": "Поддерживаемый менеджер пакетов не найден. Эта команда умеет Homebrew "
                        "(brew.sh) и conda/mamba — оба ставят в ваш домашний каталог. Поставьте "
                        "один из них или установите инструменты так, как принято в вашей системе.",
    "tools.sudo_never": "Ничего здесь не просит прав администратора.",
    "tools.state_missing": "не хватает: {n}",
    "tools.optional": "  (необязательно)",
    "tools.system": "часть системы; на macOS приходит с `xcode-select --install`",
    "tools.all_present": "Всё на месте.",
    "tools.will_run": "Недостающее установили бы эти команды:",
    "tools.routes_header": "Известные способы поставить недостающее — какой бы менеджер ни появился:",
    "tools.other_route": "✗ {tool} — пакета для {manager} нет. Другой путь: {command}",
    "tools.no_route": "✗ {tool}: проверенной команды установки нет — этот ставится руками.",
    "tools.later": "`scholion tools` покажет картину снова, `scholion tools --install` поставит "
                   "базовый набор.",
    "doc.list_header": "Документы, которые едут внутри пакета:",
    "doc.list_hint": "  scholion doc <имя>          напечатать\n"
                     "  scholion doc <имя> --path   где лежит на диске",
    "doc.unknown": "Документа «{name}» в этой сборке нет. Есть: {known}",
    "tools.see_later": "Для демо ставить больше нечего. Когда дойдёт до настоящего генома, "
                       "`scholion tools` скажет, какие внешние программы нужны.",
    "cli.bare_hint": "Scholion — ваши медицинские данные, сверенные друг с другом, на вашей машине.\n\n"
                     "  scholion init --demo   разложить синтетический профиль и осмотреться\n"
                     "  scholion overview      главный экран, когда профиль есть\n"
                     "  scholion --help        все команды",
    "tools.not_confirmed": "Установка не подтверждена — ничего не запускалось.",
    "tools.offline": "Выставлен SCHOLION_OFFLINE: установка ходит в сеть, поэтому ничего не "
                     "запускалось.",
    "tools.running": "→ {command}",
    "count.programs.one": "{n} внешней программы",
    "count.programs.few": "{n} внешних программ",
    "count.programs.many": "{n} внешних программ",
    "tools.init_intro": "На этой машине пока нет: {programs}. Без полного набора VCF нельзя ни "
                        "прочитать, ни проиндексировать:",
    "tools.not_a_tty": "Не спрашиваю — это не интерактивный терминал. Запустите "
                       "`scholion tools --install`, когда будет удобно.",
    "tools.ask": "Установить сейчас? [y/N] ",
    "tools.yes_words": "y,yes,д,да",
    "tools.declined": "Пропускаю. `scholion tools --install` сделает это позже; больше ничего не "
                      "меняется.",
    "tools.installed_ok": "✓ установлено: {tools}",
    "tools.install_failed": "✗ по-прежнему нет: {tools}",
    "genome.refused_head.unnamed": 'ответа на этой позиции нет, и почему — сказано ниже.',
    "genome.refused_head.not_on_chip": 'этой позиции на чипе нет.',
    "genome.refused_head.no_call": 'проба на чипе есть, и вызова она не дала.',
    "genome.refused_head.array_unreadable": 'файл массива на месте и не прочитался — это наш промах, а не свойство чипа.',
    "genome.refused_head.no_coordinates_for_assembly": 'в каталоге нет координаты этого локуса для сборки вашего файла.',
    "genome.refused_head.no_call_in_vcf": 'позиция прочитана, генотип не определён.',
    "genome.refused_head.malformed_genotype": 'поле генотипа на этой позиции разобрать не удалось.',
    "genome.refused_head.not_in_this_callset": 'варианта такого типа в этом файле быть не может.',
    "genome.refused_head.called": 'читатель вернул строку и не вернул с ней генотипа.',
    "genome.refused_head.called_array": 'чип вызвал здесь, и значение не дошло до этой строки.',
    "genome.refused_head.called_array_ambiguous": 'чип вызвал здесь, на локусе, неоднозначном по цепи.',
    "genome.refused_head.confirmed_ref": 'позиция прочитана и совпала с референсом.',
    "genome.refused_head.assumed_ref": 'строки на этой позиции нет.',
    "genome.refused_head.reported": 'значение пришло из отчёта, а не из файла.',
    "genome.refused_head.curated": 'это курируемая запись, а не чтение ваших данных.',
    "genome.refused_head.unrecognised_format": 'здесь лежит файл в форме, которую никто не опознал.',
    "genome.refused_head.no_array": 'файла массива тоже нет.',
    "genome.refused_head.plain": 'геномный файл на месте, несжатый, и искать по нему нельзя.',
    "genome.refused_head.gzip_not_bgzip": 'геномный файл сжат обычным gzip, по которому индекс искать не умеет.',
    "genome.refused_head.not_identified": 'вход опознать не удалось.',
    "genome.refused_head.offline": 'для этого нужна была сеть, а её нет.',
    "genome.refused_head.unreachable": 'до источника не достучались.',
    "genome.no_call_in_vcf": 'вызыватель дошёл до этой позиции и не смог решить: в поле генотипа стоит `./.`. Это no-call — не референс и не вариант.',
    "genome.malformed_genotype": 'в поле генотипа стоит «{value}» — это не генотип в понятной читателю форме. Ничего из него не предполагается.',
    'genome.refused_head.other_variant_at_position': 'на этой координате стоит другой вариант, и строка относится не к этому локусу.',
    'genome.other_variant_at_position': 'строка на этой позиции в файле есть, и она про другой вариант: локус записан как {expected}, в файле — {found}. Генотип, прочитанный из такой строки, принадлежал бы чужому варианту под именем этого локуса, поэтому не читается ничего. Что это закрывает: набор вариантов, нормализованный так же, или строка самого локуса.',
    'genome.refused_head.reference_mismatch': 'референсное основание на этой координате не то, с которым записан локус.',
    'genome.reference_mismatch': 'локус записан с референсным основанием {expected}; строка, найденная на его координате, несёт {found}. Это свойство файла, а не человека — другая сборка или другая нормализация, — и генотип, прочитанный поверх этого, был бы догадкой. Не читается ничего. Что это закрывает: файл с объявленной сборкой или те же варианты, нормализованные к референсу каталога.',
    'genome.refused_head.indel_not_read': 'событие на этой позиции — не замена одного основания, а этот читатель сравнивает по одному основанию.',
    'genome.refused.indel_not_read': 'Координата известна ({where}), известно и событие: {event}. В VCF такое событие записывается на одно основание выше, с опорой на предыдущее основание, парой аллелей разной длины — и читатель, который берёт эту координату и сравнивает по одному основанию с каждой стороны, находит там чужую строку или ничего и назвал бы это ничего «референсом». Не читается ничего, референс не предполагается. Что отвечает на вопрос: сама строка — `bcftools view -H -r {region} <файл>` показывает, что колл-программа записала на этих двух основаниях, — или скан по аннотации ClinVar (`scholion clinvar`), который читает событие так, как оно записано, если позиция аннотирована.',
    'genome.event.deletion': 'делеция',
    'genome.event.duplication': 'дупликация',
    'genome.event.insertion': 'вставка',
    'genome.event.delins': 'делеция-вставка',
    'genome.event.indel': 'изменение длины (аллели разной длины)',
    'genome.event.multi_base': 'замена нескольких оснований',
    "genome.not_in_this_callset": 'этот файл — каллсет, разложенный по типам вариантов, и варианта такого типа в нём нет. Отсутствие строки здесь не значит референс: файл в принципе не мог нести этот ответ.',
    "genome.imputed_call": 'этот генотип ВМЕНЁН — выведен по референсной панели, а не наблюдён в вашем образце. Файл сам помечает это в столбце FILTER.',
    "genome.filtered_call": 'вызыватель пометил эту строку: FILTER={value}. Она не прошла контроль качества, и показана, а не спрятана.',
    "genome.imputed_short": 'вменён, не наблюдён',
    "genome.filtered_short": 'помечен вызывателем как {value}',
    "genome.called_array": 'вызвано с массива',
    "genome_status.array_connected": '**Подключён генотипирующий массив** — {vendor}, {markers} позиций.',
    "genome_status.array_ceiling": 'Это не геном: чип несёт пробу для выбранных позиций и не читает ничего между ними, поэтому локус без пробы не был опрошен, а не «оказался референсом».',
    "genome_status.callset_whole_genome": 'Широта: {per_mb} наблюдённых вариантов на мегабазу в трёх межгенных окнах — это согласуется с полногеномным секвенированием.',
    'genome_status.callset_exome': 'Широта: {per_mb} наблюдаемых вариантов на мегабазу в трёх межгенных окнах и {coding_per_mb} на мегабазу в трёх гено-насыщенных — это форма ЭКЗОМА. Кодирующая часть генома прочитана, остальное не читалось вовсе, и отсутствие строки вне гена не является свидетельством референса.',
    'limits.scope.input_exome': 'Вход: экзом — кодирующая часть генома прочитана, межгенное пространство не читалось. Известные патогенные варианты в кодирующей последовательности здесь отвечаемы. Что не отвечаемо: глубоко интронные и регуляторные варианты, изменения числа копий и структурные перестройки, и любой вопрос, которому нужны данные по всему геному. Какие именно гены покрыты — свойство самого анализа, а не этого файла; закрывает это манифест анализа.',
    'narrow.path_closed_exome': 'Этот путь закрыт для экзома. Веса полигенной шкалы и её референсное распределение построены на данных по всему геному; просуммированные по кодирующим двум процентам, они дают не низкий процентиль, а число, за которым нет распределения. Что это закрывает: полногеномный набор вариантов.',
    'narrow.exome_boundary': 'Прочитано из экзома: кодирующая последовательность просмотрена, остальной геном — нет. Молчание здесь относится только к кодирующим вариантам; глубоко интронные и регуляторные изменения, а также изменения числа копий и структурные перестройки, находятся за пределами того, что этот файл может нести. Какие гены покрыл сам анализ, здесь не измерено; установил бы это манифест анализа.',
    "genome_status.callset_panel": 'Широта: {per_mb} наблюдённых вариантов на мегабазу — намного ниже полногеномного секвенирования. Это генотипирующая панель, разложенная в VCF, и вопросы, которым нужны полногеномные данные, по ней не отвечаются.',
    "genome_status.callset_sparse": 'Широта: {per_mb} наблюдённых вариантов на мегабазу — это скрининг, а не геном. Большая часть генома здесь не покрыта строками, и отсутствие строки не является свидетельством референса.',
    "genome_status.callset_imputed_panel": '{share} % строк этого файла ВМЕНЕНЫ — выведены по референсной панели, а не наблюдены. Наблюдённых остаётся {per_mb} на мегабазу. Импутация — модель, а модель не измерение.',
    "genome_status.callset_partial_callset_indels": 'В этом файле ТОЛЬКО ИНДЕЛЫ — ни одной подстановки в первых двадцати тысячах строк. Все SNV каталога из него нечитаемы, и отсутствие строки на SNV значит, что файл не может нести ответ, а не что вы совпадаете с референсом.',
    "genome_status.callset_partial_callset_snvs": 'В этом файле ТОЛЬКО ПОДСТАНОВКИ — ни одного индела в первых двадцати тысячах строк. Вставки и делеции из него нечитаемы.',
    "genome_status.foreign_vcf_compressed": '  · {path} — это VCF в обёртке, по которой читатели не умеют искать (имя об этом не говорит, а байты говорят). Пересжать и проиндексировать: `gunzip -c {path} | bgzip -c > genome.vcf.gz && tabix -p vcf genome.vcf.gz` (для bzip2 — `bunzip2 -c`).',
    "genome_status.foreign_vcf_spreadsheet": '  · {path} — это VCF, который открыли в таблице и пересохранили: строки шапки взяты в кавычки, колонки больше не разделены табуляцией. Возьмите исходную выгрузку у провайдера, а не чините эту копию.',
    "genome_status.foreign_genotype_table": '  · {path} — таблица генотипов (строка на позицию, без шапки VCF). Это читаемые данные, и эта сборка их пока не читает; формат назван здесь, а не выдан за «генома нет».',
    "genome_status.foreign_variant_table": '  · {path} — табличная выгрузка вариантов провайдера, не VCF. Это читаемые данные, и эта сборка их пока не читает.',
    "genome_status.foreign_cg_var_table": '  · {path} — таблица `var` Complete Genomics. Родной конвертер вендора делает из неё VCF: `cgatools mkvcf --beta --reference <ref.crr> --variant-file {path}`.',
    "limits.scope.input_panel": 'Вход: генотипирующая панель, разложенная в VCF — {per_mb} наблюдённых вариантов на мегабазу, доля от того, что даёт секвенирование. Выбранные позиции отвечают; геном между ними не прочитан.',
    "limits.scope.input_sparse": 'Вход: разреженный каллсет — {per_mb} наблюдённых вариантов на мегабазу. Это скрининг, а не геном: на большинстве позиций строки нет, и её отсутствие не свидетельствует о референсе.',
    "limits.scope.input_imputed_panel": 'Вход: каллсет, ВМЕНЁННЫЙ на {share} % — генотипы выведены по референсной панели, а не наблюдены в вашем образце. Наблюдённых остаётся {per_mb} на мегабазу. Перцентиль или скрининг, построенный на этом, опирается на модель, а ошибки модели в её выводе не видны.',
    "limits.scope.input_partial_callset_indels": 'Вход: каллсет, содержащий ТОЛЬКО ИНДЕЛЫ. Все однобуквенные подстановки каталога из этого файла нечитаемы — не отсутствуют у вас, а нечитаемы. Запросите у провайдера вторую половину каллсета.',
    "limits.scope.input_partial_callset_snvs": 'Вход: каллсет, содержащий ТОЛЬКО ПОДСТАНОВКИ. Вставки и делеции из этого файла нечитаемы.',
    "limits.scope.input_unmeasured": 'Вход: геномный файл, широту которого измерить не удалось. Ничего ниже не исходит из того, что он покрывает весь геном — это не установлено.',
    "genome.refused_head.called_strand_ambiguous": 'чип вызвал здесь, на локусе, аллели которого комплементарны друг другу.',
    "genome.called_array_ambiguous": 'вызвано с массива — неоднозначно по цепи',
    "ingest_labs.date_not_the_draw": 'бланк не печатает дату забора; точка записана на {date} — это дата назначения анализов, самое большее на день-два раньше, и названа здесь потому, что бланк не выдаёт её за дату забора',
    "tabular.assumed_ref": 'в каллсете нет строки на этой позиции — либо референс, либо здесь ничего не прочитано. Файл различить их не может.',
    "tabular.not_in_file": 'этой позиции в файле нет вовсе — она не несена, поэтому о ней ничего не установлено ни в ту, ни в другую сторону.',
    "tabular.no_call": 'строка в файле есть, генотипа в ней нет.',
    "tabular.called_container_vcf": 'прочитано из VCF, пришедшего сжатым в контейнере, — одним проходом по всему файлу, потому что для каталога такого размера индекс не нужен.',
    "tabular.called_genotype_table": 'прочитано из таблицы выбранных позиций, а не из генома: локус, строки для которого здесь нет, не был опрошен.',
    "genome.refused_head.not_in_file": 'этой позиции в том файле нет вовсе.',
    "genome.refused_head.assumed_ref_tabular": 'в этом каллсете строки на этой позиции нет.',
    "genome.refused_head.no_tabular": 'читаемой таблицы или контейнера тоже не нашлось.',
    "genome.refused_head.called_table": 'таблица вызвала здесь, и значение не дошло до этой строки.',
    "genome.refused_head.container_vcf": 'в контейнере лежит VCF, и прочитать его не удалось.',
    "genome.refused_head.genotype_table": 'таблицу генотипов прочитать не удалось.',
    "genome.refused_head.unreadable": 'файл на месте и не прочитался.',
    "genome.refused_head.no_tabular_source": 'читаемой таблицы или контейнера здесь нет.',
    "genome.called_table": 'прочитано из таблицы выбранных позиций',
    "genome_status.tabular_container": '**Подключён VCF, пришедший в контейнере** — читается одним проходом по всему файлу, а не поиском, потому что в нынешнем виде его нельзя проиндексировать. Вариантов {variants}, на мегабазу {per_mb}.',
    "genome_status.tabular_table": '**Подключена таблица генотипов** — {rows} строк выбранных позиций, из них локусов каталога {present}.',
    "genome_status.tabular_ceiling": 'Это не геном: таблица несёт те позиции, которые кто-то решил типировать, и ничего между ними, поэтому локус без строки не был опрошен, а не «оказался референсом».',
    "limits.scope.input_tabular_container": 'Вход: каллсет, пришедший в контейнере и читаемый одним проходом, а не поиском — вариантов {variants}, на мегабазу {per_mb}. Что эта широта позволяет — тот же вопрос, что для любого каллсета, и он измерен выше, а не предположен.',
    "limits.scope.input_genotype_table": 'Вход: таблица выбранных позиций — {rows} строк. Это не геном: позиции, которые никто не типировал, не прочитаны, и отсутствие строки не свидетельствует о референсе.',
    "narrow.path_closed_genotype_table": 'Этот путь закрыт для таблицы генотипов. В файле {rows} позиций, которые кто-то решил типировать, и ничего между ними, поэтому «ничего не найдено» означало бы только, что эти позиции отрицательны. Предсказательная ценность панели выбранных позиций по редким патогенным вариантам низка (BMJ 2021: 4,2 % для BRCA1/2; Moscarello 2019: 40 % отправленных на подтверждение вариантов ложны), и от смены формата файла она не растёт. Останется закрытым до появления частотного порога и ярлыка качества входа.',
    "narrow.path_closed_panel": 'Этот путь закрыт для генотипирующей панели. Измерено на этом файле: {per_mb} наблюдённых вариантов на мегабазу, тогда как полногеномное секвенирование даёт полторы тысячи и больше. Чип не перестаёт быть чипом оттого, что пришёл в виде VCF, и «ничего не найдено» здесь означало бы только, что выбранные позиции отрицательны (BMJ 2021: 4,2 % для BRCA1/2; Moscarello 2019: 40 % ложных). Останется закрытым до появления частотного порога и ярлыка качества входа.',
    "narrow.path_closed_sparse": 'Этот путь закрыт для разреженного каллсета. Измерено на этом файле: {per_mb} наблюдённых вариантов на мегабазу — это скрининг, а не геном. На большей части генома строк здесь нет вовсе, поэтому «ничего не найдено» было бы утверждением о файле, а не о вас.',
    "narrow.path_closed_imputed_panel": 'Этот путь закрыт для вменённого каллсета. {share} % строк этого файла выведены по референсной панели, а не наблюдены в вашем образце; наблюдённых остаётся {per_mb} на мегабазу. Находка, вычитанная из вывода модели, — находка модели, а не измерение вас.',
    "narrow.path_closed_partial_callset_indels": 'Этот путь закрыт для каллсета, содержащего только инделы. Все однобуквенные подстановки из этого файла нечитаемы — не отсутствуют у вас, а нечитаемы, — поэтому скрининг по нему сообщил бы об отсутствии вариантов, которых он и не мог увидеть. Запросите у провайдера вторую половину каллсета.',
    "narrow.path_closed_partial_callset_snvs": 'Этот путь закрыт для каллсета, содержащего только подстановки. Вставки и делеции из этого файла нечитаемы, поэтому скрининг по нему сообщил бы об отсутствии вариантов, которых он и не мог увидеть.',
    "narrow.path_closed_unmeasured": 'Этот путь закрыт, потому что широту этого файла измерить не удалось. Все три ответа опираются на «геном здесь прочитан, и ничего не найдено», а это предложение надо заслужить. Отказ по геному стоит одной команды; ответ по скринингу стоит находки, по которой можно начать действовать.',
    # ---- цель, заданная врачом (задача 170) ----
    "store.target_need_marker": 'нужен показатель',
    "store.target_needs_set_by": 'цели нужен автор (--set-by): цифра, за которой никто не стоит, позже прочитается как собственная цель продукта, а продукт целей не задаёт. Ничего не записано.',
    "store.target_needs_set_on": 'цели нужен день, когда она задана (--set-on ГГГГ-ММ-ДД), а «{value}» им не является: рамку лечения без даты не отличить от прошлогодней. Ничего не записано.',
    "store.target_needs_bound": 'цели нужна цифра: --low и/или --high для диапазона либо --value для одного числа. Ничего не записано.',
    "store.target_low_above_high": 'нижняя граница {low} выше верхней {high}; ничего не записано.',
    "store.target_marker_unknown": 'показатель «{marker}» неизвестен, и цель стояла бы рядом с пустотой — ничего не записано. Возможно, имелось в виду: {did_you_mean}.',
    "store.target_unit_required": 'цели нужна единица: цифру потом сравнивают с рядом, хранящимся в канонической единице, а догадка «наверное, обычная» — ровно то, ради чего эта проверка и стоит. Показатель {marker} принимает: {accepted}.',
    "store.targets_what": 'Цели, заданные лечащим врачом, записаны с его слов — кем и когда. ЛИЧНОЕ. Не выводятся, флагом не считаются.',
    "store.no_targets_file": 'ни одной цели пока не записано',
    "store.target_none_for": 'для «{marker}» цель не записана',
    "target.spec_range": '{low}–{high}',
    "target.spec_max": '≤{high}',
    "target.spec_min": '≥{low}',
    "target.spec_value": '{value}',
    "target.beside": 'цель {spec}, задана: {set_by}, {set_on}',
    "target.side_above": 'выше',
    "target.side_below": 'ниже',
    "target.discuss": 'в коридоре, но {side} цели {spec}, заданной {set_on} ({set_by}) — обсудить на приёме?',
    "target.outside_and_flagged": '{side} цели, и коридор это уже отмечает',
    "target.within": 'в пределах цели',
    "target.list_none": 'Целей, заданных врачом, не записано. Цель вносится, а не выводится: `scholion target set <показатель> --low … --high … --unit … --set-by "…" --set-on ГГГГ-ММ-ДД`.',
    "target.list_title": '**Цели, заданные врачом:** {targets}',
    "target.list_line": '{name}: цель {spec} — задана: {set_by}, {set_on}',
    "target.now": 'сейчас {value} ({date})',
    "target.now_none": 'измерений этого показателя пока нет',
    "target.frame_note": 'Цель — рамка лечения, внесённая со слов врача и здесь не выводимая. Выход за неё — не дефицит и не флаг, а вопрос, который стоит взять на приём.',
    "count.targets.one": '{n} цель',
    "count.targets.few": '{n} цели',
    "count.targets.many": '{n} целей',
    "web.target.h": 'Цели, заданные врачом',
    "web.target.form_h": 'Записать цель, которую задал врач',
    "web.target.add_toggle": 'Цель врача',
    "web.target.marker": 'Показатель',
    "web.target.low": 'от',
    "web.target.high": 'до',
    "web.target.value": 'или одно число',
    "web.target.unit": 'Единица',
    "web.target.set_by": 'Кем задана',
    "web.target.set_on": 'Когда',
    "web.target.note": 'Заметка',
    "web.target.save": 'Сохранить цель',
    "web.target.remove": 'Убрать',
    "web.target.fill_required": 'Нужны показатель, цифра, кем и когда задана',
    "web.target.saved": 'цель записана ✓',
    "web.target.removed": 'цель убрана',
    "web.target.none": 'Целей, заданных врачом, не записано. Цель вносится с его слов — продукт своих не предлагает.',
    "web.target.beside": 'цель {spec}',
    "web.target.provenance": 'задана: {set_by}, {set_on}',
    "web.target.now": 'сейчас {value} ({date})',
    "web.target.now_none": 'измерений пока нет',
    "web.target.within": 'в пределах цели',
    "web.target.side_above": 'выше',
    "web.target.side_below": 'ниже',
    "web.target.discuss": 'в коридоре, но {side} цели — обсудить на приёме?',
    "web.target.outside_and_flagged": '{side} цели, и коридор это уже отмечает',
    "web.target.discuss_h": 'В коридоре, но вне цели врача',
    "web.target.discuss_none": 'Все записанные цели достигнуты — или сравнивать пока не с чем.',
    "web.target.lg_corridor": 'коридор',
    "web.target.lg_target": 'цель',
    "web.target.frame_note": 'Цель — рамка лечения, внесённая со слов врача и здесь не выводимая. Выход за неё — не дефицит и не флаг, а вопрос, который стоит взять на приём.',
    "store.date_source_unknown": '«{value}» — не источник, из которого может прийти дата. Принимаются: {accepted}. Значение, которого никто не объявлял, будет отрисовано так, будто оно что-то значит.',
    "labs.date_source_ordered": '· дата НАЗНАЧЕНИЯ, а не забора',
    "labs.date_source_filename": '· дата из ИМЕНИ ФАЙЛА, а не с бланка',
    "near.moved_approximate_date": '⚠ и как минимум одна точка этого ряда ({dates}) датирована не бланком — датой назначения или именем файла. Сдвиг, измеренный между двумя днями, один из которых бланк не печатал, — сдвиг неопределённой величины.',
    "limits.date_unrecorded_what": 'Для {n} лабораторных точек не записано, откуда взялась их дата.',
    "limits.date_unrecorded_why": 'Они попали в профиль до того, как продукт стал это фиксировать. Не утверждается ни что они датированы забором, ни что с ними что-то не так — запись просто молчит, а «наверное, с бланка» есть ровно то предположение, которое этот слой отказывается делать.',
    "limits.date_unrecorded_closes": 'запускать нечего. Точки, добавленные с этого момента, несут свой источник, а повторная загрузка папки с бланками перепишет те, что пришли из неё.',
    # ── Task 195: the page's grammar — heads, facts, tables, statuses ──
    "web.status.critical": "вне нормы",
    "web.status.warning": "внимание",
    "web.status.good": "в норме",
    "web.status.nodata": "нет данных",
    "web.common.go_tab": "Открыть: {tab}",
    "web.common.show_more": "Нажмите, чтобы показать текст целиком",
    "web.table.marker": "Показатель",
    "web.table.value": "Сейчас",
    "web.table.ref": "Норма",
    "web.table.date": "Дата",
    "web.source.line_h": "Источники",
    "web.header.local_badge_short": "локально",
    "web.header.menu": "Справочник, ассистент, версия",
    "web.tab.medicines": "Лекарства",
    "count.genes_unread.one": "{n} целевой ген не прочитан из генома",
    "count.genes_unread.few": "{n} целевых гена не прочитаны из генома",
    "count.genes_unread.many": "{n} целевых генов не прочитано из генома",
    "web.page.overview.q": "Где вы сейчас: что вне нормы, каким системам нужно внимание и что сдать дальше.",
    "web.page.radar.q": "Каждая система организма перед визитом к врачу: что вне нормы, что на неё действует, что спросить.",
    "web.page.labs.q": "Ваши анализы: что сейчас вне нормы и как менялось каждое значение.",
    "web.page.genome.q": "На что может ответить файл вашего генома и что в нём найдено.",
    "web.page.medicines.q": "Что вы принимаете сейчас, что отменено и как новый препарат сочетается с вашим геномом, анализами и списком.",
    "web.page.lifestyle.q": "Как меняются тело, активность и восстановление, и что делать дальше.",
    "web.page.assistant.q": "Приложение работает без языковой модели. Здесь сказано, что модель добавляет и как её подключить.",
    "web.overview.fact_index": "индекс здоровья",
    "web.overview.fact_abnormal": "вне нормы, из всех показателей",
    "web.overview.fact_systems": "системы, требующие внимания",
    "web.overview.fact_tests": "анализы, которые стоит сдать",
    "web.overview.more_in_labs": "Остальные — на вкладке «Анализы»: {n}",
    "web.labs.fact_abnormal": "вне нормы, из всех",
    "web.labs.fact_within": "в пределах нормы",
    "web.labs.fact_latest": "последний анализ",
    "web.labs.out_h": "Вне нормы",
    "web.labs.none_out": "Ни один показатель не выходит за пределы нормы.",
    "web.second.fact_index_since": "индекс здоровья; {date} было {score}",
    "web.second.fact_questions": "вопросы врачу",
    "web.second.since": "было {score} ({date})",
    "web.second.verdict_out": "Вне нормы: {out}. Измерено: {measured}/{total}.",
    "web.second.verdict_in": "Всё измеренное в пределах нормы. Измерено: {measured}/{total}.",
    "web.second.verdict_nodata": "Измерений по этой системе пока нет.",
    "web.second.gen_h": "найдено: {found}; проверено: {positions}",
    "web.second.gen_absent": "Не найдено у вас, позиция прочитана: {genes}",
    "web.second.gen_unread": "Не прочитано: {genes}",
    "web.second.gen_list": "Список генов системы: прочитано {read}/{total}; находок: {findings}",
    "web.second.more": "Подробнее: все позиции панели, баллы, заметки",
    "web.second.how_to_read": "Как читать блок",
    "web.system.for_patient": "Для пациента",
    "web.system.for_clinician": "Для врача",
    "web.system.fact_score": "балл системы",
    "web.system.fact_measured": "показателей измерено",
    "web.system.fact_found": "найдено в панели",
    "web.system.genetics_detail": "Список генов, все позиции и баллы",
    "web.system.next_h": "Следующие шаги",
    "web.panel.fact_positions": "позиции панели",
    "web.panel.fact_genes": "гены",
    "web.panel.fact_studies": "позиции с исследованием",
    "web.panel.fact_signed": "подписано врачом",
    "web.genome.fact_actionable": "находки, важные для врача",
    "web.genome.fact_prs_high": "шкалы заметно выше среднего",
    "web.genome.fact_long": "гены с вариантами долголетия",
    "web.genome.set_aside_h": "Отложенные файлы",
    "web.meds.fact_current": "принимаются сейчас",
    "web.meds.fact_stopped": "отменены или на паузе",
    "web.meds.current_h": "Принимаются сейчас",
    "web.meds.past_h": "Отменённые и на паузе",
    "web.meds.status.stopped": "отменено",
    "web.meds.status.paused": "на паузе",
    "web.meds.status.not_in_scheme": "нет в схеме",
    "web.meds.status.course": "курс",
    "web.meds.status.active": "принимается",
    "web.meds.status.finished": "завершено",
    "web.drug.names_h": "Как ищется название препарата",
    "web.life.no_workouts": "В выгрузке нет тренировок.",
    "web.assistant.how_checked": "Как это проверено",
    "web.assistant.no_curated": "Текстов, написанных ассистентом, пока нет.",
    "web.guide.tour_medicines": "Что вы принимаете и что отменено, и проверка нового препарата по геному, анализам и списку.",
    "clinvar.sig.pathogenic": "Патогенный",
    "clinvar.sig.likely_pathogenic": "Вероятно патогенный",
    "clinvar.sig.uncertain_significance": "Значение не определено",
    "clinvar.sig.likely_benign": "Вероятно доброкачественный",
    "clinvar.sig.benign": "Доброкачественный",
    "clinvar.sig.conflicting_classifications_of_pathogenicity": "Противоречивые оценки",
    "clinvar.sig.conflicting_interpretations_of_pathogenicity": "Противоречивые оценки",
    "clinvar.sig.drug_response": "Ответ на препарат",
    "clinvar.sig.risk_factor": "Фактор риска",
    "clinvar.sig.protective": "Защитный",
    "clinvar.sig.association": "Ассоциация",
    "clinvar.sig.affects": "Влияет",
    "clinvar.sig.other": "Другое",
    "clinvar.sig.not_provided": "Не указано",
    "clinvar.sig.confers_sensitivity": "Повышает чувствительность",
    "clinvar.sig.likely_risk_allele": "Вероятный аллель риска",
    "clinvar.sig.established_risk_allele": "Установленный аллель риска",
    "clinvar.sig.uncertain_risk_allele": "Неопределённый аллель риска",
    "clinvar.sig.low_penetrance": "Низкая пенетрантность",
    # ── 0.5.2: rings loading, the menu's update entries, ClinVar drug responses in words ──
    "web.body.rings_loading": "генетические кольца загружаются",
    "web.menu.check_update": "Проверить обновление",
    "web.menu.recompute": "Пересчёт после обновления",
    "web.menu.checking": "Спрашиваю реестр…",
    "clinvar.response": "{drug}: ответ на препарат — {kind}",
    "clinvar.response_kind.efficacy": "эффективность",
    "clinvar.response_kind.dosage": "дозировка",
    "clinvar.response_kind.metabolism": "метаболизм",
    "clinvar.response_kind.pk": "фармакокинетика",
    "clinvar.response_kind.toxicity": "токсичность",
    "clinvar.response_kind.other": "другое",
    "phenotype.label.NM": "нормальный метаболизатор",
    "phenotype.label.IM": "промежуточный метаболизатор",
    "phenotype.label.PM": "медленный метаболизатор",
    "phenotype.label.RM": "быстрый метаболизатор",
    "phenotype.label.UM": "ультрабыстрый метаболизатор",
    "phenotype.function.normal": "нормальная функция",
    "phenotype.function.decreased": "сниженная функция",
    "phenotype.function.poor": "низкая функция",
    "phenotype.function.increased": "повышенная функция",
    "phenotype.qualifier.likely": "вероятно {label}",
    "phenotype.qualifier.possible": "возможно {label}",
    # ── 0.5.2: the version and the update, for a person and inside an assistant's session ──
    "tool.sch_version.description": "КАКАЯ СБОРКА ОТВЕЧАЕТ и вышла ли новее. Вызывайте в начале сессии. Сообщает, с какой версией данные работали последний раз и что просят пересчитать выпуски между ними, затем — есть ли в реестре пакетов более новая сборка (запрос не чаще раза в сутки и никогда без сети) и как она ставится в этом окружении. Ничего не пишет. Если новая сборка вышла, скажите человеку и спросите, прежде чем вызывать sch_update.",
    "tool.sch_update.description": "УСТАНАВЛИВАЕТ новую сборку Scholion в это окружение (pip, pipx или uv — как было установлено). Вызывайте только после того, как человек сказал «да» в этом разговоре, с confirm=true; без него ничего не ставится, а ответ говорит, что было бы выполнено. В рабочую копию исходников не ставит — предлагает git pull. После установки ассистента нужно перезапустить.",
    "tool.sch_update.param.confirm": "true — только после явного согласия человека на установку в этом разговоре",
    "upgrade.session_note": "— Вышла Scholion {latest}, в этой сессии работает {installed}. Скажите человеку и устанавливайте только после его согласия: sch_update с confirm=true или `scholion update --yes`.",
    "update.newer": "Вышла более новая Scholion: {latest} (эта сборка — {installed}).",
    "update.current": "Это самая новая Scholion: {installed}.",
    "update.cached": "(проверено за последние сутки — реестр спрашивается не чаще раза в сутки)",
    "update.how.install": "Установить здесь, когда человек согласится: `scholion update --yes` — будет выполнено `{command}`.",
    "update.how.source": "Это рабочая копия исходников; она обновляется из своего репозитория: `{command}`.",
    "update.installed": "Установлена Scholion {after} (была {before}). Перезапустите ассистента или `scholion serve`, чтобы работала новая сборка; если используется копия скилла, выполните `scholion skill --install`.",
    "update.already_current": "Ставить нечего: {installed} — актуальная версия.",
    "update.not_confirmed": "Ничего не установлено: обновление ставится только после согласия человека. Было бы выполнено `{command}`.",
    "update.failed": "Установка не завершилась (код {code}). Команда: `{command}`; последние строки:",
    "web.menu.install": "Установить обновление",
    "web.menu.install_confirm": "Установить Scholion {latest} в это окружение? После установки Scholion нужно перезапустить.",
    "web.menu.installing": "Устанавливаю…",
}
