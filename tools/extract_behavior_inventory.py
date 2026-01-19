#!/usr/bin/env python3
"""
Behavior Inventory Extractor

Extracts behavior inventory from a Python file by analyzing public methods,
their signatures, side effects, and business rules.

Usage:
    python tools/extract_behavior_inventory.py --file backend/app/services/meal_plan_service.py
"""

import ast
import os
import sys
import argparse
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class BehaviorExtractor(ast.NodeVisitor):
    """Extracts behavior information from Python code."""

    def __init__(self, file_path: str, source_code: str):
        self.file_path = file_path
        self.source_code = source_code
        self.source_lines = source_code.split('\n')
        self.behaviors = []
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extract behavior from function definitions."""
        if not node.name.startswith("_"):
            behavior = self._extract_function_behavior(node)
            self.behaviors.append(behavior)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Extract behavior from async function definitions."""
        if not node.name.startswith("_"):
            behavior = self._extract_function_behavior(node, is_async=True)
            self.behaviors.append(behavior)

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track current class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def _extract_function_behavior(self, node, is_async=False) -> Dict[str, Any]:
        """Extract detailed behavior from a function node."""
        args = self._extract_parameters(node.args)
        return_type = self._extract_return_type(node.returns)
        docstring = ast.get_docstring(node)

        side_effects = self._detect_side_effects(node)
        business_rules = self._extract_business_rules(node, docstring)
        error_conditions = self._extract_error_conditions(node)

        signature = self._build_signature(node.name, args, return_type, is_async)

        return {
            "name": node.name,
            "line": node.lineno,
            "class": self.current_class,
            "signature": signature,
            "is_async": is_async,
            "parameters": args,
            "return_type": return_type,
            "docstring": docstring,
            "side_effects": side_effects,
            "business_rules": business_rules,
            "error_conditions": error_conditions
        }

    def _extract_parameters(self, args: ast.arguments) -> List[Dict[str, Any]]:
        """Extract parameter information."""
        params = []
        for arg in args.args:
            param = {
                "name": arg.arg,
                "type": ast.unparse(arg.annotation) if arg.annotation else "Any",
                "has_default": False
            }
            params.append(param)

        if args.defaults:
            num_defaults = len(args.defaults)
            for i, default in enumerate(args.defaults):
                param_idx = len(params) - num_defaults + i
                params[param_idx]["has_default"] = True
                params[param_idx]["default"] = ast.unparse(default)

        return params

    def _extract_return_type(self, returns) -> str:
        """Extract return type annotation."""
        if returns:
            return ast.unparse(returns)
        return "Any"

    def _build_signature(self, name: str, params: List[Dict], return_type: str, is_async: bool) -> str:
        """Build function signature string."""
        async_prefix = "async " if is_async else ""
        params_str = ", ".join([
            f"{p['name']}: {p['type']}" + (f" = {p.get('default', '')}" if p.get('has_default') else "")
            for p in params
        ])
        return f"{async_prefix}def {name}({params_str}) -> {return_type}"

    def _detect_side_effects(self, node) -> List[str]:
        """Detect side effects in function body."""
        side_effects = []

        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                attr_name = ast.unparse(child)

                if "db." in attr_name or ".query" in attr_name or ".add" in attr_name:
                    side_effects.append(f"Database operation: {attr_name}")

                elif "event_bus" in attr_name or ".publish" in attr_name:
                    side_effects.append(f"Event publication: {attr_name}")

                elif "logger" in attr_name or ".log" in attr_name:
                    side_effects.append(f"Logging: {attr_name}")

                elif ".commit" in attr_name:
                    side_effects.append("Database commit")

                elif ".delete" in attr_name:
                    side_effects.append("Database deletion")

            elif isinstance(child, ast.Call):
                func_name = ast.unparse(child.func) if hasattr(child, 'func') else ""

                if "requests." in func_name or "http" in func_name.lower():
                    side_effects.append(f"HTTP request: {func_name}")

                elif "redis" in func_name.lower():
                    side_effects.append(f"Redis operation: {func_name}")

        return list(set(side_effects))

    def _extract_business_rules(self, node, docstring: Optional[str]) -> List[str]:
        """Extract business rules from function body and docstring."""
        rules = []

        for child in ast.walk(node):
            if isinstance(child, ast.If):
                condition = ast.unparse(child.test)
                rules.append(f"Conditional: {condition}")

            elif isinstance(child, ast.Raise):
                if child.exc:
                    exc_type = ast.unparse(child.exc)
                    rules.append(f"Raises: {exc_type}")

        if docstring:
            for line in docstring.split('\n'):
                if 'must' in line.lower() or 'cannot' in line.lower() or 'should' in line.lower():
                    rules.append(f"Rule from doc: {line.strip()}")

        return rules[:10]

    def _extract_error_conditions(self, node) -> List[str]:
        """Extract error conditions and exception handling."""
        errors = []

        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc:
                    exc_info = ast.unparse(child.exc)
                    errors.append(f"Raises: {exc_info}")

            elif isinstance(child, ast.ExceptHandler):
                exc_type = ast.unparse(child.type) if child.type else "Exception"
                errors.append(f"Catches: {exc_type}")

        return errors


