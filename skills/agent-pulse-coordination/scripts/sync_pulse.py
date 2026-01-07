#!/usr/bin/env python3
"""
PULSE Synchronization Script

Guardian Agent sync logic: reads pending_decisions and deferred_fixes from Agent State,
updates the Risks & Debt section of PULSE document.

Requirements: 7.5, 8.3
- 7.5: Guardian Agent SHALL surface deferred_fixes and pending_decisions prominently in Risks & Debt
- 8.3: Guardian Agent SHALL surface pending_decisions in PULSE_Document Risks & Debt section
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pulse_parser import (
    parse_pulse,
    generate_pulse,
    PulseDocument,
    RisksAndDebt,
)


@dataclass
class SyncResult:
    """Sync result"""
    success: bool
    message: str
    updated_document: Optional[PulseDocument] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def format_pending_decision(decision: Dict[str, Any]) -> str:
    """
    Format pending_decision as human-readable string
    
    Args:
        decision: PendingDecision object (dict form)
        
    Returns:
        Formatted string
    """
    decision_id = decision.get("decision_id", "unknown")
    context = decision.get("context", "No context provided")
    requesting_agent = decision.get("requesting_agent", "unknown")
    options = decision.get("options", [])
    
    # Build options summary
    if options:
        option_summaries = [opt.get("description", "")[:50] for opt in options[:3]]
        options_text = f" Options: {', '.join(option_summaries)}"
        if len(options) > 3:
            options_text += f" (+{len(options) - 3} more)"
    else:
        options_text = ""
    
    return f"[{decision_id}] {context} (from {requesting_agent}){options_text}"


def format_deferred_fix(fix: Dict[str, Any]) -> str:
    """
    Format deferred_fix as human-readable string
    
    Args:
        fix: DeferredFix object (dict form)
        
    Returns:
        Formatted string
    """
    fix_id = fix.get("fix_id", "unknown")
    description = fix.get("description", "No description")
    reason = fix.get("reason_deferred", "No reason provided")
    target_task = fix.get("target_task", "unknown")
    
    return f"[{fix_id}] {description} - Deferred: {reason} (target: {target_task})"


def extract_pending_decisions_from_agent_state(agent_state: Dict[str, Any]) -> List[str]:
    """
    Extract pending_decisions from Agent State and format as string list
    
    Args:
        agent_state: Agent State JSON data
        
    Returns:
        Formatted pending_decisions string list
    """
    pending_decisions = agent_state.get("pending_decisions", [])
    return [format_pending_decision(d) for d in pending_decisions]


def extract_deferred_fixes_from_agent_state(agent_state: Dict[str, Any]) -> List[str]:
    """
    Extract deferred_fixes from Agent State and format as string list
    
    Args:
        agent_state: Agent State JSON data
        
    Returns:
        Formatted deferred_fixes string list
    """
    deferred_fixes = agent_state.get("deferred_fixes", [])
    return [format_deferred_fix(f) for f in deferred_fixes]


def sync_risks_and_debt(
    pulse_document: PulseDocument,
    agent_state: Dict[str, Any],
    preserve_existing: bool = True
) -> PulseDocument:
    """
    Sync pending_decisions and deferred_fixes from Agent State to PULSE document's Risks & Debt section
    
    Args:
        pulse_document: Existing PULSE document
        agent_state: Agent State JSON data
        preserve_existing: Whether to preserve existing Risks & Debt content
        
    Returns:
        Updated PulseDocument
        
    Requirements: 7.5, 8.3
    """
    # Extract pending_decisions
    new_pending_decisions = extract_pending_decisions_from_agent_state(agent_state)
    
    # Extract deferred_fixes as technical debt
    new_deferred_fixes = extract_deferred_fixes_from_agent_state(agent_state)
    
    # Build new RisksAndDebt
    if preserve_existing:
        # Preserve existing content, add new content (deduplicated)
        existing_pending = set(pulse_document.risks_and_debt.pending_decisions)
        existing_debt = set(pulse_document.risks_and_debt.technical_debt)
        
        # Merge pending_decisions
        merged_pending = list(pulse_document.risks_and_debt.pending_decisions)
        for decision in new_pending_decisions:
            if decision not in existing_pending:
                merged_pending.append(decision)
        
        # Merge deferred_fixes into technical_debt
        merged_debt = list(pulse_document.risks_and_debt.technical_debt)
        for fix in new_deferred_fixes:
            if fix not in existing_debt:
                merged_debt.append(fix)
        
        new_risks_and_debt = RisksAndDebt(
            cognitive_warnings=pulse_document.risks_and_debt.cognitive_warnings,
            technical_debt=merged_debt,
            pending_decisions=merged_pending
        )
    else:
        # Complete replacement
        new_risks_and_debt = RisksAndDebt(
            cognitive_warnings=pulse_document.risks_and_debt.cognitive_warnings,
            technical_debt=new_deferred_fixes,
            pending_decisions=new_pending_decisions
        )
    
    # Create updated document
    return PulseDocument(
        mental_model=pulse_document.mental_model,
        narrative_delta=pulse_document.narrative_delta,
        risks_and_debt=new_risks_and_debt,
        semantic_anchors=pulse_document.semantic_anchors
    )


def sync_pulse_from_agent_state(
    pulse_content: str,
    agent_state: Dict[str, Any],
    preserve_existing: bool = True
) -> SyncResult:
    """
    Sync and update PULSE document from Agent State
    
    Args:
        pulse_content: Markdown content of PULSE document
        agent_state: Agent State JSON data
        preserve_existing: Whether to preserve existing Risks & Debt content
        
    Returns:
        SyncResult: Sync result
        
    Requirements: 7.5, 8.3
    """
    # Parse PULSE document
    parse_result = parse_pulse(pulse_content)
    if not parse_result.valid:
        return SyncResult(
            success=False,
            message="Failed to parse PULSE document",
            errors=[f"[{e.section}] {e.message}" for e in parse_result.errors]
        )
    
    # Sync Risks & Debt
    updated_document = sync_risks_and_debt(
        parse_result.document,
        agent_state,
        preserve_existing
    )
    
    return SyncResult(
        success=True,
        message="Successfully synchronized PULSE document",
        updated_document=updated_document
    )


def sync_pulse_files(
    pulse_file_path: str,
    agent_state_file_path: str,
    output_path: Optional[str] = None,
    preserve_existing: bool = True
) -> SyncResult:
    """
    Sync PULSE document from files
    
    Args:
        pulse_file_path: PULSE document file path
        agent_state_file_path: Agent State JSON file path
        output_path: Output file path (if None, overwrite original file)
        preserve_existing: Whether to preserve existing Risks & Debt content
        
    Returns:
        SyncResult: Sync result
    """
    # Read PULSE document
    try:
        with open(pulse_file_path, "r", encoding="utf-8") as f:
            pulse_content = f.read()
    except FileNotFoundError:
        return SyncResult(
            success=False,
            message=f"PULSE file not found: {pulse_file_path}",
            errors=[f"File not found: {pulse_file_path}"]
        )
    except Exception as e:
        return SyncResult(
            success=False,
            message=f"Failed to read PULSE file: {e}",
            errors=[str(e)]
        )
    
    # Read Agent State
    try:
        with open(agent_state_file_path, "r", encoding="utf-8") as f:
            agent_state = json.load(f)
    except FileNotFoundError:
        return SyncResult(
            success=False,
            message=f"Agent State file not found: {agent_state_file_path}",
            errors=[f"File not found: {agent_state_file_path}"]
        )
    except json.JSONDecodeError as e:
        return SyncResult(
            success=False,
            message=f"Invalid JSON in Agent State file: {e}",
            errors=[str(e)]
        )
    except Exception as e:
        return SyncResult(
            success=False,
            message=f"Failed to read Agent State file: {e}",
            errors=[str(e)]
        )
    
    # Execute sync
    result = sync_pulse_from_agent_state(pulse_content, agent_state, preserve_existing)
    
    if result.success and result.updated_document:
        # Generate updated Markdown
        updated_markdown = generate_pulse(result.updated_document)
        
        # Write output file
        output_file = output_path or pulse_file_path
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(updated_markdown)
            result.message = f"Successfully synchronized and saved to {output_file}"
        except Exception as e:
            return SyncResult(
                success=False,
                message=f"Failed to write output file: {e}",
                errors=[str(e)]
            )
    
    return result


def main():
    """Command line entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Synchronize PULSE document with Agent State"
    )
    parser.add_argument(
        "pulse_file",
        help="Path to PULSE document (PROJECT_PULSE.md)"
    )
    parser.add_argument(
        "agent_state_file",
        help="Path to Agent State file (AGENT_STATE.json)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: overwrite input file)"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing Risks & Debt content instead of merging"
    )
    
    args = parser.parse_args()
    
    result = sync_pulse_files(
        args.pulse_file,
        args.agent_state_file,
        args.output,
        preserve_existing=not args.replace
    )
    
    if result.success:
        print(f"✅ {result.message}")
    else:
        print(f"❌ {result.message}")
        for error in result.errors:
            print(f"   - {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
