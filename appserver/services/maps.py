"""
    Maps for the progress tracker
"""

# Step map with label and weight
STEP_MAP= {
    "init": {"label": "Initializing agent", "weight": 5},
    "building_logic_map": {"label": "Building OPL logic map", "weight": 20},
    "generating": {"label": "Generating frontend and backend", "weight": 35},
    "evaluating": {"label": "Running evaluation", "weight": 25},
    "resolving_problem": {"label": "Found issue, trying to resolve", "weight": 0},
    "finishing": {"label": "Agent finished, returning to user", "weight": 10},
    "packaging": {"label": "Packaging project", "weight": 30},
    "retry": {"label": "Generated failed, retrying", "weight": 0},
}

# Tool map
TOOL_MAP = {
    "generate_opl_logic_map": "building_logic_map",
    "generate_problem": "resolving_problem",
    "finish_and_return_user": "finishing",
    "generate_code": "generating",
    "generate_code_evaluation": "evaluating",
}

# Critical session states
CRITICAL_SESSION_STATES = {
    "opl_logic_map": "building_logic_map",
    "generated_code_zip": "generating",
    "code_evaluation": "evaluating",
    "workflow_problem": "resolving_problem",
    "finish_code_zip_base64": "finishing",
}