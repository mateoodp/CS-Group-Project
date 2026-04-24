# Swiss Alpine Hiking Condition Forecaster

A Streamlit web application that turns raw weather data into actionable,
machine-learning-driven trail safety recommendations for Swiss alpine routes.
Instead of passively showing temperature and wind speed, the app delivers a
concrete **GO / BORDERLINE / AVOID** verdict for any trail on any date — updated
daily and personalised to each user's risk tolerance.

> University of St.Gallen (HSG) · Grundlagen und Methoden der Informatik
> (FCS/BWL) · Group Project · Deadline **14.05.2026**

---

## 1. Quick start

```bash
# 1. Clone
git clone https://github.com/mateoodp/CS-Group-Project.git
cd CS-Group-Project          # or hiking-forecaster/ if that's your folder name

# 2. Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. First-run setup — creates SQLite DB and seeds the 20 trails
python -c "from data.db_manager import setup_db; setup_db()"

# 5. Launch the Streamlit app
streamlit run app.py
```

The app opens on `http://localhost:8501`.

---

## 2. Repository layout

```
hiking-forecaster/
├── app.py                    # Streamlit entry point (navigation + session state)
├── requirements.txt          # pip dependencies
├── README.md                 # this file
├── .gitignore
├── .streamlit/
│   └── config.toml           # theme + server config
├── data/
│   ├── __init__.py
│   ├── db_manager.py         # all SQLite operations (TM2)
│   ├── weather_fetcher.py    # Open-Meteo + GeoAdmin APIs + caching (TM3)
│   ├── label_engine.py       # rule-based bootstrap labeller (TM5 / TM3)
│   └── trails_seed.json      # 20 pre-loaded Swiss trails
├── ml/
│   ├── __init__.py
│   ├── trail_classifier.py   # feature engineering + train + predict (TM4)
│   └── model.pkl             # serialised trained Random Forest (generated)
├── pages/
│   ├── 1_Dashboard.py        # Folium map + user report form (TM1 / TM5)
│   ├── 2_Forecast.py         # 7-day timeline + risk slider (TM2 / TM3)
│   ├── 3_Compare.py          # multiselect + radar chart (TM4 / TM5)
│   └── 4_About.py            # metrics + contribution matrix (TM1 / TM4)
├── utils/
│   ├── __init__.py
│   └── constants.py          # shared constants (labels, colours, thresholds)
└── tests/
    └── test_smoke.py         # minimal smoke tests
```

---

## 3. Team and ownership

| Member | Role | Primary modules |
|--------|------|-----------------|
| TM1 | Project Lead · Map/Visualisation | repo mgmt, `pages/1_Dashboard.py` (map), `pages/4_About.py` |
| TM2 | Database Lead · Testing | `data/db_manager.py`, `pages/2_Forecast.py` charts, `tests/` |
| TM3 | Data / API Lead · Video | `data/weather_fetcher.py`, demo video |
| TM4 | ML Lead · Compare tab | `ml/trail_classifier.py`, `pages/3_Compare.py` |
| TM5 | Feature Eng · User Reports | derived features, report form, Streamlit Cloud deploy |

> Everyone contributes to **code documentation** (Criterion 6) and appears in
> the **contribution matrix** (Criterion 7).

### Contribution matrix

| Task / Feature | TM1 | TM2 | TM3 | TM4 | TM5 |
|---|:-:|:-:|:-:|:-:|:-:|
| Project Management | **L** | S | — | — | — |
| Product Concept | M | M | — | — | S |
| API Integration (`weather_fetcher.py`) | — | — | **L** | — | S |
| Database Design (`db_manager.py`) | — | **L** | — | — | — |
| Bootstrap Label Engine (`label_engine.py`) | — | — | M | — | **L** |
| ML Model (`trail_classifier.py`) | — | — | — | **L** | M |
| Feature Engineering | — | — | — | M | **L** |
| Folium Map (Dashboard tab) | **L** | — | — | — | S |
| Forecast Tab (charts + slider) | S | **L** | M | — | — |
| Compare Tab (radar chart) | — | — | — | **L** | S |
| User Report Form | — | — | — | — | **L** |
| About Tab + Metrics | **L** | S | — | S | — |
| Code Documentation | M | M | M | M | M |
| Testing & Bug Fixes | — | **L** | S | S | — |
| Video Recording | — | — | **L** | — | M |
| Streamlit Cloud Deployment | — | — | — | — | **L** |