def generate_behavior_inventory(file_path: str, output_dir: str) -> str:
    """Generate behavior inventory markdown document."""
    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()

    tree = ast.parse(source_code, filename=file_path)
    extractor = BehaviorExtractor(file_path, source_code)
    extractor.visit(tree)

    component_name = Path(file_path).stem
    md_content = _build_markdown(component_name, file_path, extractor.behaviors)

    output_file = os.path.join(output_dir, f"{component_name}_inventory.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"[OK] Behavior inventory saved to: {output_file}")
    return output_file


def _build_markdown(component_name: str, file_path: str, behaviors: List[Dict]) -> str:
    """Build markdown document from extracted behaviors."""
    md = f"""# Component: {component_name} - Behavior Inventory

**File**: `{file_path}`
**Generated**: {_get_timestamp()}
**Public Methods**: {len(behaviors)}

---

## Overview

This document inventories all public methods in the `{component_name}` component,
documenting their behavior, parameters, return values, side effects, and business rules.

**Purpose**: Ensure zero behavior changes during restructuring migration.

---

## Public Methods

"""

    for i, behavior in enumerate(behaviors, 1):
        md += f"""### {i}. `{behavior['name']}`

**Signature**:
```python
{behavior['signature']}
```

**Location**: Line {behavior['line']}
{f"**Class**: `{behavior['class']}`" if behavior['class'] else ""}

"""

        if behavior['parameters']:
            md += "**Parameters**:\n"
            for param in behavior['parameters']:
                default_info = f" (default: `{param.get('default', '')}`))" if param.get('has_default') else ""
                md += f"- `{param['name']}`: `{param['type']}`{default_info}\n"
            md += "\n"

        md += f"**Returns**: `{behavior['return_type']}`\n\n"

        if behavior['docstring']:
            md += f"**Documentation**:\n```\n{behavior['docstring']}\n```\n\n"

        if behavior['side_effects']:
            md += "**Side Effects**:\n"
            for effect in behavior['side_effects']:
                md += f"- {effect}\n"
            md += "\n"

        if behavior['business_rules']:
            md += "**Business Rules**:\n"
            for rule in behavior['business_rules']:
                md += f"- {rule}\n"
            md += "\n"

        if behavior['error_conditions']:
            md += "**Error Conditions**:\n"
            for error in behavior['error_conditions']:
                md += f"- {error}\n"
            md += "\n"

        md += "**Called By**: _(To be filled by dependency graph)_\n\n"
        md += "**Test Coverage**: _(To be filled manually)_\n\n"
        md += "---\n\n"

    md += """
## Migration Checklist

- [ ] All public methods documented
- [ ] All parameters documented
- [ ] All return types documented
- [ ] All side effects identified
- [ ] All business rules extracted
- [ ] All error conditions listed
- [ ] Dependency graph generated
- [ ] Test coverage verified
- [ ] Manual review completed

## Notes

_(Add any additional notes about this component's behavior)_

"""

    return md


def _get_timestamp() -> str:
    """Get current timestamp."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Extract behavior inventory from Python file")
    parser.add_argument("--file", required=True, help="Path to Python file")
    parser.add_argument("--output", default="docs/migration/behavior_inventories", help="Output directory")

    args = parser.parse_args()

    file_path = os.path.abspath(args.file)
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)

    output_file = generate_behavior_inventory(file_path, args.output)
    print(f"\n[INFO] Review the behavior inventory and fill in:")
    print("  - 'Called By' for each method (use dependency graph)")
    print("  - 'Test Coverage' for each method")
    print("  - Any additional notes")


if __name__ == "__main__":
    main()
