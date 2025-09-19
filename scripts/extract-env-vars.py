#!/usr/bin/env python3
"""Extract all environment variables from the codebase."""

import os
import re
from pathlib import Path
from typing import Set, Dict, List

def extract_env_vars(root_dir: Path) -> Dict[str, List[str]]:
    """Extract environment variables from source files."""
    env_vars: Dict[str, Set[str]] = {}
    
    # Patterns to match environment variable access
    patterns = {
        'typescript': [
            r'process\.env\.(\w+)',
            r'process\.env\["([^"]+)"\]',
            r"process\.env\['([^']+)'\]"
        ],
        'python': [
            r'os\.environ\.get\(["\'](\w+)',
            r'os\.environ\[["\'](\w+)',
            r'os\.getenv\(["\'](\w+)',
            r'environ\.get\(["\'](\w+)'
        ]
    }
    
    # File extensions to search
    extensions = {
        '.ts': 'typescript',
        '.tsx': 'typescript', 
        '.js': 'typescript',
        '.jsx': 'typescript',
        '.py': 'python'
    }
    
    for path in root_dir.rglob('*'):
        if not path.is_file():
            continue
            
        # Skip node_modules and other build directories
        if any(part in path.parts for part in ['node_modules', 'dist', 'build', '.git', '__pycache__']):
            continue
            
        ext = path.suffix
        if ext not in extensions:
            continue
            
        lang = extensions[ext]
        
        try:
            content = path.read_text(encoding='utf-8')
            
            for pattern in patterns[lang]:
                matches = re.findall(pattern, content)
                for match in matches:
                    if lang not in env_vars:
                        env_vars[lang] = set()
                    env_vars[lang].add(match)
        except Exception as e:
            print(f"Error reading {path}: {e}")
    
    # Convert sets to sorted lists
    result = {lang: sorted(list(vars_set)) for lang, vars_set in env_vars.items()}
    return result

def main():
    """Main function."""
    root = Path('/home/jmagar/compose/firecrawl')
    
    # Extract variables
    env_vars = extract_env_vars(root)
    
    # Get unique variables across all languages
    all_vars = set()
    for vars_list in env_vars.values():
        all_vars.update(vars_list)
    
    print("# Environment Variables Used in Code\n")
    print(f"Total unique variables: {len(all_vars)}\n")
    
    # Print by language
    for lang, vars_list in env_vars.items():
        print(f"\n## {lang.upper()} ({len(vars_list)} variables)")
        for var in vars_list:
            print(f"  - {var}")
    
    # Print combined sorted list
    print(f"\n## All Variables (alphabetical)")
    for var in sorted(all_vars):
        # Check which .env files contain this variable
        sources = []
        
        # Check root .env
        root_env = root / '.env'
        if root_env.exists():
            content = root_env.read_text()
            if re.search(f'^{re.escape(var)}=', content, re.MULTILINE):
                sources.append("root")
        
        # Check MCP .env
        mcp_env = root / 'apps/firecrawler/.env'
        if mcp_env.exists():
            content = mcp_env.read_text()
            if re.search(f'^{re.escape(var)}=', content, re.MULTILINE):
                sources.append("mcp")
        
        source_str = f" [{', '.join(sources)}]" if sources else " [NOT IN ENV]"
        print(f"  - {var}{source_str}")

if __name__ == "__main__":
    main()