Legend: **L** = Lead · M = Major · S = Support · — = None

---

## 4. Git workflow

- `main` — always runnable, always passing. Protected. **No direct pushes.**
- `dev` — integration branch. All feature branches merge here first.
- `feature/xxx` — one per feature / person (e.g. `feature/ml-pipeline`,
  `feature/folium-map`).

Workflow: create branch → develop → push → open Pull Request → peer review →
merge to `dev` → weekly merge to `main`.

### Commit message convention

```
[type]: [short description]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
Example: `feat: add 7-day forecast chart`.

Commit often — at least once per working session per person. The GitHub commit
history is used as independent evidence for the contribution matrix.

---

## 5. Development timeline (10-day plan)

| Phase | Days | Goal | Owners |
|---|---|---|---|
| 1 — Setup | 1–2 | Working repo, seeded DB | TM1 · TM2 · TM3 |
| 2 — ML Pipeline | 3–4 | Trained model + metrics | TM4 · TM5 |
| 3 — Core UI | 5–6 | Dashboard + Forecast tabs | TM1 · TM2 · TM3 |
| 4 — Advanced | 7–8 | Compare + Reports + About | TM4 · TM5 · TM1 |
| 5 — Polish | 9 | Docstrings, tests, deploy | All (TM2 leads) |
| 6 — Video | 10 | 4-min demo, submission | TM3 · TM5 |

Minimum Viable Version (if behind schedule by Day 7): cut the Compare tab. The
remaining features (Dashboard + Forecast + User Reports + ML + About) still
address all 8 grading criteria.

---

## 6. Grading alignment (target 24/24)

| # | Criterion | Covered by |
|---|---|---|
| 1 | Problem Statement | README + About tab (Swiss alpine accident stats) |
| 2 | API + Database | `weather_fetcher.py` (3 APIs) + `db_manager.py` (4 tables) |
| 3 | Visualisation | Folium map · elevation profile · 7-day timeline · radar · confusion matrix |
| 4 | User Interaction | Trail selector · date picker · risk slider · report form · multiselect · retrain |
| 5 | Machine Learning | Random Forest · 7 engineered features · confusion matrix · SHAP-style importance · retrain button |
| 6 | Code Documentation | Google-style docstrings · type hints · this README · constants file |
| 7 | Contribution Matrix | Table above + About tab + GitHub commit history |
| 8 | Demo Video | 4-min walkthrough — problem → API → DB → viz → ML → interaction (**human voiceover, never AI**) |

---

## 7. Tech stack

- Streamlit 1.32+
- scikit-learn 1.4 · pandas · numpy
- Plotly 5.18+ · Folium · streamlit-folium
- SQLite (stdlib `sqlite3`)
- Deployment: Streamlit Community Cloud

---

## 8. Connecting the remote (one-time setup)

If this repo was scaffolded locally:

```bash
git remote add origin https://github.com/mateoodp/CS-Group-Project.git
git push -u origin main
git push -u origin dev
```

---

## 9. Data sources & attribution

- **Open-Meteo Forecast API** — `https://api.open-meteo.com/v1/forecast`
- **Open-Meteo Historical Archive** — `https://archive-api.open-meteo.com/v1/archive`
- **Swisstopo GeoAdmin** — `https://api3.geo.admin.ch`

All three are free and do not require an API key.

---

## 10. Licence

Academic coursework — not for redistribution. Weather data © respective providers.
