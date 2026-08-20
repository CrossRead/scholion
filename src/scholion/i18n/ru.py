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
    "genome.unknown_gene": "Ген {gene} не найден в справочнике координат.",
    "genome.no_database": "полная геномная база ещё не подключена.",
    "genome.loci": "**{gene}** — локусы:",
    "genome.called": "вызван из VCF",
    "genome.assumed_ref": "референс (сайт не вариантный)",
    "genome.depth": "покрытие {value}",
    "genome.gene_at": "ген **{gene}** ({chrom}:{pos})",
    "genome.genotype": "генотип **{genotype}**",
    "genome.significance": "Клиническая значимость (ClinVar/Ensembl): {values}",
    "genome.consequence": "Последствие: {text}",
    "genome.resolved_by": "координата получена: {source}",

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
    "drug.phenotype_not_determined": "Фенотип {gene} по твоим данным не определён — дальше общее правило, а не утверждение о тебе.",
    "drug.no_guidance_for_phenotype": "В каталоге нет рекомендации для фенотипа {phenotype} гена {gene} по этому препарату. Это пробел в справочных данных, а не вывод о тебе — вопрос к врачу.",
    "basis.read": "Прочитано {read} из {total} маркеров модели.",
    "basis.missing": "Не прочитано: {names}.",
    "basis.obtainable": "Эти позиции есть в каталоге локусов: полный геном (VCF) из собственных ридов или прицельный фармакогенетический тест, который их покрывает, закроет этот пробел и превратит общее правило в утверждение об этом человеке.",
    "basis.not_in_catalogue": "В каталоге локусов их тоже нет — нужен лабораторный анализ.",
    "basis.not_called": "VCF подключён, но у {names} в нём нет строки — это либо референс, либо отсутствие покрытия, и по файлу их не различить. Собрать другой VCF ничего не изменит: эти позиции нужно прогенотипировать из выравненных чтений, и до тех пор они считаются непрочитанными.",
    "basis.not_modelled": "В каталоге проекта по этому гену есть {names}, и модель интерпретации это пока не использует — то есть даже полный VCF эту часть не закроет.",
    "phenotype.from_called_diplotype": "по вызванному диплотипу {diplotype} (PyPGx/PharmCAT — с числом копий и фазой), что важнее оценки по tag-SNP",
    "phenotype.assumed": "{label} — ПРЕДПОЛАГАЕТСЯ, прочитаны не все маркеры",
    "prescription.title": "**Второе мнение: {drug}** — итог: **{overall}**",
    "prescription.class": "класс: {value}",
    "prescription.source": "источник: {value}",
    "prescription.genome_header": "Твой геном:",
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
    "prescription.no_pgx": "Значимой фармакогенетики по препарату нет (CPIC): "
                           "генов, влияющих на дозу/эффект, не выявлено.",
    "prescription.actionable": "важен",
    "prescription.gene_phenotype": "твой фенотип **{phenotype}** — {label}",
    "prescription.variants": "варианты: {list}",
    "prescription.labs_header": "Твои анализы:",
    # ── red flags from the owner's own profile ───────────────────────────
    "prescription.safety_h": "Красный флаг из твоего профиля:",
    "prescription.safety_factor": "**Фактор:** {text}",
    "prescription.safety_why": "Почему это важно: {text}",
    "prescription.safety_pro": "Что говорит в пользу низкого риска: {text}",
    "prescription.safety_unknown": "Что неизвестно: {text}",
    "prescription.safety_action": "**Действие:** {text}",
    "prescription.safety_source": "Источник: {text}",

    "prescription.no_lab_control": "Специфического лабораторного контроля по классу не требуется.",
    "prescription.monitor": "Контролировать: {text}",
    "prescription.already_abnormal": "У тебя уже отклонены: **{names}** — "
                                     "важно при этом препарате.",
    "prescription.threshold_crossed": "{name} {value} — пройден клинический порог действия "
                                      "{threshold} ({label}).",
    "prescription.source_ref": "источник: {source}",
    "prescription.near_edge": "В норме, но у границы коридора: **{names}** — "
                              "при этом препарате следить особенно.",
    "prescription.not_tested": "ещё не сдавал",
    "prescription.interactions_header": "Твои назначения:",
    "prescription.interaction": "с **{meds}** — {effect} (механизм: {mechanism}).",
    "prescription.what_to_do": "Что делать: {text}",
    "prescription.no_interactions_partial": "Явных взаимодействий с опознанной частью текущего "
                                            "списка не найдено. НЕ сравнивалось, потому что класс "
                                            "не определён: {names}.",
    "prescription.no_interactions": "Явных взаимодействий с текущими назначениями не найдено.",
    "prescription.dose_header": "Дозовый и критический контекст:",
    "prescription.doses": "Дозы: нутрицевтическая {nutritional} · "
                          "фармакологическая {pharmacologic}.",
    "prescription.effect": "эффект: {text}",
    "prescription.by_dose": "по дозе: {text}",
    "prescription.not_measured": "{name}: не сдавал",
    "prescription.your_numbers": "твои цифры: {items}",
    "prescription.forms": "Формы: {text}",
    "prescription.alternative": "альтернатива: **{name}**",
    "prescription.alt_melatonin": "мелатонин/сон",
    "prescription.alt_metabolic": "метаболика",
    "prescription.alt_caveat": "оговорка",

    # ── анализы ──────────────────────────────────────────────────────────
    "labs.header": "**Анализы:** {abnormal} из {total}",
    "labs.near_more": "ещё {n} у границы коридора",
    "labs.crossed": "клинических порогов действия пройдено: {n}",
    "labs.draw_context_saved": "записано для {day}: {context} — применено к {n} показателям, измеренным в тот день дважды",
    "labs.fasting_after_event": "⚠ пороги ниже предполагают пробу натощак; этот забор сделан после — {text} — поэтому пересечение здесь не означает названного состояния",
    "labs.condition_unknown": "⚠ это второй забор за день, а пороги ниже предполагают пробу натощак — пока не сказано, что было между замерами, считайте отмеченное пересечение неподтверждённым",
    "labs.same_day_repeat": "два замера {day}: {points} — это повтор, а не расхождение в данных",
    "labs.same_day_context": "между ними: {text}",
    "labs.same_day_ask": "почему в тот день сдавали дважды и что было между замерами — процедура, приём препарата, нагрузка? `scholion lab-draw --day <дата> --reason … --between …`",
    "labs.near_limit_is_flat": "«У границы» считается как плоские 10 % от предела для любого аналита. Это эвристика, а не reference change value: между заборами натрий меняется на доли процента, а CRP на десятки, поэтому зона для одних показателей слишком мягкая, для других слишком строгая.",
    "labs.ref_from_reference_base": "интервал общий справочный, а не напечатанный на вашем бланке",
    "labs.genome_link": "геном: {text}",
    "count.abnormal.one": "{n} отклонение",
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
    "metrics.empty_hint": "Внеси вес/сон/шаги во вкладке «Показатели».",

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
                    "`_meta._example` лежит заполненный пример — перенеси его на "
                    "верхний уровень и перепиши под свою цель.",
    "goal.title_default": "Цель",
    "goal.as_of": "данные на {date}",
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
                                "них не может. Если выданная тебе инструкция и этот список "
                                "расходятся — прав список: это сборка, которая перед тобой. "
                                "Каждая команда принимает `--json`.",
    "capabilities.reads_h": "Только читают — {n} команд. Безопасно вызывать, чтобы ответить на вопрос.",
    "capabilities.writes_h": "МЕНЯЮТ данные — {n} команд. Не для ответа на вопрос. Двух родов, "
                             "помечено на каждой строке: одни СОЧИНЯЮТ значения в профиль — "
                             "такие модели как инструмент не выдаются никогда; другие ПЕРЕНОСЯТ "
                             "в профиль собственные документы человека и ничего не выдумывают — "
                             "такие модели доверить можно.",
    "capabilities.kind.authors": "сочиняет значения — модели не выдаётся",
    "capabilities.kind.transcribes": "переносит собственные документы человека",
    "capabilities.face.web": "есть в веб-интерфейсе",
    "clinvar.low_confidence": "низкая достоверность (0-1 звезды): уровень пересмотра не подтверждает это с силой, которую подразумевает класс",
    "clinvar.low_confidence_note": "{n} из них опираются на пересмотр ClinVar 0-1 звезды — патогенная трактовка на таком уровне — самый переоценённый класс для потребительского секвенирования; воспринимать как повод перепроверить, а не как находку.",
    "clinvar.empty": "Значимых вариантов ClinVar в твоём VCF не извлечено.",
    "clinvar.header": "**Клинически значимые находки (ClinVar): {n}**",
    "clinvar.shown": "(показаны первые {n})",
    "clinvar.how_to_read": "**Как это читать.**",

    # ── вторичные находки ACMG ───────────────────────────────────────────
    "acmg.unread_header": "Прочитано недостаточно глубоко для решения — {n} генов панели. Отрицательный результат по ним не является утверждением:",
    "acmg.needs_phase_header": "{n} находок в генах, которым нужны обе повреждённые копии, обнаружены как две гетерозиготы. Лежат ли они на разных хромосомах — а именно это делало бы их биаллельными — нефазированный файл сказать не может; в цис человек обычный носитель. Разрешается генотипом родителя или длинными ридами:",
    "acmg.needs_class_header": "{n} находок в генах, которые ACMG репортит только для узкого класса вариантов — класс нужно установить, прежде чем это станет находкой:",
    "acmg.how_to_run": "Запусти `python3 src/ingest/acmg_sf_scan.py` — "
                       "он сверит твой VCF со списком генов ACMG Secondary Findings.",
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
    "prs.caveat.reference_panel": "перцентиль — это положение внутри референсной выборки; пакет расчёта пинуется по версии, а не по хешу, а референсная панель, которую он скачивает при первом запуске, не пинуется вовсе — две машины в принципе могут поставить один и тот же геном относительно разных референсных данных",
    "prs.no_model": "нет модели",
    "prs.evidence_legend": "Уровень доказательности: ✚ клинически валидировано · "
                           "· вспомогательный контекст · без метки — исследовательский уровень",

    # ── слой долголетия ──────────────────────────────────────────────────
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
    "reconcile.unreadable": "НЕ ПРОЧИТАНО ({n}) — возможны потерянные данные, открой файлы "
                            "на Mac (материализация iCloud) и повтори:",
    "reconcile.bytes": "{n} байт",
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
    "genome.refused_head.several_files": "геномных файлов больше одного, и ни один не выбран.",
    "genome.refused_head.several_samples": "в файле несколько образцов, и ни один не выбран.",
    "genome.refused_head.foreign_input": "в папке есть геномные данные, но нет читаемого VCF.",
    "genome.refused_head.no_engine": "геномный файл на месте, а читателя не установлено.",
    "genome.refused.no_file": "Координата найдена, но полная геномная база ещё не подключена (нужны genome/*.vcf.gz + .tbi).",
    "genome.refused.no_answer": "Координата найдена, файл подключён, но читатель не вернул на этой позиции ничего — чаще всего это отсутствующий или сломанный индекс (`.tbi`/`.csi`). `scholion genome-status` говорит, какой. Пустой ответ — это не референс, и как референс он не подаётся.",
    "genome.refused.unreadable_file": "Координата найдена. Файл в геномной папке в таком виде не читается — `scholion genome-status` печатает одну команду, которая это чинит. Ничего не отсутствует и ничего не нужно добывать.",
    "genome.refused.assembly_unsupported": "Координата найдена, и ваш файл тоже: он подключён и проиндексирован. Он вызван на сборке, координат для которой в каталоге нет, и на лету ничего не пересчитывается — пересчитанная позиция указывает на настоящее основание, но не на то. `scholion genome-status` называет сборку и что делать.",
    "genome.refused.several_files": "Координата найдена. Геномных файлов в папке больше одного, и какой из них ваш — не нам угадывать: `SCHOLION_GENOME_VCF` говорит это одной переменной.",
    "genome.refused.several_samples": "Координата найдена. В файле несколько образцов — трио или совместный вызов, — и чтение первой колонки выдало бы за вас другого человека. `SCHOLION_GENOME_SAMPLE` говорит, какой образец ваш.",
    "genome.refused.foreign_input": "Координата найдена. В папке лежат геномные данные, которые не являются читаемым VCF — `scholion genome-status` называет каждый файл и то, что ему нужно.",
    "genome.refused.no_engine": "Координата найдена и файл на месте, но не установлено ни одного читателя: bcftools, pysam или рабочий индекс `.tbi` рядом с файлом.",
    "genome_status.file": "Файл: {path}",
    "genome_status.reader": "Чтение: {reader}",
    "genome_status.not_ready": "**Геном найден, но не готов к чтению:** {reason}",
    "genome_status.no_index": "нет индекса .tbi",
    "genome_status.assembly_unknown_actions": "Три способа установить, от дешёвого к дорогому:\n  1. **Если знаешь, кто делал секвенирование** — сборка названа в их отчёте, и хватит одной переменной: `SCHOLION_GENOME_ASSEMBLY=GRCh37 scholion genome-status` (или GRCh38, или T2T-CHM13v2.0).\n  2. **Прочитать из заголовка:** `bcftools view -h {path} | grep -E '##(contig|reference)'` — `length=` рядом с chr1 отвечает сразу: 249250621 — GRCh37, 248956422 — GRCh38, 248387328 — T2T.\n  3. **Вписать контиги один раз**, чтобы файл дальше отвечал сам за себя: `bcftools reheader -f <reference>.fai {path}`.",
    "genome_status.assembly_mismatch": "**Геномный слой отключён: файл вызван относительно {found}, а каталог координат — в {want}.** Один и тот же вариант лежит в разных сборках на разных позициях: например, APOE rs429358 — это 19:44 908 684 в GRCh38 и 19:45 411 941 в GRCh37. Запрос координаты одной сборки к файлу другой попадает в другой ген, и ответ окажется неверным, не выглядя неверным.",
    "genome_status.assembly_fix": "Перевести файл в {want} (`CrossMap` или `bcftools +liftover` с chain-файлом) либо пере-вызвать варианты из выравнивания относительно этой сборки. Координаты здесь сознательно не пересчитываются на лету: тихое преобразование добавило бы ровно тот класс ошибок, ради устранения которого слой и существует. Всё вне генома — анализы, назначения, носимые — работает как обычно.",
    "genome_status.coordinates_secondary": "читается по координатам {assembly} — каталог несёт в этой сборке {have} локусов из {total}, остальные из этого файла не читаются, а не угадываются. Между сборками ничего не пересчитывается.",
    "genome_status.assembly_ok": "Сборка: {found}",
    "genome_status.assembly_unknown": "**Сборка: не установлена.** В заголовке нет ни длин контигов, ни строки `##reference`, и за концом первой хромосомы GRCh38 не нашлось ни одного варианта — значит и данные её не выдали. Ответы считаются так, будто файл в {want}; если это не так, каждый геномный ответ — про не ту позицию.",
    "genome_status.unusable_plain": "**Геномный файл лежит рядом и пока не читается:** {path} — это обычный `.vcf`. Читатели ищут по файлу позиционно, поэтому он должен быть блочно сжат и проиндексирован. Это одна команда, а не другой файл.",
    "genome_status.unusable_gzip_not_bgzip": "**Геномный файл лежит рядом и пока не читается:** {path} — он сжат обычным gzip, а не bgzip. Выглядит правильно, но `tabix` откажется с сообщением о формате, которое ничего не объясняет.",
    "genome_status.unusable_fix": "Починить так: {cmd}",
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
    "ingest.not_ingested_header": "Из {n} файлов не взято ничего — каждый назван, с причиной:",
    "ingest.not_ingested_more": "… и ещё {n}",
    "ingest.conflict": "расхождение: {marker} за {date} — оставлено {kept}, другой бланк дал {other}",
    "ingest.repeat": "повтор: {marker} измерен дважды {day} ({first} и {second}) — `scholion lab-draw --day {day}` запишет, что было между",
    "ingest.labs_done": "Обработано файлов: {files}, точек: {points}, пропущено: {skipped}.",
    "ingest.no_folder": "не указана папка с PDF",
    "ingest.studies_done": "Заключений всего: {total}; добавлено {added}, обновлено {updated}, "
                           "файлов просмотрено {seen}. {hint}",
    "ingest.garmin_done": "✓ Образ жизни пересобран: {metrics} метрик, диапазон {range}. "
                          "Записано в {out}",
    "ingest.garmin_backup": " (бэкап: {path})",

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
1. Ты не назначаешь и не отменяешь терапию. Итог разбора — вопросы к врачу.
2. Числа ниже уже посчитаны локальным кодом по первичным данным. Не пересчитывай их
   и не заменяй «типичными» значениями: если чего-то нет, так и скажи — нет.
