# ============================================
# CHAMP V3 -- Goal Card Templates
# Brick 8: Pre-built Goal Card templates for
# common task types. Fill in the blanks.
# ============================================

TEMPLATE_SCRIPT = """\
GOAL CARD v1.0
(goal_id: {goal_id} | project_id: {project_id} | priority: {priority} | risk_level: {risk_level})

1) OBJECTIVE
- {objective}

2) PROBLEM
- {problem}

3) SOLUTION
- {solution}

4) STACK
- {stack}

5) CONSTRAINTS
- {constraints}

6) APPROVAL
- {approval}

7) DELIVERABLES
- {deliverables}

8) CONTEXT / ASSETS
- {context_assets}

9) SUCCESS CHECKS
- {success_checks}
"""

# ---- Ready-to-use templates ----

PYTHON_SCRIPT_TEMPLATE = TEMPLATE_SCRIPT.format(
    goal_id="GC-SCRIPT-001",
    project_id="champ_v3",
    priority="P1",
    risk_level="low",
    objective="Create a Python script that [DESCRIBE WHAT IT DOES].",
    problem="[WHO needs this and WHY].",
    solution="Python script that [HOW it solves the problem].",
    stack="Python 3, [LIBRARIES]",
    constraints="Must run locally. No paid APIs. Under 30 minutes.",
    approval="None. Auto-execute.",
    deliverables="[script_name].py, [output_file]",
    context_assets="[Any inputs, data files, API endpoints, examples]",
    success_checks="Script runs without errors\n- Output file exists\n- [SPECIFIC CHECKS]",
)

WEB_SCRAPER_TEMPLATE = TEMPLATE_SCRIPT.format(
    goal_id="GC-SCRAPE-001",
    project_id="champ_v3",
    priority="P1",
    risk_level="low",
    objective="Scrape [TARGET DATA] from [WEBSITE] and save to [FORMAT].",
    problem="[WHO] needs [WHAT DATA] but collecting it manually is slow.",
    solution="Python script using requests/BeautifulSoup to extract data and save to CSV/JSON.",
    stack="Python 3, requests, beautifulsoup4, csv",
    constraints="Respect robots.txt. No login required. Rate limit requests. Under 30 minutes.",
    approval="None. Auto-execute. No external writes beyond local files.",
    deliverables="scraper.py, output.[csv|json]",
    context_assets="Target URL: [URL]\nData fields: [FIELD1, FIELD2, ...]\nExpected rows: [N]",
    success_checks="Script runs without errors\n- Output file has [N]+ rows\n- All fields present\n- Data is valid (no nulls in required fields)",
)

API_INTEGRATION_TEMPLATE = TEMPLATE_SCRIPT.format(
    goal_id="GC-API-001",
    project_id="champ_v3",
    priority="P1",
    risk_level="low",
    objective="Build a [LANGUAGE] module that integrates with [API NAME].",
    problem="[WHO] needs to [ACTION] via [API] programmatically.",
    solution="Wrapper module with functions for [ENDPOINTS]. Error handling + retry logic.",
    stack="Python 3, requests, [API SDK if any]",
    constraints="Use free tier only. Handle rate limits. Timeout after 30s per call.",
    approval="None. Auto-execute.",
    deliverables="[module_name].py, test_[module_name].py, example usage in README",
    context_assets="API docs: [URL]\nAuth: [method] (key in env var [VAR_NAME])\nEndpoints: [LIST]",
    success_checks="Module imports without errors\n- Tests pass\n- [N] API endpoints covered\n- Error handling works for 4xx/5xx",
)

DATA_PIPELINE_TEMPLATE = TEMPLATE_SCRIPT.format(
    goal_id="GC-DATA-001",
    project_id="champ_v3",
    priority="P1",
    risk_level="low",
    objective="Build a data pipeline that [READS FROM] -> [TRANSFORMS] -> [WRITES TO].",
    problem="[WHO] needs [DATA] transformed from [FORMAT A] to [FORMAT B].",
    solution="Python ETL script: extract from [SOURCE], transform [HOW], load to [DEST].",
    stack="Python 3, pandas, [connectors]",
    constraints="Must handle [N] rows. Memory efficient. Idempotent (safe to re-run).",
    approval="None. Auto-execute.",
    deliverables="pipeline.py, sample_output.[format], run log",
    context_assets="Input: [PATH/URL]\nSchema: [FIELDS]\nTransform rules: [RULES]",
    success_checks="Pipeline runs end-to-end without errors\n- Output has expected schema\n- Row count matches input\n- No data loss",
)

FILE_ORGANIZER_TEMPLATE = TEMPLATE_SCRIPT.format(
    goal_id="GC-ORGANIZE-001",
    project_id="champ_v3",
    priority="P2",
    risk_level="low",
    objective="Organize files in [DIRECTORY] by [CRITERIA] into [STRUCTURE].",
    problem="[DIRECTORY] has [N] unorganized files making it hard to find things.",
    solution="Python script that scans, categorizes, and moves/copies files into organized folders.",
    stack="Python 3, pathlib, shutil",
    constraints="Never delete originals. Create copies or moves with undo log. Under 10 minutes.",
    approval="None. Auto-execute. No external writes beyond target directory.",
    deliverables="organizer.py, undo_log.json, summary report",
    context_assets="Target directory: [PATH]\nOrganize by: [date/type/name/size]\nOutput structure: [DESCRIPTION]",
    success_checks="Script runs without errors\n- All files accounted for (none lost)\n- Undo log contains every move\n- Folder structure matches spec",
)


def list_templates() -> dict[str, str]:
    """Return all available templates by name."""
    return {
        "python_script": PYTHON_SCRIPT_TEMPLATE,
        "web_scraper": WEB_SCRAPER_TEMPLATE,
        "api_integration": API_INTEGRATION_TEMPLATE,
        "data_pipeline": DATA_PIPELINE_TEMPLATE,
        "file_organizer": FILE_ORGANIZER_TEMPLATE,
    }


def get_template(name: str) -> str:
    """Get a template by name. Raises KeyError if not found."""
    templates = list_templates()
    if name not in templates:
        available = ", ".join(templates.keys())
        raise KeyError(f"Unknown template '{name}'. Available: {available}")
    return templates[name]
