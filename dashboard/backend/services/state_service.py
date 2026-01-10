import json
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema
from jsonschema import validate

# Define paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / ".kiro" / "specs" / "AGENT_STATE.json"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "codeagent-wrapper" / "agent-state-schema.json"

class StateValidationError(Exception):
    """Raised when the state file fails schema validation."""
    pass

class StateNotFoundError(Exception):
    """Raised when the state file cannot be found."""
    pass

class StateReadError(Exception):
    """Raised when the state file cannot be read or parsed."""
    pass

_cached_schema: Optional[Dict[str, Any]] = None

def _load_schema(schema_path: Path) -> Dict[str, Any]:
    global _cached_schema
    if _cached_schema:
        return _cached_schema
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
        
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            _cached_schema = json.load(f)
        return _cached_schema
    except Exception as e:
        raise StateReadError(f"Failed to load schema from {schema_path}: {e}")

def load_state(state_path: Optional[Path] = None, schema_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Reads and validates the AGENT_STATE.json file.
    
    Args:
        state_path: Path to AGENT_STATE.json. Defaults to .kiro/specs/AGENT_STATE.json relative to project root.
        schema_path: Path to agent-state-schema.json. Defaults to codeagent-wrapper/agent-state-schema.json relative to project root.
        
    Returns:
        Dict containing the parsed state.
        
    Raises:
        StateNotFoundError: If the state file doesn't exist.
        StateReadError: If the file isn't valid JSON.
        StateValidationError: If the JSON doesn't match the schema.
    """
    if state_path is None:
        state_path = DEFAULT_STATE_PATH
    if schema_path is None:
        schema_path = DEFAULT_SCHEMA_PATH
        
    if not state_path.exists():
        raise StateNotFoundError(f"State file not found at {state_path}")
        
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateReadError(f"Invalid JSON in state file: {e}")
    except Exception as e:
        raise StateReadError(f"Error reading state file: {e}")
        
    try:
        schema = _load_schema(schema_path)
        validate(instance=state_data, schema=schema)
    except jsonschema.ValidationError as e:
        raise StateValidationError(f"State validation failed: {e.message}")
    except FileNotFoundError as e:
         raise StateReadError(f"Schema definition missing: {e}")

    return state_data
