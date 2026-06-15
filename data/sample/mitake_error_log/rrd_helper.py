"""
RRD Tool Helper Module
Provides Python wrapper around the system rrdtool command-line tool
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any


def run_rrdtool(*args: str) -> str:
    """
    Execute rrdtool command with given arguments.
    
    Args:
        *args: Command arguments for rrdtool
        
    Returns:
        str: Output from rrdtool command
        
    Raises:
        RuntimeError: If rrdtool command fails
    """
    try:
        result = subprocess.run(
            ["rrdtool"] + list(args),
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"rrdtool error: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("rrdtool not found. Install with: brew install rrdtool")


def fetch_rrd(rrd_file: str, cf: str = "AVERAGE", start: int = None, end: int = None) -> Dict[str, Any]:
    """
    Fetch data from an RRD file.
    
    Args:
        rrd_file: Path to RRD file
        cf: Consolidation function (AVERAGE, MIN, MAX, LAST)
        start: Start time (unix timestamp or relative like -1d)
        end: End time (unix timestamp or relative like now)
        
    Returns:
        dict: Parsed RRD data
    """
    args = [rrd_file, cf]
    if start:
        args.append(f"--start={start}")
    if end:
        args.append(f"--end={end}")
    
    output = run_rrdtool("fetch", *args)
    return parse_rrd_fetch(output)


def parse_rrd_fetch(output: str) -> Dict[str, Any]:
    """Parse output from rrdtool fetch command."""
    lines = output.splitlines()
    
    header = {}
    data = []
    header_found = False
    
    for line in lines:
        if not line.strip():
            continue
        
        if not header_found and ':' not in line:
            # First non-empty header line contains the data source names.
            header['columns'] = line.split()
            header_found = True
            continue
        
        if not header_found:
            # Skip any leading lines before the header.
            continue
        
        if ':' in line:
            try:
                timestamp_str, value_str = line.split(':', 1)
                timestamp = int(timestamp_str.strip())
                values = []
                for v in value_str.strip().split():
                    if v.lower() == 'nan':
                        values.append(None)
                    else:
                        values.append(float(v))
                data.append({"timestamp": timestamp, "values": values})
            except (ValueError, IndexError):
                continue
    
    return {
        "header": header,
        "data": data
    }


def info_rrd(rrd_file: str) -> Dict[str, Any]:
    """
    Get information about an RRD file.
    
    Args:
        rrd_file: Path to RRD file
        
    Returns:
        dict: RRD file information
    """
    output = run_rrdtool("info", rrd_file)
    info = {}
    
    for line in output.strip().split('\n'):
        parts = line.split(' = ', 1)
        if len(parts) == 2:
            key = parts[0].strip()
            value = parts[1].strip().strip('"')
            info[key] = value
    
    return info


if __name__ == "__main__":
    # Test if rrdtool is available
    try:
        output = run_rrdtool("version")
        print("rrdtool is available:")
        print(output)
    except RuntimeError as e:
        print(f"Error: {e}")
