"""Generate ``data/trails_seed.json`` from the curated trails table below.

Run from the project root:

    python -m scripts.generate_trails

The data here is hand-curated and covers all 26 cantons. Coordinates,
altitudes, difficulties, and lengths are realistic but approximate — good
enough for a hiking-condition demo, not for navigation.

To extend: append a row to ``TRAILS`` (any canton). The script validates
schema and writes a fresh ``trails_seed.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "trails_seed.json"

# Each row: name, canton, region, difficulty, min_alt_m, max_alt_m, lat, lon, length_km
# Regions: "Alps", "Pre-Alps", "Jura", "Mittelland".
# Difficulty follows the SAC scale: T1 (easy hike) … T6 (alpine).

TRAILS: list[tuple] = [
    # ---------- Valais (VS) ----------
    ("Matterhorn — Hörnlihütte", "VS", "Alps", "T4", 2583, 3260, 45.9800, 7.6506, 6.8),
    ("Gornergrat Panorama", "VS", "Alps", "T2", 2582, 3089, 45.9837, 7.7842, 7.1),
    ("Riffelsee Loop", "VS", "Alps", "T2", 2582, 2776, 45.9839, 7.7570, 4.5),
    ("Stockhorn (Zermatt)", "VS", "Alps", "T3", 3089, 3405, 45.9889, 7.8000, 5.0),
    ("Zermatt — Sunnegga", "VS", "Alps", "T1", 1620, 2288, 46.0260, 7.7500, 3.0),
    ("Zermatt — Edelweiss", "VS", "Alps", "T2", 1620, 2150, 46.0260, 7.7320, 5.5),
    ("Saas-Fee — Hannig", "VS", "Alps", "T1", 1800, 2336, 46.1100, 7.9300, 3.4),
    ("Saas-Fee — Plattjen", "VS", "Alps", "T2", 1800, 2570, 46.1100, 7.9400, 5.0),
    ("Britanniahütte", "VS", "Alps", "T3", 2350, 3030, 46.0833, 7.9667, 6.0),
    ("Mattmark Stausee", "VS", "Alps", "T2", 2197, 2350, 46.0233, 7.9700, 7.0),
    ("Aletsch — Eggishorn", "VS", "Alps", "T2", 2200, 2927, 46.4300, 8.0900, 5.5),
    ("Aletsch — Bettmerhorn", "VS", "Alps", "T2", 1950, 2872, 46.3917, 8.0500, 6.0),
    ("Aletsch — Märjelensee", "VS", "Alps", "T3", 2200, 2360, 46.4400, 8.0700, 7.5),
    ("Riederfurka — Riederalp", "VS", "Alps", "T2", 1925, 2065, 46.3833, 8.0250, 4.0),
    ("Belalp — Aletsch", "VS", "Alps", "T2", 2090, 2095, 46.3933, 8.0050, 6.5),
    ("Cabane des Vignettes", "VS", "Alps", "T4", 2300, 3160, 46.0167, 7.5333, 8.0),
    ("Pigne d'Arolla approach", "VS", "Alps", "T4", 2050, 3796, 45.9667, 7.5167, 9.0),
    ("Pas de Chèvres", "VS", "Alps", "T3", 1950, 2855, 46.0500, 7.4833, 6.0),
    ("Cabane de Bertol", "VS", "Alps", "T4", 1900, 3311, 46.0167, 7.4833, 7.5),
    ("Mont Fort", "VS", "Alps", "T3", 2200, 3329, 46.0833, 7.3000, 7.0),
    ("Cabane Mont Fort", "VS", "Alps", "T2", 2200, 2457, 46.0833, 7.2833, 4.0),
    ("Pierre Avoi", "VS", "Alps", "T3", 1900, 2473, 46.1167, 7.2167, 5.5),
    ("Verbier — Croix-de-Cœur", "VS", "Alps", "T2", 1500, 2174, 46.1000, 7.2167, 4.5),
    ("Crans-Montana — Bella Lui", "VS", "Alps", "T2", 2096, 2543, 46.3167, 7.4833, 5.0),
    ("Plaine Morte", "VS", "Alps", "T3", 2360, 2927, 46.3833, 7.5167, 6.0),
    ("Anzère — Tsalan d'Arbaz", "VS", "Alps", "T2", 1500, 2200, 46.3000, 7.4000, 5.5),
    ("Lötschenpass", "VS", "Alps", "T4", 1400, 2690, 46.4667, 7.7500, 9.0),
    ("Hockenhorn", "VS", "Alps", "T3", 2200, 3293, 46.4500, 7.7333, 7.5),
    ("Cabane de Moiry", "VS", "Alps", "T3", 2249, 2825, 46.1333, 7.6000, 5.0),
    ("Cabane Tracuit", "VS", "Alps", "T4", 1670, 3256, 46.1500, 7.6833, 9.5),

    # ---------- Graubünden (GR) ----------
    ("Piz Languard", "GR", "Alps", "T3", 2240, 3262, 46.5050, 9.9294, 5.9),
    ("Muottas Muragl — Alp Languard", "GR", "Alps", "T2", 2130, 2700, 46.5189, 9.9144, 6.3),
    ("Diavolezza", "GR", "Alps", "T3", 2093, 2978, 46.4083, 9.9667, 4.5),
    ("Morteratsch Glacier", "GR", "Alps", "T2", 1896, 2150, 46.4333, 9.9333, 6.0),
    ("Roseg Valley", "GR", "Alps", "T2", 1850, 2155, 46.4500, 9.8833, 8.0),
    ("Lej da Staz", "GR", "Pre-Alps", "T1", 1800, 1810, 46.4900, 9.8500, 4.5),
    ("Lej Marsch", "GR", "Pre-Alps", "T1", 1768, 1820, 46.4833, 9.8500, 3.0),
    ("Maloja — Plaun da Lej", "GR", "Alps", "T2", 1815, 1850, 46.3833, 9.6833, 7.0),
    ("Lej da Cavloc", "GR", "Alps", "T2", 1800, 1907, 46.3833, 9.6500, 4.5),
    ("Davos Parsenn — Weissfluhjoch", "GR", "Alps", "T2", 1840, 2693, 46.8333, 9.7833, 7.0),
    ("Davos Schatzalp — Strela", "GR", "Alps", "T2", 1800, 2350, 46.8000, 9.8167, 5.5),
    ("Jakobshorn", "GR", "Alps", "T3", 1530, 2590, 46.7833, 9.8500, 6.0),
    ("Arosa — Weisshorn", "GR", "Alps", "T3", 1800, 2653, 46.7833, 9.6833, 6.5),
    ("Lenzerheide — Rothorn", "GR", "Alps", "T3", 1500, 2865, 46.7333, 9.5833, 7.5),
    ("Stätzerhorn", "GR", "Alps", "T2", 1500, 2575, 46.7500, 9.5500, 6.0),
    ("Flims — Cassons", "GR", "Alps", "T2", 1100, 2675, 46.8333, 9.2833, 8.0),
    ("Crap Sogn Gion", "GR", "Alps", "T2", 1100, 2228, 46.8333, 9.2500, 6.0),
    ("Vorab", "GR", "Alps", "T3", 2200, 3018, 46.8500, 9.1833, 7.0),
    ("Albulapass", "GR", "Alps", "T2", 2100, 2315, 46.5833, 9.8333, 5.5),
    ("Bergün — Preda", "GR", "Pre-Alps", "T1", 1370, 1789, 46.6333, 9.7500, 6.5),
    ("Lai da Tuma", "GR", "Alps", "T3", 2030, 2345, 46.6333, 8.7167, 7.0),
    ("Disentis — Caischavedra", "GR", "Alps", "T2", 1130, 1900, 46.7000, 8.8500, 5.5),
    ("Greina Plateau (GR)", "GR", "Alps", "T3", 1850, 2360, 46.5833, 8.9167, 9.0),
    ("Vrin — Diesrut", "GR", "Alps", "T3", 1450, 2428, 46.6500, 9.1167, 7.5),
    ("Lukmanier — Pian Segno", "GR", "Alps", "T2", 1900, 1980, 46.5500, 8.8000, 5.0),
    ("Macun Lakes", "GR", "Alps", "T3", 1900, 2616, 46.7833, 10.1500, 8.5),
    ("S-charl — Pass da Costainas", "GR", "Alps", "T3", 1810, 2251, 46.7000, 10.3667, 7.0),
    ("Munt la Schera", "GR", "Alps", "T3", 1850, 2587, 46.6500, 10.2333, 6.0),
    ("Promontogno — Soglio", "GR", "Pre-Alps", "T2", 700, 1090, 46.3333, 9.5667, 5.5),
    ("Bregaglia — Maloja Pass", "GR", "Alps", "T2", 1815, 1900, 46.4000, 9.7000, 6.0),

    # ---------- Bern (BE) ----------
    ("First — Bachalpsee", "BE", "Alps", "T1", 2168, 2265, 46.6638, 8.1225, 6.0),
    ("Faulhorn — First", "BE", "Alps", "T2", 2167, 2681, 46.6638, 8.1225, 8.0),
    ("Schynige Platte — Faulhorn", "BE", "Alps", "T3", 1967, 2681, 46.6500, 7.9000, 15.5),
    ("Männlichen — Kleine Scheidegg", "BE", "Alps", "T1", 2061, 2230, 46.6167, 7.9333, 4.5),
    ("Eiger Trail", "BE", "Alps", "T2", 1850, 2320, 46.5833, 7.9667, 6.5),
    ("Oeschinensee Rundweg", "BE", "Alps", "T2", 1578, 1900, 46.4972, 7.7303, 6.0),
    ("Schilthorn — Birg", "BE", "Alps", "T3", 2677, 2970, 46.5583, 7.8350, 4.7),
    ("Stockhorn (BE)", "BE", "Pre-Alps", "T2", 1100, 2190, 46.6833, 7.5167, 6.5),
    ("Niesen Treppenweg", "BE", "Pre-Alps", "T3", 690, 2362, 46.6500, 7.6500, 8.0),
    ("Niederhorn — Burgfeldstand", "BE", "Pre-Alps", "T2", 1950, 2063, 46.7242, 7.7583, 5.6),
    ("Augstmatthorn", "BE", "Pre-Alps", "T3", 1900, 2137, 46.7500, 7.9167, 6.0),
    ("Brienzer Rothorn", "BE", "Alps", "T3", 1100, 2350, 46.7833, 8.0500, 8.5),
    ("Hardergrat", "BE", "Alps", "T5", 1300, 2206, 46.7000, 7.9000, 22.0),
    ("Schreckhorn approach", "BE", "Alps", "T4", 1600, 2680, 46.5833, 8.1833, 9.0),
    ("Sigriswiler Rothorn", "BE", "Pre-Alps", "T3", 800, 2050, 46.7333, 7.7000, 7.0),
    ("Beatenberg — Niederhorn", "BE", "Pre-Alps", "T1", 1100, 1950, 46.7167, 7.7833, 5.5),
    ("Engstligenalp Rundweg", "BE", "Alps", "T2", 1950, 2000, 46.4833, 7.5833, 4.5),
    ("Hahnenmoospass", "BE", "Alps", "T2", 1950, 1957, 46.4833, 7.4833, 5.0),
    ("Rinderberg", "BE", "Alps", "T2", 1300, 2079, 46.4333, 7.4833, 6.0),
    ("Doldenhorn approach", "BE", "Alps", "T4", 1670, 2700, 46.4667, 7.7333, 8.5),
    ("Gemmi Pass", "BE", "Alps", "T2", 1411, 2350, 46.4083, 7.6167, 7.0),
    ("Wispile Sanetsch", "BE", "Alps", "T2", 1300, 1907, 46.4500, 7.2333, 5.5),
    ("Lauenensee Rundweg", "BE", "Alps", "T1", 1380, 1450, 46.4000, 7.3333, 5.0),
    ("Hohgant Loop", "BE", "Pre-Alps", "T3", 1500, 2197, 46.7833, 7.8000, 7.5),
    ("Brienzergrat", "BE", "Alps", "T4", 1900, 2350, 46.7833, 8.1000, 12.0),
    ("Gurten — Rundweg", "BE", "Mittelland", "T1", 600, 858, 46.9333, 7.4500, 4.0),

    # ---------- Ticino (TI) ----------
    ("Verzasca — Lavertezzo", "TI", "Pre-Alps", "T1", 540, 700, 46.2667, 8.8333, 6.0),
    ("Sonogno — Cabbiolo", "TI", "Alps", "T2", 920, 1050, 46.3500, 8.7833, 7.5),
    ("Robiei — Bavona", "TI", "Alps", "T3", 950, 1893, 46.4500, 8.5500, 8.0),
    ("Bosco Gurin Loop", "TI", "Alps", "T2", 1500, 1700, 46.3167, 8.4833, 6.5),
    ("Pizzo Pesciora approach", "TI", "Alps", "T4", 1750, 3122, 46.5000, 8.4500, 9.0),
    ("Monte Generoso", "TI", "Pre-Alps", "T2", 1605, 1701, 45.9272, 9.0167, 5.8),
    ("Monte San Salvatore", "TI", "Pre-Alps", "T1", 280, 912, 45.9833, 8.9500, 3.5),
    ("Monte Bre", "TI", "Pre-Alps", "T1", 280, 925, 46.0167, 8.9833, 4.0),
    ("Camoghé", "TI", "Pre-Alps", "T3", 1500, 2228, 46.1333, 8.9667, 7.0),
    ("San Lucio", "TI", "Pre-Alps", "T2", 1500, 1612, 46.0500, 9.0000, 5.0),
    ("Pizzo Leone", "TI", "Pre-Alps", "T3", 800, 1659, 46.1500, 8.7333, 6.5),
    ("Greina Plateau (TI)", "TI", "Alps", "T3", 2000, 2360, 46.5667, 8.9000, 9.5),
    ("Cima dell'Uomo", "TI", "Alps", "T3", 1300, 2390, 46.2833, 9.0667, 7.0),
    ("Pizzo di Vogorno", "TI", "Alps", "T4", 540, 2442, 46.2167, 8.8500, 11.0),
    ("Cardada — Cimetta", "TI", "Pre-Alps", "T1", 1340, 1671, 46.1833, 8.7833, 4.0),

    # ---------- Uri (UR) ----------
    ("Surenenpass", "UR", "Alps", "T2", 1850, 2291, 46.8167, 8.4833, 11.0),
    ("Klausenpass — Urnerboden", "UR", "Alps", "T2", 1390, 1948, 46.8667, 8.8500, 8.0),
    ("Furkapass", "UR", "Alps", "T3", 2429, 2860, 46.5667, 8.4167, 6.0),
    ("Sustenpass", "UR", "Alps", "T2", 2224, 2375, 46.7333, 8.4500, 5.0),
    ("Eggberge", "UR", "Pre-Alps", "T1", 1450, 1700, 46.8833, 8.6500, 4.5),
    ("Schächental Loop", "UR", "Pre-Alps", "T2", 800, 1500, 46.8333, 8.7000, 7.5),
    ("Maderanertal — Etzlital", "UR", "Alps", "T3", 1400, 2400, 46.7500, 8.7833, 9.0),
    ("Krönten approach", "UR", "Alps", "T4", 1450, 3108, 46.7667, 8.6500, 8.5),
    ("Andermatt — Nätschen", "UR", "Alps", "T1", 1444, 1840, 46.6500, 8.5833, 4.5),
    ("Gemsstock", "UR", "Alps", "T3", 1444, 2961, 46.6167, 8.6000, 5.5),

    # ---------- Schwyz (SZ) ----------
    ("Grosser Mythen", "SZ", "Pre-Alps", "T3", 1400, 1898, 47.0167, 8.7833, 4.0),
    ("Kleiner Mythen", "SZ", "Pre-Alps", "T4", 1400, 1811, 47.0167, 8.7667, 3.5),
    ("Hoch-Ybrig — Druesberg", "SZ", "Pre-Alps", "T3", 1500, 2282, 47.0167, 8.8833, 7.0),
    ("Stoos — Fronalpstock", "SZ", "Pre-Alps", "T2", 1300, 1922, 46.9833, 8.6500, 5.0),
    ("Rotenflue", "SZ", "Pre-Alps", "T2", 1100, 1571, 47.0000, 8.7833, 4.5),
    ("Wägitalersee Loop", "SZ", "Pre-Alps", "T1", 900, 950, 47.1000, 8.8833, 12.0),
    ("Höch Hand", "SZ", "Pre-Alps", "T3", 1100, 2080, 47.0833, 8.9333, 7.5),
    ("Ibergeregg — Roggenstock", "SZ", "Pre-Alps", "T2", 1400, 1778, 47.0500, 8.7833, 5.0),
    ("Sihlsee Rundweg", "SZ", "Mittelland", "T1", 880, 890, 47.1167, 8.7833, 18.0),
    ("Rigi Kulm via Känzeli", "SZ", "Pre-Alps", "T1", 1432, 1798, 47.0573, 8.4855, 4.0),

    # ---------- Lucerne (LU) ----------
    ("Pilatus — Tomlishorn", "LU", "Pre-Alps", "T2", 2073, 2128, 46.9789, 8.2531, 3.2),
    ("Pilatus — Klimsenkapelle", "LU", "Pre-Alps", "T3", 1450, 2128, 46.9789, 8.2531, 6.0),
    ("Sörenberg — Brienzer Rothorn", "LU", "Pre-Alps", "T2", 1170, 2350, 46.8333, 8.0667, 7.0),
    ("Schratteflue", "LU", "Pre-Alps", "T3", 1300, 2092, 46.8167, 8.0500, 6.5),
    ("Eigenthal — Mittaggüpfi", "LU", "Pre-Alps", "T2", 850, 1917, 46.9833, 8.2333, 6.0),
    ("Hilferenpass", "LU", "Pre-Alps", "T2", 1300, 1700, 46.7833, 8.0833, 5.5),
    ("Stanserhorn from Emmetten", "LU", "Pre-Alps", "T2", 760, 1898, 46.9667, 8.3667, 8.0),
    ("Napf", "LU", "Pre-Alps", "T2", 800, 1408, 47.0167, 7.9500, 6.5),

    # ---------- Obwalden (OW) ----------
    ("Titlis — Trübsee", "OW", "Alps", "T3", 1800, 3020, 46.7708, 8.4372, 7.9),
    ("Engelberg — Trübsee", "OW", "Pre-Alps", "T1", 1000, 1800, 46.8167, 8.4000, 5.0),
    ("Jochpass — Engstlensee", "OW", "Alps", "T2", 1820, 2207, 46.7667, 8.3833, 6.0),
    ("Hahnen", "OW", "Alps", "T4", 1800, 2606, 46.7833, 8.3667, 6.0),
    ("Klein Titlis", "OW", "Alps", "T3", 1800, 2900, 46.7708, 8.4400, 7.5),
    ("Brünig — Kaiserstuhl", "OW", "Pre-Alps", "T1", 1000, 1411, 46.7500, 8.1500, 4.5),
    ("Melchsee-Frutt — Tannensee", "OW", "Alps", "T2", 1900, 2100, 46.7833, 8.2833, 5.5),

    # ---------- Nidwalden (NW) ----------
    ("Stanserhorn — Wiesenberg", "NW", "Pre-Alps", "T2", 450, 1898, 46.9667, 8.3667, 8.0),
    ("Klewenalp — Stockhütte", "NW", "Pre-Alps", "T2", 1600, 1900, 46.9667, 8.4333, 5.0),
    ("Niederbauen Chulm", "NW", "Pre-Alps", "T3", 1600, 1923, 46.9333, 8.5500, 4.5),
    ("Buochserhorn", "NW", "Pre-Alps", "T3", 800, 1807, 46.9667, 8.4500, 6.5),
    ("Bürgenstock — Hammetschwand", "NW", "Pre-Alps", "T1", 880, 1132, 46.9833, 8.4000, 5.0),

    # ---------- Glarus (GL) ----------
    ("Klausenpass (GL side)", "GL", "Alps", "T2", 1948, 2052, 46.8667, 8.8500, 6.5),
    ("Kärpf", "GL", "Alps", "T3", 1500, 2794, 46.9667, 9.1000, 8.0),
    ("Mürtschenstock", "GL", "Alps", "T4", 1300, 2441, 47.0500, 9.1333, 7.5),
    ("Vorder Glärnisch", "GL", "Pre-Alps", "T4", 850, 2327, 47.0333, 8.9833, 8.0),
    ("Bischofalp", "GL", "Pre-Alps", "T2", 1100, 1900, 46.9333, 9.0833, 5.5),
    ("Klöntalersee Rundweg", "GL", "Pre-Alps", "T1", 850, 870, 47.0167, 9.0167, 14.0),
    ("Richisau — Pragelpass", "GL", "Pre-Alps", "T2", 1100, 1554, 47.0333, 8.9333, 6.0),
    ("Braunwald — Eggstock", "GL", "Alps", "T3", 1300, 2449, 46.9333, 8.9833, 7.0),

    # ---------- St. Gallen (SG) ----------
    ("Speer", "SG", "Pre-Alps", "T3", 800, 1950, 47.1833, 9.0167, 7.0),
    ("Mattstock", "SG", "Pre-Alps", "T3", 800, 1936, 47.1833, 9.1000, 6.5),
    ("Federispitz", "SG", "Pre-Alps", "T3", 600, 1865, 47.1833, 9.0167, 7.0),
    ("Chäserrugg — Churfirsten", "SG", "Alps", "T3", 1340, 2262, 47.1583, 9.3153, 9.2),
    ("Wildhaus — Säntis", "SG", "Alps", "T3", 1100, 2502, 47.2000, 9.3333, 9.5),
    ("Toggenburg — Schwägalp", "SG", "Pre-Alps", "T2", 1352, 1502, 47.2667, 9.3333, 5.5),
    ("Alvier", "SG", "Alps", "T3", 800, 2343, 47.1167, 9.4833, 8.5),
    ("Gauschla", "SG", "Alps", "T3", 1500, 2310, 47.1000, 9.4500, 6.0),
    ("Pizol — 5-Seen", "SG", "Alps", "T3", 2227, 2780, 46.9667, 9.4000, 11.0),
    ("Sargans Schloss Loop", "SG", "Mittelland", "T1", 480, 700, 47.0500, 9.4500, 4.5),

    # ---------- Appenzell (AI / AR) ----------
    ("Säntis via Schwägalp", "AR/AI", "Alps", "T3", 1352, 2502, 47.2493, 9.3432, 7.8),
    ("Hoher Kasten — Bollenwees", "AI", "Pre-Alps", "T2", 1480, 1795, 47.3028, 9.4253, 6.5),
    ("Schäfler Ridge", "AI", "Alps", "T4", 1644, 2049, 47.2700, 9.3750, 4.1),
    ("Ebenalp — Seealpsee", "AI", "Pre-Alps", "T2", 1120, 1644, 47.2822, 9.3967, 5.3),
    ("Meglisalp Loop", "AI", "Alps", "T3", 1520, 2153, 47.2567, 9.3833, 6.4),
    ("Bollenwees — Sämtisersee", "AI", "Pre-Alps", "T2", 1480, 1500, 47.2833, 9.4167, 5.0),
    ("Kronberg — Jakobsbad", "AI", "Pre-Alps", "T2", 872, 1663, 47.2917, 9.3333, 7.2),
    ("Hundwiler Höhi", "AR", "Pre-Alps", "T1", 800, 1306, 47.3500, 9.3500, 5.0),
    ("Stoss — Gais", "AR", "Mittelland", "T1", 800, 950, 47.3833, 9.4500, 4.0),
    ("Klimsenhorn — Schäfler", "AI", "Alps", "T4", 1500, 2049, 47.2667, 9.3833, 5.0),

    # ---------- Vaud (VD) ----------
    ("Diablerets — Glacier 3000", "VD", "Alps", "T3", 1900, 2971, 46.3833, 7.2333, 6.5),
    ("Quille du Diable", "VD", "Alps", "T3", 1900, 2456, 46.3667, 7.2167, 5.5),
    ("Mont Tendre", "VD", "Jura", "T2", 1080, 1679, 46.6000, 6.3333, 7.0),
    ("La Dôle", "VD", "Jura", "T2", 1100, 1677, 46.4167, 6.1000, 6.0),
    ("Chasseron", "VD", "Jura", "T2", 1300, 1607, 46.8500, 6.5333, 5.0),
    ("Rochers de Naye", "VD", "Pre-Alps", "T2", 950, 2042, 46.4333, 6.9833, 7.5),
    ("Tour d'Aï", "VD", "Pre-Alps", "T3", 1500, 2331, 46.3667, 6.9667, 6.0),
    ("Tour de Mayen", "VD", "Pre-Alps", "T3", 1500, 2326, 46.3667, 6.9833, 5.5),
    ("Cape au Moine (VD)", "VD", "Pre-Alps", "T3", 1500, 1941, 46.4167, 7.0500, 5.0),
    ("Pierre du Moëllé", "VD", "Pre-Alps", "T2", 1500, 1660, 46.4333, 7.1167, 4.5),
    ("Grammont", "VD", "Pre-Alps", "T3", 900, 2172, 46.3500, 6.8000, 8.0),
    ("Lac de Bret Loop", "VD", "Mittelland", "T1", 670, 680, 46.5500, 6.8167, 5.5),

    # ---------- Fribourg (FR) ----------
    ("Moléson", "FR", "Pre-Alps", "T2", 1100, 2002, 46.5500, 7.0167, 6.0),
    ("Vanil Noir", "FR", "Pre-Alps", "T4", 1300, 2389, 46.5333, 7.1167, 8.0),
    ("Le Folliéran", "FR", "Pre-Alps", "T3", 1300, 2340, 46.5667, 7.1333, 6.5),
    ("La Berra", "FR", "Pre-Alps", "T2", 1100, 1719, 46.6333, 7.1500, 5.5),
    ("Schwarzsee — Riggisalp", "FR", "Pre-Alps", "T2", 1050, 1495, 46.6667, 7.2833, 4.5),
    ("Kaiseregg", "FR", "Pre-Alps", "T3", 1050, 2185, 46.6500, 7.3000, 7.5),
    ("Schopfenspitz", "FR", "Pre-Alps", "T3", 1100, 2102, 46.6167, 7.2000, 6.5),
    ("Cape au Moine (FR)", "FR", "Pre-Alps", "T3", 1500, 1941, 46.5500, 7.1500, 5.0),
    ("Gibloux", "FR", "Mittelland", "T1", 700, 1206, 46.7000, 7.0667, 4.5),
    ("Vudalla", "FR", "Pre-Alps", "T2", 900, 1670, 46.5833, 7.0500, 5.5),

    # ---------- Neuchâtel (NE) ----------
    ("Creux du Van", "NE", "Jura", "T2", 750, 1463, 46.9342, 6.7308, 10.5),
    ("Chasseral — La Neuveville", "NE", "Jura", "T2", 800, 1606, 47.1333, 7.0667, 9.0),
    ("Chaumont", "NE", "Jura", "T1", 700, 1087, 47.0167, 6.9833, 4.0),
    ("Vue des Alpes — Tête de Ran", "NE", "Jura", "T2", 1283, 1422, 47.0500, 6.8500, 5.5),
    ("Mont Racine", "NE", "Jura", "T2", 1100, 1439, 47.0167, 6.7833, 5.5),
    ("Champ-du-Moulin Gorge", "NE", "Jura", "T1", 600, 700, 46.9667, 6.7833, 6.0),

    # ---------- Jura (JU) ----------
    ("Mont Soleil — Mont Crosin", "JU", "Jura", "T1", 1100, 1300, 47.1500, 7.0500, 6.5),
    ("Le Suchet", "JU", "Jura", "T2", 1100, 1588, 46.7500, 6.4833, 5.5),
    ("Chasseral (JU)", "JU", "Jura", "T2", 1100, 1606, 47.1333, 7.0833, 7.0),
    ("Le Raimeux", "JU", "Jura", "T2", 800, 1302, 47.2667, 7.4500, 5.5),
    ("Doubs Gorges", "JU", "Jura", "T1", 500, 700, 47.2667, 6.9000, 6.5),

    # ---------- Solothurn (SO) ----------
    ("Weissenstein — Hasenmatt", "SO", "Jura", "T2", 1280, 1445, 47.2500, 7.5167, 6.5),
    ("Hasenmatt", "SO", "Jura", "T2", 800, 1445, 47.2667, 7.4667, 5.0),
    ("Wisenberg", "SO", "Jura", "T1", 600, 1003, 47.4167, 7.7500, 4.5),
    ("Stallflue", "SO", "Jura", "T2", 800, 1115, 47.3000, 7.5667, 5.0),
    ("Schauenburg — Wasserfallen", "SO", "Jura", "T1", 600, 950, 47.3833, 7.6833, 5.5),

    # ---------- Basel-Landschaft (BL) ----------
    ("Wasserfallen — Reigoldswil", "BL", "Jura", "T1", 500, 944, 47.3833, 7.6833, 4.5),
    ("Belchen", "BL", "Jura", "T2", 600, 1099, 47.3667, 7.8167, 5.0),
    ("Passwang", "BL", "Jura", "T2", 700, 1204, 47.3500, 7.6833, 6.0),
    ("Schauenburgflue", "BL", "Jura", "T1", 400, 700, 47.4833, 7.7167, 4.0),

    # ---------- Aargau (AG) ----------
    ("Lägern — Hochwacht", "AG", "Jura", "T2", 400, 859, 47.4833, 8.4000, 6.0),
    ("Wasserflue", "AG", "Jura", "T1", 400, 866, 47.4500, 8.0667, 5.5),
    ("Geissflue", "AG", "Jura", "T1", 400, 963, 47.4167, 7.9333, 5.0),
    ("Linnerlinde Loop", "AG", "Mittelland", "T1", 400, 650, 47.4500, 8.0167, 6.0),
    ("Erlinsbach — Bänkerjoch", "AG", "Jura", "T1", 450, 688, 47.4167, 8.0833, 5.0),

    # ---------- Zürich (ZH) ----------
    ("Üetliberg — Felsenegg", "ZH", "Mittelland", "T1", 470, 869, 47.3500, 8.4833, 6.0),
    ("Albis — Albishorn", "ZH", "Mittelland", "T1", 600, 909, 47.2833, 8.5333, 7.0),
    ("Pfannenstiel", "ZH", "Mittelland", "T1", 600, 853, 47.2333, 8.6500, 5.5),
    ("Bachtel", "ZH", "Pre-Alps", "T1", 700, 1115, 47.2833, 8.8500, 5.0),
    ("Hörnli (ZH)", "ZH", "Pre-Alps", "T1", 1100, 1133, 47.3333, 8.9667, 4.5),
    ("Schauenberg", "ZH", "Mittelland", "T1", 600, 893, 47.4500, 8.7333, 5.0),

    # ---------- Zug (ZG) ----------
    ("Zugerberg — Wildspitz", "ZG", "Pre-Alps", "T2", 700, 1580, 47.1833, 8.5667, 7.5),
    ("Wildspitz", "ZG", "Pre-Alps", "T2", 1000, 1580, 47.1500, 8.6500, 5.5),
    ("Rossberg — Gnipen", "ZG", "Pre-Alps", "T3", 1000, 1580, 47.0833, 8.6000, 6.0),

    # ---------- Thurgau (TG) ----------
    ("Seerücken — Salenstein", "TG", "Mittelland", "T1", 400, 660, 47.6333, 9.0833, 6.5),
    ("Pfynerwald", "TG", "Mittelland", "T1", 400, 500, 47.5500, 9.1000, 5.5),
    ("Hohenrain Loop", "TG", "Mittelland", "T1", 600, 700, 47.4500, 9.0500, 5.0),

    # ---------- Schaffhausen (SH) ----------
    ("Randen — Hagenturm", "SH", "Mittelland", "T1", 500, 912, 47.7833, 8.5667, 6.0),
    ("Reiat-Höhe", "SH", "Mittelland", "T1", 500, 700, 47.7500, 8.7167, 5.5),
    ("Munot — Rhine Loop", "SH", "Mittelland", "T1", 400, 450, 47.7000, 8.6333, 4.5),

    # ---------- Geneva (GE) ----------
    ("Salève foothills", "GE", "Pre-Alps", "T1", 400, 700, 46.1833, 6.1833, 5.0),
    ("Vessy — Carouge", "GE", "Mittelland", "T1", 380, 450, 46.1667, 6.1500, 4.5),

    # ---------- Basel-Stadt (BS) ----------
    ("Lange Erlen Park Loop", "BS", "Mittelland", "T1", 250, 270, 47.5833, 7.6167, 4.0),
]


VALID_DIFFICULTIES = {"T1", "T2", "T3", "T4", "T5", "T6"}
VALID_REGIONS = {"Alps", "Pre-Alps", "Jura", "Mittelland"}
CH_BBOX = (45.7, 47.9, 5.8, 10.6)  # (lat_min, lat_max, lon_min, lon_max)


def _validate(rows: list[dict]) -> None:
    seen_names: set[str] = set()
    for r in rows:
        if r["name"] in seen_names:
            raise ValueError(f"Duplicate trail name: {r['name']!r}")
        seen_names.add(r["name"])
        if r["difficulty"] not in VALID_DIFFICULTIES:
            raise ValueError(f"{r['name']}: invalid difficulty {r['difficulty']!r}")
        if r["region"] not in VALID_REGIONS:
            raise ValueError(f"{r['name']}: invalid region {r['region']!r}")
        if r["min_alt_m"] > r["max_alt_m"]:
            raise ValueError(f"{r['name']}: min_alt > max_alt")
        if not (CH_BBOX[0] <= r["lat"] <= CH_BBOX[1]
                and CH_BBOX[2] <= r["lon"] <= CH_BBOX[3]):
            raise ValueError(f"{r['name']}: coordinates outside Switzerland bbox")
        if r["length_km"] <= 0:
            raise ValueError(f"{r['name']}: non-positive length")


def to_dicts() -> list[dict]:
    rows = [
        {
            "name": name,
            "canton": canton,
            "region": region,
            "difficulty": difficulty,
            "min_alt_m": min_alt,
            "max_alt_m": max_alt,
            "lat": lat,
            "lon": lon,
            "length_km": length,
        }
        for (name, canton, region, difficulty, min_alt, max_alt, lat, lon, length)
        in TRAILS
    ]
    _validate(rows)
    return rows


def main() -> None:
    rows = to_dicts()
    OUT_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    cantons = sorted({r["canton"] for r in rows})
    regions = sorted({r["region"] for r in rows})
    diffs = sorted({r["difficulty"] for r in rows})
    print(f"✓ Wrote {len(rows)} trails to {OUT_PATH.relative_to(OUT_PATH.parent.parent)}")
    print(f"  Cantons     ({len(cantons):2d}): {' '.join(cantons)}")
    print(f"  Regions     ({len(regions):2d}): {' '.join(regions)}")
    print(f"  Difficulties({len(diffs):2d}): {' '.join(diffs)}")


if __name__ == "__main__":
    main()