3. У каждого вывода указывай источник: показатель и дату либо команду, которая его дала.
4. Коридоры нормы взяты из печатных бланков этого человека. Не подставляй чужие нормы.
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

Не выдумывай вывод этих команд — попроси выполнить и пришлить результат.
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
                                    "ожидаются, что знает геномный слой. Начинай отсюда, когда "
                                    "вопрос широкий — экран называет части, о которых стоит "
                                    "спросить дальше.",
    "tool.sch_second_opinion.description": "Одна страница к разговору с врачом: индекс здоровья "
                                          "по системам, текущие отклонения анализов, сгруппированные "
                                          "по системе, к которой относятся, фармакогенетический "
                                          "список наблюдения против имеющихся назначений и анализы, "
                                          "которые ещё имеет смысл сдать. По каждому препарату "
                                          "сказано, прочитан ли генотип или печатается общее правило.",
    "tool.sch_limits.description": "НА ЧТО ЭТИ ДАННЫЕ ОТВЕТИТЬ НЕ МОГУТ и чем закрывается каждый "
                                  "пробел. Читай прежде любого отрицательного утверждения: «ничего "
                                  "не найдено» значимо только рядом с тем, где искали. Называет "
                                  "клетку матрицы «класс входа × архитектура признака», измеренное "
                                  "покрытие и каждое утверждение, которого профиль не выдерживает.",
    "tool.sch_radar.description": "Индекс здоровья по системам организма, 0–100 каждая, с "
                                 "изменением относительно прошлого измерения и списком "
                                 "сдвинувшихся маркёров. Знаменатель — заявленная панель системы, "
                                 "а не та её часть, что оказалась измерена: система с двумя "
                                 "значениями из девяти так и говорит.",
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
                                 "Используй, чтобы оценить, насколько профиль приблизился к "
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
    "gene.vcf_pending": "полная геномная база готовится (Трек 2) — тогда подтянутся твои "
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
    "radar.domain.glucose": "Углеводный обмен",
    "radar.domain.inflammation": "Воспаление",
    "radar.domain.hormones": "Гормоны",
    "radar.domain.liver": "Печень",
    "radar.domain.micronutrients": "Витамины",
    "radar.domain.renal": "Почки",
    "radar.domain.fitness": "Форма",
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
    "focus.bedtime_share": "за последние {n} ноч. экспорта уложился в порог {share} % раз, "
                           "среднее засыпание {clock}",
    "focus.awake_mean": "за последние {n} ноч. экспорта бодрствование в постели в среднем "
                        "{mean} мин",
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
    "provenance.no_coverage": "нет profile/labs_coverage.json — запусти reconcile (или "
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
    "store.unknown_source": "неизвестный источник",
    "store.folder_not_found": "папка не найдена: {path}",
    "store.sources_purpose": "Выбранные пользователем папки-источники данных. Персональное.",
    "store.need_day_and_context": "нужен день и хотя бы одно из --reason / --between",
    "store.no_repeat_that_day": "ни у одного показателя за {day} нет двух замеров — объяснять нечего",
    "store.no_labs": "в профиле пока нет лабораторной истории",
    "store.need_marker_date": "нужны marker и date",
    "redact.no_file": "файла {path} нет",
    "redact.no_patterns": "Файла .personal_patterns нет, поэтому убраны только структурные классы — фамилия и номер образца остались, потому что здесь их никто не знает. Заведи файл (он вне git): printf '%s\n' 'Фамилия' 'НОМЕР-ОБРАЗЦА' 'mail@example.com' > .personal_patterns",
    "redact.title": "**Вычищенный текст**",
    "redact.replaced": "Заменено: {what}.",
    "redact.replaced_none": "Ни одно правило не сработало. Это не справка о чистоте — смотри ниже.",
    "redact.notices_head": "**Чего инструмент НЕ тронул, потому что решать не ему:**",
    "redact.notice_genotype": "токенов вида генотипа — {n}. rsID, аллели и звёздочные аллели — это твой геном, и они же обычно предмет самого сообщения об ошибке: реши по каждому.",
    "redact.notice_measurement": "чисел с единицей рядом — {n}. Это твои результаты.",
    "redact.footer": "Прочитай текст ниже перед публикацией. Инструмент не отличит лабораторное значение от номера версии, а issue публична с секунды создания.",
    "limits.prs_both_closes": "Скор сняли с доверия две причины, и только одна в твоей власти: генотипирование позиций модели из BAM (src/ingest/prs_genotype_sites.sh) закрывает часть про покрытие и оставляет остальное как есть — причина выше про модель, а не про прочтение.",
    "limits.prs_model_why": "Скор снят с доверия по валидности самой модели, а не по прочтению.",
    "limits.prs_measured_closes": "Закрывать нечего: величина, которую оценивает модель, "
                                  "измерена у тебя напрямую — {name} {value} {unit} ({date}). "
                                  "Измерение сильнее перцентиля, посчитанного по вариантам; "
                                  "скор к нему ничего не добавляет.",
    "limits.prs_model_closes": "Твоими данными это не закрывается — ограничение в модели, а не в прочтении. Помогла бы только другая модель, а там, где признак измеряется напрямую, ответ даёт само измерение.",
    "limits.interval_basis_locus": "измерено по локусам генов с полем, а не по кодирующей последовательности: небольшой провал внутри крупного гена почти не двигает это число, а именно про такой провал его обычно и спрашивают",
    "limits.interval_basis_unknown": "по чему измерены эти проценты — не записано; по кодирующей последовательности и по локусу целиком это разные величины, и разница не мала",
    "limits.coverage_unknown": "Покрытие твоего генома ни разу не измерялось, поэтому «ничего не найдено» в гене не отличить от «не прочитано».",
    "limits.coverage_closes": "Запусти `bash src/ingest/qc_callability.sh` — нужны mosdepth и BAM, на выходе profile/callability.tsv.",
    "limits.coverage_what": "Ни на один отрицательный геномный вывод нельзя опереться.",
    "limits.no_genome_what": "О геноме нельзя сказать ничего.",
    "limits.assembly_what": "О геноме сказать нельзя ничего: файл в сборке {found}.",
    "limits.assembly_why": "Каталог координат написан в {want}, а файл вызван относительно {found}. Каждый локус искался бы не на своей позиции, поэтому геномный слой отключён, а не допущен к ответу.",
    "limits.assembly_closes": "Перевести файл в {want} (CrossMap или bcftools +liftover с chain-файлом) либо пере-вызвать варианты из выравнивания относительно этой сборки.",
    "limits.assembly_unknown_what": "Сборка геномного файла не установлена.",
    "limits.assembly_unknown_why": "Её не выдали ни заголовок, ни данные: нет длин контигов, нет `##reference`, и за концом первой хромосомы GRCh38 вариантов не нашлось. Ответы считаются так, будто файл в {want}; если это не так, каждый из них — про не ту позицию, и выглядеть неверным он не будет.",
    "limits.assembly_unknown_closes": "Выставить `SCHOLION_GENOME_ASSEMBLY` в ту сборку, что названа в отчёте о секвенировании (GRCh37 · GRCh38 · T2T-CHM13v2.0) — это всё лечение, одна строка. Если никто не помнит, прочитать из файла: `bcftools view -h <file> | grep '##contig' | head -1`, где chr1 на 249250621 — GRCh37, а 248956422 — GRCh38. Чтобы закрыть навсегда: `bcftools reheader -f <reference>.fai <file>`.",
    "limits.no_genome_why": "VCF не подключён: любой геномный ответ был бы про отсутствие файла, а не про тебя.",
    "limits.no_genome_closes": "Что закрывает: VCF из собственных ридов либо выгрузка из лаборатории. Путь описан в `scholion doc preparing-the-genome`.",
    "limits.weak_gene_what": "Отрицательный результат по {gene} — не утверждение.",
    "limits.weak_gene_why": "Достаточно глубоко для решения о гетерозиготе (>=10x) прочитано лишь {pct} % оснований гена; остальное не прочитано, а непрочитанное основание даёт то же «находок нет», что и чистое.",
    "limits.weak_gene_closes": "Более глубокое секвенирование либо прицельный анализ {gene} — под него недопокрытые участки выгружаются в BED.",
    "limits.gene_not_read_what": "Фармакогенетический фенотип {gene} не определён.",
    "limits.gene_not_read_why": "Маркёры гена не прочитаны.",
    "limits.gene_not_read_closes": "См. основание выше: там названы позиции и способ их прогенотипировать.",
    "limits.no_corridor_what": "{n} показателей печатаются без референсного коридора, а значит и без флага.",
    "limits.no_corridor_why": "Ни твой бланк, ни словарь не дают границ для: {markers}. Показать их против чужого коридора было бы хуже, чем без флага.",
    "limits.no_corridor_closes": "Внеси коридор со своего бланка: `add-lab <показатель> <дата> <значение> --unit ... --ref-low ... --ref-high ...`.",
    "limits.no_labs_what": "О лабораторном слое нельзя сказать ничего.",
    "limits.no_labs_why": "В профиле нет ни одного показателя.",
    "limits.no_labs_closes": "`import-labs panel.csv` для целой панели или `add-lab` для одного значения; папка PDF — через `ingest-labs`.",
    "limits.prs_what": "Процентиль по «{trait}» снят с доверия.",
    "limits.prs_why": "Вызвано лишь {pct} % вариантов модели — процентиль на таком входе это число без популяции за ним.",
    "limits.prs_closes": "Прогенотипируй позиции модели из BAM (src/ingest/prs_genotype_sites.sh) либо возьми модель с лучшим покрытием.",
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
    "limits.coverage_weak_line": "Ниже 90 %: {n} генов.",
    "limits.closes_label": "закрывается",
    "limits.summary": "{count} ограничений, у {closable} названо, чем закрыть.",
    "import.row": "строка {row}",
    "import.dry_ok": "файл чистый: импортировалось бы {n} строк. Ничего не записано — это был пробный прогон.",
    "import.written": "импортировано: {n} строк",
    "import.markers": "Показатели: {markers}",
    "import_csv.empty": "в файле нет строки заголовка",
    "import_csv.missing_columns": "не хватает обязательных колонок: {columns}. Найденный заголовок: {seen}. Ожидаются: marker, date, value и по желанию unit, ref_low, ref_high, note.",
    "import_csv.need_marker_date": "нет показателя или нет даты",
    "import_csv.value_not_number": "значение «{value}» не число",
    "import_csv.unknown_marker": "такого показателя нет. Возможно: {did_you_mean}",
    "import_csv.bad_unit": "единица «{unit}» этому показателю не подходит; принимаются: {accepted}",
    "import_csv.file_not_found": "файла {path} нет",
    "import_csv.unreadable": "{path} не открывается как текст UTF-8: {error}",
    "import_csv.nothing_written": "{n} строк не прошли — НИЧЕГО не записано. Файл импортируется целиком или никак: половина панели в профиле выглядит как целая.",
    "import_csv.write_failed": "строка {row} прошла проверку и упала на записи: {detail}. Дальше импорт не пошёл.",
    "store.marker_unknown": "показателя «{marker}» нет, а молчаливое создание — ровно то, из-за чего один анализ превращается в два ряда под двумя написаниями; ничего не записано. Возможно: {did_you_mean}. Чтобы завести осознанно, передай --new вместе с единицей.",
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
    "phenoage.no_age": "Неизвестен возраст: добавь birth_date в profile/metrics.json.",
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
    "reconcile.candidate_hint": "Рядом с каталогом данных лежит похожая на бланки папка: {path}. По догадке она НЕ читается — назови её один раз: SCHOLION_LABS_DIR='{path}', либо передай --lab-dir, либо перенеси бланки в raw/lab/.",
    "reconcile.no_folder": "Папка с бланками не найдена: {path}. Укажи --lab-dir PATH или "
                           "задай SCHOLION_LABS_DIR.",
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
    "selfcheck.unreadable_hint": "   → открой эти файлы на Mac (iCloud материализует), затем "
                                 "повтори проверку.",
    "selfcheck.ok": "✅ Целостность анализов: ОК — нечитаемых бланков нет.",
    "selfcheck.counters": "   бланков: {files} · совпало точек: {covered} · на ручную "
                          "проверку: {missing} пропуск(ов) / {mismatch} расхожд. (детально: "
                          "scholion reconcile)",

    # ── выгрузка Garmin ───────────────────────────────────────────────
    "garmin.builder_missing": "не найден {path}",
    "garmin.candidate_hint": "Рядом с каталогом данных лежит выгрузка носимого: {path}. По догадке она НЕ читается — назови её один раз: `scholion set-folder garmin '{path}'`, передай папку аргументом или перенеси в raw/wearables/.",
    "garmin.no_export": "Не найдена папка garmin_export (с DI_CONNECT). Скачай свежий "
                        "GDPR-экспорт Garmin (Connect → Настройки аккаунта → Экспорт данных), "
                        "распакуй в garmin_export рядом с проектом — или укажи путь явно.",
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
    "genome.clinvar_not_run": "Твой VCF ещё не аннотирован по ClinVar. Аннотация — часть "
                              "подготовки генома: `scholion doc preparing-the-genome`.",
    "genome.conflict": "Отчёт лаборатории и собственные чтения здесь расходятся: в отчёте "
                       "{reported}, в чтениях {called}. Выше показано то, что говорят чтения — "
                       "у них есть покрытие, их можно перепроверить, и отчёт сделан из них. "
                       "Такое расхождение имеет смысл отнести тому, кто выдал отчёт.",
    "genome.confirmed_by_report": "Собственные чтения и отчёт лаборатории в этой позиции совпадают.",
    "genome.acmg_not_run": "Твой VCF ещё не сверен со списком ACMG SF. Сверка — часть "
                           "подготовки генома: `scholion doc preparing-the-genome`.",
    "genome.apoe_ambiguous": "Обе точки гетерозиготны, и такой генотип — это {a} либо {b}, смотря какой аллель на какой хромосоме; этого файл не несёт. {a} заметно частотнее во всех изученных популяциях — это повод сказать, что вероятнее, а не повод напечатать это как ответ. Разрешается фазировкой или генотипом родителя.",
    "genome.apoe_unexpected": "rs429358 {a} при rs7412 {b} — комбинация, которой ε-гаплотипы не дают; проверьте вызовы, прежде чем что-то из них выводить",
    "genome.indels_not_left_aligned": "⚠ Вставки и делеции в этом списке сопоставлялись БЕЗ левого выравнивания: аннотация шла без референсной FASTA, поэтому индел, записанный иначе, чем копия в ClinVar, был не найден, а не найден и отвергнут. Замен это не касается. Задайте SCHOLION_REFERENCE_FASTA и перезапустите `annotate_clinvar.sh`.",
    "genome.apoe_note": "ε-статус приблизителен без фазировки; для клиники подтвердить.",
    "clinvar.tier.pathogenic": "Патогенные / вероятно патогенные",
    "clinvar.tier.pathogenic.hint": "надо знать: связь с болезнью или носительство",
    "clinvar.tier.drug": "Фармакогенетика",
    "clinvar.tier.drug.hint": "влияет на подбор/дозу лекарств — обсудить с врачом (см. "
                              "«Препараты»)",
    "clinvar.tier.risk": "Факторы риска",
    "clinvar.tier.risk.hint": "умеренно повышают риск — контекст для скрининга, не диагноз",
    "clinvar.tier.protective": "Защитные",
    "clinvar.tier.protective.hint": "вариант с защитным эффектом",
    "clinvar.tier.association": "Слабые ассоциации (GWAS)",
    "clinvar.tier.association.hint": "статистическая связь малой силы; не действие",
    "clinvar.tier.uncertain": "Неоднозначные / неопределённые",
    "clinvar.tier.uncertain.hint": "эксперты не сошлись во мнении — как правило, не риск",

    # ── инструментальные исследования и заключения врачей ─────────────
    "studies.kind_default": "исследование",
    "studies.from_conclusion": "из заключения",
    "studies.no_pdf_reader": "Не найден инструмент чтения PDF: pip3 install pdfplumber",
    "studies.folder_not_found": "Папка не найдена: {path}",
    "studies.meta_what": "ЛИЧНЫЕ инструментальные исследования и заключения врачей.",
    "studies.hint": "Поля answers/does_not_answer загрузчик НЕ заполняет — это суждение. "
                    "Пройди новые записи и допиши, на какие вопросы исследование отвечает, а "
                    "на какие нет.",

    # ── загрузка PDF-бланков анализов ─────────────────────────────────
    "ingest_labs.reason_several_dates": "в таблице {n} разных дат забора ({first} … {last}); этот импорт относит файл целиком к одной дате, а выбрать одну из нескольких значило бы угадать за человека",
    "ingest_labs.reason_ambiguous_date": "на бланке «{raw}» — это либо {first}, либо {second}; на странице не сказано, в каком порядке печатает эта лаборатория, а точка, попавшая не в тот месяц, встаёт в ряд и двигает тренд. Введите дату забора сами через `scholion add-lab` или возьмите выгрузку, где дата записана полностью",
    "ingest_labs.date_from_filename": "дата {date} взята из ИМЕНИ ФАЙЛА, а не с бланка — на самой странице её нет. Файл называет тот, кто его сохранил, и часто по дню скачивания",
    "ingest_labs.reason_no_date": "на бланке не нашлась дата взятия",
    "ingest_labs.reason_no_text": "в файле нет извлекаемого текста (скан без распознавания)",
    "ingest_labs.reason_table_labels": "{n} подписей строк этой таблицы не совпали ни с одним показателем словаря — они перечислены, а не сохранены под приблизительным именем",
    "ingest_labs.reason_no_marker": "дата прочитана, но ни одна строка не совпала с известным показателем",
    "fhir.title": "**Бандл FHIR:** {path} — наблюдений {observations}",
    "fhir.dry_run": "взял бы {n} результатов (ничего не записано)",
    "fhir.added": "внесено в профиль: {n}",
    "fhir.refused": "{label} — не записано: {reason}",
    "fhir.not_taken": "**Не взято, по причинам:**",
    "fhir.reason.no_quantity": "в ресурсе нет числового значения (кодированный результат, панель-группировка, вложение)",
    "fhir.reason.loinc_not_in_catalogue": "кода LOINC нет в словаре этой сборки — сопоставить по названию значило бы угадать, что это за показатель",
    "fhir.reason.no_loinc": "у наблюдения нет кода LOINC вовсе",
    "fhir.reason.no_date": "нет даты; результат без даты в ряду не место",
    "fhir.reason.not_final": "источник сам не считает результат окончательным (статус не final/amended/corrected)",
    "fhir.profile_facts": "бандл сообщает о своём пациенте ещё и {facts}. НЕ применено: файл может содержать родственника, образец или двух человек, а взять личность из файла — та ошибка, которая потом отравляет всё остальное. Если это вы — задайте сами: `scholion init --sex … --birth-year …`",
    "fhir.unreadable": "{path} не читается как JSON: {error}",
    "fhir.not_a_bundle": "это ресурс FHIR типа «{kind}», а не Bundle. Выгрузите бандл целиком — одиночный ресурс истории не несёт",
    "ingest_labs.folder_empty": "в {path} нет ни одного файла с результатами — ни PDF, ни выгрузки CSV/TSV/TXT",
    "ingest_labs.no_pdf_reader": "Не найден инструмент чтения PDF. Установи в Терминале: pip3 "
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
    "net.diag_host_refused": "проверка связи обращается только к справочным хостам, которые использует сам инструмент, и только по https — произвольный адрес не запрашивается",
    "net.offline_deliberate": "SCHOLION_OFFLINE=1 — сетевые запросы отключены сознательно",
    "net.offline_hint": "снимите переменную окружения SCHOLION_OFFLINE, если сеть нужна",
    "net.certificates_hint": "Похоже на отсутствие корневых сертификатов у Python на Mac. Один "
                             "раз выполни в Терминале: /Applications/Python\\ 3.13/Install\\ "
                             "Certificates.command (или: pip3 install --upgrade certifi).",
    "net.tls_verify_failed": "Проверка сертификата не прошла — запрос отменён. Ответ по "
                             "непроверенному каналу может быть подменён, а из него берётся класс "
                             "препарата и пара ген↔препарат. Обойти проверку осознанно: "
                             "SCHOLION_TLS_INSECURE=1.",
    "net.tls_insecure_warning": "⚠ SCHOLION_TLS_INSECURE=1 — сертификат НЕ проверяется, "
                                "ответ может быть подменён.",

    # ── расчёт полигенных баллов по PGS Catalog ───────────────────────
    "prs.no_uvx": "не найден uvx — установи uv (https://docs.astral.sh/uv)",
    "prs.server_silent": "сервер just-prs завершился без ответа",
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
    "web.header.local_badge_hint": "Почему это важно и как подключить модель — вкладка «Ассистент»",
    "web.header.disclaimer": "Не диагноз и не назначение. Материал для обсуждения с лечащим "
                             "врачом. Ассистент не меняет терапию.",
    "web.header.build": "сборка {version}",
    "web.header.language": "Язык интерфейса",

    # ── web: the tabs ────────────────────────────────────────────────────
    "web.tab.overview": "Обзор",
    "web.tab.labs": "Анализы",
    "web.tab.drugs": "Препараты",
    "web.tab.genome": "Геном",
    "web.tab.lifestyle": "Образ жизни",
    "web.tab.tests": "Что сдать",
    "web.tab.second_opinion": "Второй взгляд",
    "web.tab.prescriptions": "Назначения",
    "web.tab.assistant": "Ассистент",

    # ── web: words shared by every screen ────────────────────────────────
    "web.common.loading": "загрузка…",
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
    "web.goal.title": "Твоя цель по показателям",
    "web.goal.as_of": "данные на {date}",
    "web.goal.in_one_phrase": "Одной фразой:",
    "web.goal.targets_h": "Целевые показатели",
    "web.goal.col_marker": "Показатель",
    "web.goal.col_now": "Сейчас",
    "web.goal.col_best": "Твой лучший (год)",
    "web.goal.col_target": "Цель",
    "web.goal.lg_now": "сейчас",
    "web.goal.lg_best": "лучшее историческое",
    "web.goal.lg_target": "цель",
    "web.goal.lg_window": "твоё опорное окно",
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
                     "появляются сами; сверяй их с жёлтыми целевыми линиями и зелёным опорным "
                     "окном — и то и другое берётся из цели, заданной тобой в health_goals.json. "
                     "Там, где цель — состав тела, ключевая метрика {key_metric}, а не только "
                     "цифра на весах.",
    "web.goal.note_key": "жир вниз при мышце на месте",
    "web.goal.chart_nodata": "Рядов здесь пока нет — график появится, когда будет что "
                             "рисовать.",
    "web.goal.charts_unavailable": "Графики недоступны (не загрузился chart.min.js). Перезапусти "
                                   "приложение и обнови страницу.",

    # ── web: overview ────────────────────────────────────────────────────
    "web.header.subject": "субъект {subject}",
    "web.header.genome_gaps": "{n} целевых генов не прочитано из генома",
    "web.header.demo_banner": "ДЕМО — вымышленный человек. Ничто на этих экранах не относится "
                              "к вам: числа, назначения и генотипы сгенерированы. Свой профиль "
                              "заводится командой «scholion init».",
    "count.prescriptions.one": "{n} назначение",
    "count.prescriptions.few": "{n} назначения",
    "count.prescriptions.many": "{n} назначений",
    "web.overview.focus_h": "Фокус внимания",
    "web.overview.watched_h": "Показатели под контролем",
    "web.overview.stat_above": "из них выше потолка",
    "web.overview.stat_below": "из них ниже пола",
    "web.overview.stat_abnormal": "вне нормы из измеренных маркёров",
    "web.overview.stat_suggested": "анализов к сдаче",
    "web.overview.stat_note": "Второе и третье числа делят первое по направлению — ниже пола "
                              "не мягче, чем выше потолка. Четвёртое — это список на вкладке "
                              "«Что сдать».",
    "web.overview.red_h": "Вне нормы сейчас",
    "web.overview.red_window": "за последние 12 месяцев",
    "web.overview.stale_hidden": "Ещё {count} старше 12 мес. скрыто — смотри на вкладке «Анализы».",
    "web.overview.tests_h": "Что сдать",
    "web.overview.no_red": "Отклонений среди {n} измеренных показателей нет.",
    "web.overview.no_red_nodata": "Ничего ещё не измерено, поэтому и отмечать нечего. "
                                  "Загрузите анализы — и эта строка начнёт что-то значить.",
    "web.overview.no_priority_tests": "Из того, что сейчас в профиле, нового назначения не "
                                      "следует. Плановый контроль и интервалы повторов — на "
                                      "вкладке «Что сдать».",

    # ── web: focus of attention ──────────────────────────────────────────
    "web.focus.track_tip": "база {base} · сейчас {now} · ориентир {target}",
    "web.focus.baseline": "база {value}",
    "web.focus.target": "ориентир {value} {unit}",
    "web.focus.since": "с {date}",
    "web.focus.vs_baseline": "{delta} к базе",
    "web.focus.mean_over": "среднее за {n} ноч. {from} → {to}",
    "web.focus.levers_h": "Рычаги — что показывают собственные данные",
    "web.focus.expected_prefix": "ожидаемо ",
    "web.focus.now": "сейчас: {text}",
    "web.focus.journal_h": "Журнал эпизодов",
    "web.focus.journal_count": "· {n} записей",
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
    "web.labs.docs_folder_unset": "Укажи ОДНУ папку с исходными PDF (напр. «Лабораторные "
                                  "исследования»). Приложение само извлечёт показатели с датами и "
                                  "создаст сводку анализов — отдельный labs.json выбирать не "
                                  "нужно.",
    "web.labs.reading_pdf": "Читаю PDF из папки…",
    "web.labs.ingest_files": "Обработано файлов: {n}",
    "web.labs.ingest_points": ", добавлено точек: {points}, пропущено (без изменений/не анализы): "
                              "{skipped}.",
    "web.labs.ingest_nothing_new": "Новых показателей не найдено (возможно, всё уже загружено).",
    "web.labs.points_added": "Добавлено {n} точек ✓",
    "web.labs.no_new_data": "Новых данных нет",
    "web.labs.add_note": "Новая точка добавится в labs.json (profile). Инструменты и тренды "
                         "обновятся сразу.",
    "web.labs.genome_link": "геном: {text}",

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
    "web.form.fill_required": "Заполни показатель, дату и значение",

    # ── web: the drug check ──────────────────────────────────────────────
    "web.drug.title": "Проверка назначения",
    "web.drug.intro": "«Полная проверка» = фармакогенетика + взаимодействия с твоими текущими "
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
    "web.dose.your_numbers": "твои цифры:",
    "web.dose.not_measured": "не сдавал",
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
    "web.rx.no_pgx": "Значимой фармакогенетики по этому препарату не выявлено (CPIC): генов, "
                     "влияющих на дозу/эффект, нет.",
    "web.rx.curated_value": "куратор",
    "web.rx.actionable": "важен",
    "web.rx.your_phenotype": "твой фенотип:",
    "web.rx.your_variants": "твои варианты:",
    "web.rx.no_lab_control": "Специфического лабораторного контроля по классу не требуется.",
    "web.rx.not_taken_yet": "ещё не сдавал",
    "web.rx.monitor_while": "Контролировать при приёме: {text}",
    "web.rx.near_note": "В норме, но у границы коридора: {names} — при этом препарате следить "
                        "особенно.",
    "web.rx.watch_note": "У тебя уже отклонены: {names} — это важно учесть при этом препарате.",
    "web.rx.with_yours": "с твоими:",
    "web.rx.mechanism": "механизм: {text}",
    "web.rx.what_to_do": "что делать: {text}",
    "web.rx.no_interactions_partial": "Явных взаимодействий с опознанной частью твоего текущего "
                                      "списка не найдено. НЕ сравнивалось, потому что класс не "
                                      "определён: {names}.",
    "web.rx.no_interactions": "Явных взаимодействий с твоими текущими назначениями не найдено.",
    "web.rx.via_gene": "ген {gene}",
    "web.rx.via_drug_name": "по названию препарата",
    "web.rx.genotype": "генотип {genotype}",
    "web.rx.clinvar_h": "ClinVar по препарату",
    "web.rx.clinvar_note": "твои варианты из свежей ClinVar, связанные с этим лекарством",
    "web.rx.h_genome": "Твой геном",
    "web.rx.h_labs": "Твои анализы",
    "web.rx.h_meds": "Твои назначения",

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
    "web.radar.not_enough": "Недостаточно данных для диаграммы (нужно ≥3 системы с анализами). "
                            "Загрузи анализы из папки на вкладке «Анализы».",
    "web.radar.tip": "{label}: {score}/100 ({ok}/{total} в норме)",
    "web.radar.tip_partial": "{label}: {score}/100 (в норме {ok} из {measured} измеренных; "
                             "в домене заявлено {total})",
    "web.radar.was": "было {score}/100 по {compared} показателям, у которых есть более "
                     "ранняя точка ({date}) — {word}",
    "web.radar.prev_measurement": "пред. измерение",
    "web.radar.no_previous": "нет предыдущего измерения для сравнения",
    "web.radar.now": "сейчас",
    "web.radar.previous": "прошлое измерение",
    "web.second.title": "Второй взгляд перед визитом к врачу",
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
    "web.second.routine_elsewhere": "Ещё {n} — плановый контроль: уже сдано, следим по интервалу. "
                                    "Они на вкладке",

    # ── предложение цели ─────────────────────────────────────────────────
    "goalgen.why.guideline": "{body} публикует этот ориентир ({year}).",
    "goalgen.why.guideline_conditional": "{body} публикует этот ориентир ({year}) для людей "
                                         "с состоянием «{condition}». Относится ли это к "
                                         "тебе — по профилю не подтвердить.",
    "goalgen.why.no_target": "{body} рассмотрело этот маркёр и отказалось задавать целевое "
                             "значение. Это и есть вывод, а не пробел — числа здесь не "
                             "предлагается.",
    "goalgen.why.personal_best": "Лучшее, чего ты достигал — {date}, из {n} измерений за "
                                 "{months} мес. Это не чья-то рекомендация, это твои "
                                 "собственные измерения.",
    "goalgen.why.reference": "Стенка лабораторного коридора. Слабее двух других: «внутри "
                             "нормы» — это то, где большинство и так находится, а не цель.",
    "goalgen.how_to_read": "Это предложение, а не назначение. Там, где клиническая ассоциация "
                           "опубликовала ориентир, он приведён с источником; иначе предлагается "
                           "твой собственный лучший результат — факт о тебе, а не совет. Любое "
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
    "goalgen.none": "Пока ничему здесь нельзя назначить цель. Загрузи ещё анализов — и ответ "
                    "будет другим.",
    "goalgen.skipped_h": "Для чего цель не предложена и почему",
    "goalgen.src.guideline": "клиническое руководство",
    "goalgen.src.personal_best": "твой собственный максимум",
    "goalgen.src.reference": "лабораторный коридор",
    "web.goalgen.h": "Пусть приложение предложит цель",
    "web.goalgen.intro": "Оно читает то, что ты измерил, и то, что публикуют клинические "
                         "ассоциации, и предлагает ориентир для каждого маркёра, для которого "
                         "хватает оснований. Каждая строка говорит, откуда взято число. Пока не "
                         "нажмёшь «Сохранить», ничего не записывается.",
    "web.goalgen.btn": "Предложить цель",
    "web.goalgen.save": "Сохранить отмеченные",
    "web.goalgen.saved": "Записано в profile/health_goals.json — целей: {n}.",
    "web.goalgen.now": "сейчас",
    "web.goalgen.reached": "ты здесь уже был",
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
                                   "(copy-number), который короткие чтения и SNP-чипы видят плохо. "
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
    "web.meds.add": "Добавить",
    "web.meds.remove": "удалить",
    "web.meds.empty": "Пока пусто.",
    "web.meds.enter_name": "Введите препарат",
    "web.meds.added_attention": "Добавлено — есть на что обратить внимание",
    "web.meds.removed": "Удалено",

    # ── web: personal metrics ────────────────────────────────────────────
    "web.metrics.title": "Личные показатели здоровья",
    "web.metrics.sex": "пол",
    "web.metrics.sex_label": "Пол",
    "web.metrics.male": "муж",
    "web.metrics.female": "жен",
    "web.metrics.age": "возраст",
    "web.metrics.height": "рост, см",
    "web.metrics.height_label": "Рост, см",
    "web.metrics.bmi": "ИМТ",
    "web.metrics.profile_btn": "Профиль (рост/год/пол)",
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
    "web.bullet.src_goal": "заданная тобой цель",
    "web.bullet.src_ref": "граница коридора лаборатории",
    "web.bullet.src_norm": "общая рекомендация",
    "web.bullet.src_own": "выведено из твоих собственных данных",
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
    "web.life.garmin_btn": "Обновить из Garmin-экспорта",
    "web.life.garmin_note": "пересобирает из свежего GDPR-экспорта Garmin (garmin_export) с "
                            "бэкапом",
    "web.life.rebuilding": "пересобираю…",
    "web.life.garmin_done": "Garmin обновлён: {metrics} метрик ({range})",
    "web.life.garmin_nights": "ночей сна {n}",
    "web.life.garmin_preserved": "сохранено из прежнего файла {n} точек",
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
    "web.life.enter_waist": "Введи объём талии, см",
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
    "web.brief.new_data": "Появились новые данные после последней правки формулировок:",
    "web.brief.block_dates": "текст от {reviewed}, данные от {newest}",
    "web.brief.numbers_note": "Числа пересчитаны автоматически — пересмотра требуют выводы. "
                              "Попроси ассистента обновить справку.",
    "web.brief.dropped_h": "Снятые тревоги — чего делать не надо",
    "web.brief.compiled": "Формулировки от {date}; числа подставляются из профиля при каждом "
                          "открытии.",

    # ── web: genome ──────────────────────────────────────────────────────
    "web.genome.title": "Геном — комплексный анализ",
    "web.genome.nav_summary": "Сводка",
    "web.genome.nav_updates": "Обновления",
    "web.genome.nav_risks": "Риски (PGS)",
    "web.genome.nav_longevity": "Долголетие",
    "web.genome.nav_clinvar": "ClinVar",
    "web.genome.nav_locus": "Поиск локуса",
    "web.genome.db_connected": "база подключена",
    "web.genome.db_not_connected": "база не подключена",
    "web.genome.db_after_script": "геномная часть отвечает, когда подключён полный VCF — "
                                 "как его получить, описано в "
                                 "`scholion doc preparing-the-genome`",
    "web.genome.intro": "Всё про твой геном в одном месте: и преимущества, и риски. Ниже — что "
                        "нового в базах, полигенные риски, долголетие, клинически значимые находки "
                        "ClinVar и поиск любого локуса. Ничего не покидает машину. Не диагноз — "
                        "материал к врачу.",
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
    "web.genome.assumed_ref": "референс (не вариантный сайт)",

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
    "web.longevity.carries": "несёт аллель",
    "web.longevity.stat_checked": "вариантов проверено",
    "web.longevity.stat_carrier": "значимых-носитель",
    "web.longevity.stat_genes": "генов",
    "web.longevity.key_markers_h": "Ключевые маркёры",
    "web.longevity.by_gene_h": "Значимые носительства по генам",
    "web.longevity.by_gene_note": "Литературный каталог: ты носитель варианта, изучавшегося при "
                                  "долголетии. Направление большинства ассоциаций не закодировано "
                                  "— навигатор по генам, не оценка риска.",

    # ── web: ClinVar findings ────────────────────────────────────────────
    "web.clinvar.not_run": "ClinVar-аннотация ещё не запускалась.",
    "web.clinvar.nothing": "Значимых находок не извлечено",
    "web.clinvar.experts": "эксперты",
    "web.clinvar.several_labs": "неск. лабораторий",
    "web.clinvar.actionable_of": "действенных находок из {total}",
    "web.clinvar.intro": "Твои варианты, размеченные свежей ClinVar. Важное сверху: {pathogenic} "
                         "(носительство/болезнь), {pgx} (лекарства), {risk}. Остальные {n} "
                         "(слабые/неоднозначные) — под катом, обычно не риск. Не диагноз.",
    "web.clinvar.w_pathogenic": "патогенные",
    "web.clinvar.w_pgx": "фармакогенетика",
    "web.clinvar.w_risk": "факторы риска",
    "web.clinvar.show_weak": "Показать слабые и неоднозначные ({n})",

    # ── web: checking the databases for updates ──────────────────────────
    "web.updates.never": "Проверок ещё не было. Нажми «Проверить обновления» — приложение сверит "
                         "твой геном со свежей ClinVar и покажет, что нового.",
    "web.updates.last_check": "Последняя проверка:",
    "web.updates.nothing_new": "Ничего нового с прошлой проверки.",
    "web.updates.new_h": "Новые находки ({n})",
    "web.updates.changed_h": "Изменилась классификация ({n})",
    "web.updates.check_btn": "Проверить обновления",
    "web.updates.in_progress": "идёт проверка…",
    "web.updates.downloading": "Скачиваю свежую ClinVar и сверяю с твоим геномом — это несколько "
                               "минут.",
    "web.updates.failed": "Проверка не завершилась (код {code}).",

    # ── web: the assistant tab ───────────────────────────────────────────
    "web.assistant.title": "Ассистент — необязательный слой",
    "web.assistant.works_without": "приложение работает без ассистента",
    "web.assistant.everything_local": "Все числа, флаги, тренды, фармакогенетика, «второе мнение» "
                                      "и чеклист следующего забора считаются кодом на вашей "
                                      "машине. Ни интернет, ни языковая модель для этого не нужны.",
    "web.assistant.scan_lead": "Проверено сканом собственного кода при открытии вкладки:",
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
                       "именно твои числа — написано на том экране, где они показаны, рядом "
                       "с числом.",

    "web.guide.sources_h": "Откуда взято число",
    "web.guide.sources_body": "Большинство вкладок открываются строкой мелких меток над "
                              "содержимым. Метка показывает, откуда вкладка взяла данные: из "
                              "твоих файлов на этой машине, или из публичной справочной базы, "
                              "к которой обратились по сети (ClinVar, RxClass, Ensembl). Ничего "
                              "не утверждается без одного из этих двух источников, и оба никогда "
                              "не окрашены одинаково. Подключена ли на вкладке «Ассистент» "
                              "языковая модель или нет — на это различие не влияет: сами числа "
                              "всегда считает код на твоей машине.",

    "web.guide.status_h": "Цвета и значки",
    "web.guide.status_intro": "Одни и те же пять значков повторяются почти на каждой вкладке. "
                              "Цвет никогда не бывает единственным сигналом — рядом всегда "
                              "стоит число и подпись, так что значок остаётся читаемым, даже "
                              "если цвет неразличим.",
    "web.guide.status_good_label": "норма",
    "web.guide.status_good_why": "Цель достигнута, или цели нет, а значение — внутри "
                                 "референсного коридора.",
    "web.guide.status_warning_label": "внимание",
    "web.guide.status_warning_why": "Внутри референсного коридора, но личная цель ещё не "
                                    "достигнута — либо фармакогенетический эффект, о котором "
                                    "стоит помнить, но не тревожный сигнал.",
    "web.guide.status_critical_label": "критично",
    "web.guide.status_critical_why": "Вне референсного коридора лаборатории, либо тревожный "
                                     "сигнал, поднятый из твоего же профиля.",
    "web.guide.status_near_label": "у границы",
    "web.guide.status_near_why": "Формально внутри нормы, но у самой её стенки. Показано синим, "
                                 "а не жёлтым, намеренно — чтобы человек с нарушением "
                                 "цветовосприятия видел отличие от «внимания» в самом тоне, а не "
                                 "только в подписи.",
    "web.guide.status_unknown_label": "нет данных",
    "web.guide.status_unknown_why": "Пока не о чем судить — не измерено, либо не найдено в "
                                    "твоих файлах.",
    "web.guide.status_three_note": "Само суждение использует три уровня, а не пять: норма, "
                                   "внимание, критично. Четвёртый, почти неотличимый уровень "
                                   "пробовали и отказались от него — при обычном контрасте он "
                                   "неотличим от «внимания» для обычного зрения. «У границы» и "
                                   "«нет данных» — не уровни тяжести; они отмечают другое: "
                                   "положение значения или его отсутствие.",

    "web.guide.tour_h": "Что делает каждая вкладка",
    "web.guide.tour_overview": "Первый экран: карточка «в фокусе внимания» — на что стоит "
                               "посмотреть в первую очередь и почему — а под ней панель цели, "
                               "если задана цель по форме тела.",
    "web.guide.tour_labs": "Каждый сданный анализ, сверенный со своим референсным диапазоном, "
                           "с трендом там, где измерений достаточно.",
    "web.guide.tour_drugs": "Проверить препарат по названию до приёма: быстрая проверка только "
                            "по фармакогенетике, или полная — геном, текущие анализы, "
                            "взаимодействия с тем, что уже принимаешь, и ClinVar.",
    "web.guide.tour_genome": "Полигенные риски как перцентили в популяции, варианты, связанные "
                             "с долголетием, находки ClinVar в твоём геноме, проверка на то, "
                             "что изменилось со времени последнего чтения ClinVar, и поиск по "
                             "гену или rsID.",
    "web.guide.tour_lifestyle": "Показатели с носимых устройств на фоне личной цели, полоса "
                                "«сейчас → цель» по каждому показателю и история тренировок.",
    "web.guide.tour_tests": "Что имеет смысл сдать в следующий раз и что сдавалось достаточно "
                            "недавно, чтобы пропустить.",
    "web.guide.tour_second_opinion": "Одна страница, объединяющая радар по направлениям "
                                     "здоровья, фармакогенетические флаги по текущим "
                                     "назначениям и предложенные анализы — сделана для печати "
                                     "и похода к врачу.",
    "web.guide.tour_prescriptions": "Препараты, которые ты принимаешь. Добавление нового "
                                    "запускает ту же проверку взаимодействий, что и вкладка "
                                    "проверки препарата, — против остального списка.",
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
    "web.guide.term_sources_body": "«Локальное» — это файл, уже лежащий на этой машине: твои "
                                   "анализы, твой геном, твои назначения. «Публичное» — "
                                   "справочная база, к которой обращаются по сети, чтобы их "
                                   "истолковать: ClinVar — для значимости вариантов, RxClass — "
                                   "для классов препаратов, Ensembl — для координат. Движок "
                                   "никогда не отправляет содержимое твоих файлов в публичный "
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
    "server.no_labs_folder": "Не выбрана папка исследований. Нажми «📁 Папка исследований».",
    "server.context_not_saved": "не удалось сохранить: {error}",
    "server.update.no_bcftools": "Нет bcftools в PATH приложения. Запусти update_check.sh из "
                                 "терминала, где доступен brew.",
    "server.selfcheck_skipped": "(самопроверка анализов пропущена: {error})",
    "server.already_running": "Scholion уже запущен: {url} — открываю в браузере.",
    "server.no_free_port": "Не удалось занять порт в диапазоне {first}–{last}. Закрой лишние окна "
                           "приложения и запусти снова.",
    "server.port_busy": "Порт {wanted} занят — запускаюсь на свободном порту {chosen}.",
    "server.listening": "Scholion: {url}  (Ctrl+C для остановки)",
    "server.profile": "Профиль: {path}",
    "server.stopped": "Остановлено.",
    # --- external command-line tools (scholion tools) ---------------------
    "tools.title": "**Внешние инструменты**",
    "tools.intro": "Сам разбор работает на стандартной библиотеке. Подготовка геномных данных — "
                   "нет: прочитать VCF, проиндексировать его и измерить покрытие умеют отдельные "
                   "программы. Ниже — что есть, а чего нет.",
    "tools.manager_found": "менеджер пакетов: {name}",
    "tools.no_manager": "Поддерживаемый менеджер пакетов не найден. Эта команда умеет Homebrew "
                        "(brew.sh) и conda/mamba — оба ставят в твой домашний каталог. Поставь "
                        "один из них или установи инструменты так, как принято в твоей системе.",
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
    "tools.not_a_tty": "Не спрашиваю — это не интерактивный терминал. Запусти "
                       "`scholion tools --install`, когда будет удобно.",
    "tools.ask": "Установить сейчас? [y/N] ",
    "tools.yes_words": "y,yes,д,да",
    "tools.declined": "Пропускаю. `scholion tools --install` сделает это позже; больше ничего не "
                      "меняется.",
    "tools.installed_ok": "✓ установлено: {tools}",
    "tools.install_failed": "✗ по-прежнему нет: {tools}",
}
