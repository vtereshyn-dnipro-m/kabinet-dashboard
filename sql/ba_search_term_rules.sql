-- 14.09.2026. Правила отбора фраз из Brand Analytics Top Search Terms.
--
-- Полный отчёт за неделю по одному рынку — 143 тыс. фраз и 426 тыс. строк (ES,
-- 162 МБ JSON). Хранить всё по восьми рынкам бессмысленно: 99 % — чужие категории
-- (ежедневники, косметика). Загрузчик оставляет фразу, если выполнено хотя бы одно:
--   top_n    — фраза входит в первые N по searchFrequencyRank (общая картина спроса);
--   category — фраза матчит регулярку категории на языке рынка (наша семантика,
--              замена Helium);
--   own      — среди топ-3 кликнутых ASIN есть наш (всегда, без правила), плюс
--              один «прыжок»: все фразы, где кликают те же конкурирующие ASIN.
-- Регулярки — стартовый словарь по инструменту, править здесь, не в коде.
CREATE TABLE IF NOT EXISTS kabinet_data.ba_search_term_rules (
    id          SERIAL PRIMARY KEY,
    marketplace TEXT NOT NULL,                 -- ES, DE, FR, IT, GB, NL, PL, BE
    rule_type   TEXT NOT NULL CHECK (rule_type IN ('top_n', 'category')),
    value       TEXT NOT NULL,                 -- top_n: число; category: регулярка (POSIX/Java, без учёта регистра)
    note        TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT ON kabinet_data.ba_search_term_rules TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";  -- сервис-принципал Claude Code, под ним джоб
GRANT SELECT ON kabinet_data.ba_search_term_rules TO claude_code_ro;

INSERT INTO kabinet_data.ba_search_term_rules (marketplace, rule_type, value, note) VALUES
 ('ES','top_n','5000','по решению владельца 14.09.2026: первые 5 000 фраз рынка'),
 ('DE','top_n','5000',NULL),('FR','top_n','5000',NULL),('IT','top_n','5000',NULL),
 ('GB','top_n','5000',NULL),('NL','top_n','5000',NULL),('PL','top_n','5000',NULL),('BE','top_n','5000',NULL),
 ('ES','category','motosierra|atornillador|destornillador|taladro|amoladora|radial|soplador|desbrozadora|martillo|perforador|sierra|lijadora|cortasetos|pulverizador|sulfatadora|hidrolimpiadora|bater[ií]a (20|40) ?v|llave de impacto|multiherramienta|compresor|generador|cortac[eé]sped|aspirador de hojas|ingletadora|caladora|fresadora|pistola de calor|dnipro','электроинструмент и сад, стартовый словарь'),
 ('DE','category','kettensäge|akkuschrauber|bohrschrauber|bohrmaschine|winkelschleifer|laubbläser|freischneider|motorsense|bohrhammer|säge|schleifer|heckenschere|drucksprüher|hochdruckreiniger|akku (20|40) ?v|schlagschrauber|multitool|kompressor|stromerzeuger|rasenmäher|kappsäge|stichsäge|oberfräse|heißluftpistole|dnipro','стартовый словарь'),
 ('FR','category','tronçonneuse|visseuse|perceuse|meuleuse|souffleur|débroussailleuse|perforateur|scie|ponceuse|taille-haie|pulvérisateur|nettoyeur haute pression|batterie (20|40) ?v|clé à chocs|outil multifonction|compresseur|groupe électrogène|tondeuse|scie à onglet|scie sauteuse|défonceuse|décapeur thermique|dnipro','стартовый словарь'),
 ('IT','category','motosega|avvitatore|trapano|smerigliatrice|flessibile|soffiatore|decespugliatore|tassellatore|perforatore|sega|levigatrice|tagliasiepi|pompa a spalla|idropulitrice|batteria (20|40) ?v|utensile multifunzione|compressore|generatore|tosaerba|troncatrice|seghetto alternativo|fresatrice|pistola termica|dnipro','стартовый словарь'),
 ('GB','category','chainsaw|drill|screwdriver|angle grinder|leaf blower|brush cutter|strimmer|rotary hammer|sds|saw|sander|hedge trimmer|sprayer|pressure washer|(20|40) ?v battery|impact wrench|multi ?tool|compressor|generator|lawn ?mower|mitre saw|jigsaw|router|heat gun|dnipro','стартовый словарь'),
 ('NL','category','kettingzaag|schroefmachine|boormachine|accuboor|haakse slijper|bladblazer|bosmaaier|boorhamer|zaag|schuurmachine|heggenschaar|drukspuit|hogedrukreiniger|accu (20|40) ?v|slagmoersleutel|multitool|compressor|generator|grasmaaier|afkortzaag|decoupeerzaag|bovenfrees|heteluchtpistool|dnipro','стартовый словарь'),
 ('PL','category','piła łańcuchowa|pilarka|wkrętarka|wiertarka|szlifierka kątowa|dmuchawa|kosa spalinowa|podkaszarka|młot udarowy|młotowiertarka|piła|szlifierka|nożyce do żywopłotu|opryskiwacz|myjka ciśnieniowa|akumulator (20|40) ?v|klucz udarowy|multitool|kompresor|agregat|kosiarka|ukośnica|wyrzynarka|frezarka|opalarka|dnipro','стартовый словарь'),
 ('BE','category','tronçonneuse|visseuse|perceuse|meuleuse|souffleur|débroussailleuse|perforateur|scie|ponceuse|taille-haie|pulvérisateur|nettoyeur haute pression|batterie (20|40) ?v|clé à chocs|outil multifonction|compresseur|tondeuse|kettingzaag|schroefmachine|boormachine|accuboor|haakse slijper|bladblazer|bosmaaier|boorhamer|zaag|schuurmachine|heggenschaar|hogedrukreiniger|accu (20|40) ?v|grasmaaier|dnipro','FR + NL');

SELECT marketplace, rule_type, left(value, 40) AS value FROM kabinet_data.ba_search_term_rules ORDER BY rule_type, marketplace;

-- Джоб 807913225672389 создан 14.09.2026 сервис-принципалом, среда 03:30 Kyiv (тихое окно квоты).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (807913225672389, 'Kabinet - Brand Analytics Loader', 192, 'WED 03:30 Kyiv weekly', 'Brand Analytics: Top Search Terms (отбор по ba_search_term_rules), Item Comparison, Alternate Purchase; 8 рынков')
ON CONFLICT DO NOTHING;

-- Стоп-слова (rule_type = 'exclude'): первый прогон показал, что «tondeuse» ловит машинки
-- для бороды, «ponceuse» — пилки для ногтей, «drill»/«saw» — пазлы и «no drill blinds».
-- Фраза с категорийным словом, но со стоп-словом, категорией не считается.
ALTER TABLE kabinet_data.ba_search_term_rules DROP CONSTRAINT IF EXISTS ba_search_term_rules_rule_type_check;
ALTER TABLE kabinet_data.ba_search_term_rules ADD CONSTRAINT ba_search_term_rules_rule_type_check CHECK (rule_type IN ('top_n', 'category', 'exclude'));
INSERT INTO kabinet_data.ba_search_term_rules (marketplace, rule_type, value, note) VALUES
 ('ES','exclude','uñas|pelo|barba|cabello|perro|gato|niñ|puzzle|aceitera|cocina|dental|maquillaje','стоп-слова'),
 ('DE','exclude','nagel|nägel|haar|bart|hund|katze|kinder|puzzle|küche|zahn|make-?up','стоп-слова'),
 ('FR','exclude','barbe|cheveux|ongle|poil|chien|chat|enfant|puzzle|cuisine|dentaire|maquillage','стоп-слова'),
 ('IT','exclude','unghie|capelli|barba|cane|gatto|bambin|puzzle|cucina|dental|trucco','стоп-слова'),
 ('GB','exclude','puzzle|nail|hair|beard|dog|cat|toy|kids|lego|kitchen|dental|makeup|no drill|blind','стоп-слова'),
 ('NL','exclude','nagel|haar|baard|hond|kat|kinder|puzzel|keuken|tand|make-?up','стоп-слова');
