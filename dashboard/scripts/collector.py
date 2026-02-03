#!/usr/bin/env python3
"""
Tmux Event Collector

Polls tmux panes and extracts JSON events for the dashboard.
Outputs normalized events to stdout as JSON lines.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PaneInfo:
    pane_id: str
    window_id: str
    window_name: str
    session_name: str
    current_command: str
    pane_pid: int


@dataclass 
class Event:
    id: str
    timestamp: float
    source: dict
    event_type: str
    content: str
    raw: Optional[str] = None


class TmuxCollector:
    """Collects events from tmux panes."""
    
    def __init__(self, session_name: Optional[str] = None):
        self.session_name = session_name  # None = all sessions
        self.pane_buffers: dict[str, list[str]] = {}
        self.event_counter = 0
    
    def run_tmux(self, *args: str) -> str:
        """Execute a tmux command and return output."""
        try:
            result = subprocess.run(
                ["tmux"] + list(args),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return ""
    
    def get_panes(self) -> list[PaneInfo]:
        """Get all panes, optionally filtered by session."""
        # -a flag lists ALL panes across ALL sessions
        cmd = ["list-panes", "-a", "-F", 
               "#{pane_id}|#{window_id}|#{window_name}|#{session_name}|#{pane_current_command}|#{pane_pid}"]
        
        output = self.run_tmux(*cmd)
        
        panes = []
        for line in output.split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) >= 6:
                session = parts[3]
                # Filter by session if specified
                if self.session_name and session != self.session_name:
                    continue
                panes.append(PaneInfo(
                    pane_id=parts[0],
                    window_id=parts[1],
                    window_name=parts[2],
                    session_name=session,
                    current_command=parts[4],
                    pane_pid=int(parts[5]) if parts[5].isdigit() else 0
                ))
        return panes
    
    def capture_pane(self, pane_id: str, lines: int = 500) -> list[str]:
        """Capture the last N lines from a pane."""
        output = self.run_tmux(
            "capture-pane", "-pe", "-S", f"-{lines}", "-t", pane_id
        )
        return output.split("\n")
    
    def extract_new_lines(self, pane_id: str, current_lines: list[str]) -> list[str]:
        """Extract only new lines since last capture using line count tracking."""
        # Filter out empty lines for comparison
        non_empty = [l for l in current_lines if l.strip()]
        
        previous_count = self.pane_buffers.get(pane_id, 0)
        current_count = len(non_empty)
        
        # Store current count for next comparison
        self.pane_buffers[pane_id] = current_count
        
        if previous_count == 0:
            # First capture: return last 10 lines for context
            return non_empty[-10:] if len(non_empty) > 10 else non_empty
        
        if current_count <= previous_count:
            # No new lines or pane was cleared
            return []
        
        # Return only the truly new lines
        new_count = current_count - previous_count
        return non_empty[-new_count:] if new_count <= 20 else non_empty[-20:]
    
    def parse_event(self, line: str, pane: PaneInfo) -> Optional[Event]:
        """Parse a line into an event if it contains meaningful content."""
        line = line.strip()
        if not line:
            return None
        
        self.event_counter += 1
        event_id = f"evt-{self.event_counter:06d}"
        
        # Detect event type
        event_type = "message"
        
        # JSON detection
        if line.startswith("{") and "tool" in line.lower():
            event_type = "tool_call"
        elif '"error"' in line.lower() or line.startswith("Error:"):
            event_type = "error"
        elif '"status"' in line.lower():
            event_type = "status"
        elif any(kw in line.lower() for kw in ["passed", "failed", "test"]):
            event_type = "test_result"
        elif any(kw in line.lower() for kw in ["modified", "created", "deleted"]):
            event_type = "file_change"
        elif line.startswith("$") or line.startswith(">"):
            event_type = "command"
        
        return Event(
            id=event_id,
            timestamp=time.time(),
            source={
                "session": pane.session_name,
                "window": pane.window_name,
                "pane": pane.pane_id,
                "command": pane.current_command
            },
            event_type=event_type,
            content=line
        )
    
    def collect_once(self) -> list[dict]:
        """Perform one collection cycle."""
        events = []
        
        for pane in self.get_panes():
            lines = self.capture_pane(pane.pane_id)
            new_lines = self.extract_new_lines(pane.pane_id, lines)
            
            for line in new_lines:
                event = self.parse_event(line, pane)
                if event:
                    events.append(asdict(event))
        
        return events
    
    def build_session_state(self) -> dict:
        """Build session state with windows and panes for sidebar display."""
        panes = self.get_panes()
        
        # Group panes by window
        windows_map: dict[str, dict] = {}
        for pane in panes:
            win_id = pane.window_id
            if win_id not in windows_map:
                windows_map[win_id] = {
                    "id": win_id,
                    "name": pane.window_name,
                    "isActive": False,
                    "panes": []
                }
            
            # Determine pane status based on command
            cmd = pane.current_command.lower()
            if "python" in cmd or "node" in cmd or "npm" in cmd:
                status = "busy"
            elif cmd in ["bash", "zsh", "sh", "fish"]:
                status = "idle"
            else:
                status = "active"
            
            windows_map[win_id]["panes"].append({
                "id": pane.pane_id,
                "command": pane.current_command,
                "status": status,
                "eventCount": 0
            })
        
        # Mark first window as active
        windows = list(windows_map.values())
        if windows:
            windows[0]["isActive"] = True
        
        return {
            "name": self.session_name or "all",
            "windows": windows,
            "connected": True
        }
    
    def stream(self, interval_ms: int = 500):
        """Stream events continuously."""
        interval_sec = interval_ms / 1000.0
        state_interval = 5  # Send session state every 5 seconds
        last_state_time = 0.0
        
        print(json.dumps({
            "type": "init",
            "session": self.session_name or "all",
            "timestamp": time.time()
        }), flush=True)
        
        # Send initial session state
        state = self.build_session_state()
        print(json.dumps({
            "type": "session_state",
            "state": state,
            "timestamp": time.time()
        }), flush=True)
        last_state_time = time.time()
        
        while True:
            try:
                events = self.collect_once()
                if events:
                    for event in events:
                        print(json.dumps(event), flush=True)
                
                # Periodically send session state updates
                if time.time() - last_state_time >= state_interval:
                    state = self.build_session_state()
                    print(json.dumps({
                        "type": "session_state",
                        "state": state,
                        "timestamp": time.time()
                    }), flush=True)
                    last_state_time = time.time()
                
                time.sleep(interval_sec)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(json.dumps({
                    "type": "error",
                    "message": str(e),
                    "timestamp": time.time()
                }), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Tmux Event Collector")
    parser.add_argument("--session", "-s", default=None, help="Tmux session name (omit for all)")
    parser.add_argument("--interval", "-i", type=int, default=500, help="Poll interval in ms")
    parser.add_argument("--test", action="store_true", help="Run in test mode (single capture)")
    
    args = parser.parse_args()
    
    collector = TmuxCollector(args.session)
    
    if args.test:
        events = collector.collect_once()
        print(json.dumps({"events": events, "count": len(events)}, indent=2))
    else:
        collector.stream(args.interval)


if __name__ == "__main__":
    main()
