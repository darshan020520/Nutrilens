#!/usr/bin/env python3
"""
Dependency Graph Generator

Generates a complete dependency graph for a Python file or component,
showing all imports, function calls, and dependencies.

Usage:
    python tools/generate_dependency_graph.py --file backend/app/services/meal_plan_service.py
    python tools/generate_dependency_graph.py --component meal_plan
"""

import ast
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


class DependencyAnalyzer(ast.NodeVisitor):
    """Analyzes Python AST to extract dependencies."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.imports: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.function_calls: List[Dict[str, Any]] = []
        self.current_function = None
        self.current_class = None

    def visit_Import(self, node: ast.Import):
        """Track import statements."""
        for alias in node.names:
            self.imports.append({
                "type": "import",
                "module": alias.name,
                "alias": alias.asname,
                "line": node.lineno
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track from X import Y statements."""
        module = node.module or ""
        for alias in node.names:
            self.imports.append({
                "type": "import_from",
                "module": module,
                "name": alias.name,
                "alias": alias.asname,
                "line": node.lineno
            })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function definitions."""
        self.current_function = node.name

        # Extract parameters
        args = []
        for arg in node.args.args:
            arg_type = None
            if arg.annotation:
                arg_type = ast.unparse(arg.annotation)
            args.append({
                "name": arg.arg,
                "type": arg_type
            })

        # Extract return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        # Check if it's a public function
        is_public = not node.name.startswith("_")

        self.functions.append({
            "name": node.name,
            "line": node.lineno,
            "args": args,
            "return_type": return_type,
            "is_public": is_public,
            "class": self.current_class,
            "decorators": [ast.unparse(d) for d in node.decorator_list]
        })

        self.generic_visit(node)
        self.current_function = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track class definitions."""
        self.current_class = node.name

        bases = [ast.unparse(base) for base in node.bases]

        self.classes.append({
            "name": node.name,
            "line": node.lineno,
            "bases": bases,
            "decorators": [ast.unparse(d) for d in node.decorator_list]
        })

        self.generic_visit(node)
        self.current_class = None

    def visit_Call(self, node: ast.Call):
        """Track function calls."""
        try:
            func_name = ast.unparse(node.func)
            self.function_calls.append({
                "function": func_name,
                "line": node.lineno,
                "in_function": self.current_function,
                "in_class": self.current_class
            })
        except Exception:
            pass

        self.generic_visit(node)


def analyze_file(file_path: str) -> Dict[str, Any]:
    """Analyze a single Python file and extract dependencies."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=file_path)
        analyzer = DependencyAnalyzer(file_path)
        analyzer.visit(tree)

        return {
            "file": file_path,
            "imports": analyzer.imports,
            "functions": analyzer.functions,
            "classes": analyzer.classes,
            "function_calls": analyzer.function_calls
        }
    except Exception as e:
        return {
            "file": file_path,
            "error": str(e)
        }


def find_reverse_dependencies(file_path: str, backend_root: str) -> List[Dict[str, Any]]:
    """Find all files that import the given file."""
    reverse_deps = []
    target_module = file_path.replace(backend_root, "").replace("/", ".").replace("\\", ".").replace(".py", "").strip(".")

    for root, dirs, files in os.walk(backend_root):
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv']]

        for file in files:
            if not file.endswith('.py'):
                continue

            full_path = os.path.join(root, file)
            if full_path == file_path:
                continue

            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content, filename=full_path)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if target_module in alias.name:
                                reverse_deps.append({
                                    "file": full_path.replace(backend_root + "\\", "").replace(backend_root + "/", ""),
                                    "line": node.lineno,
                                    "type": "import",
                                    "statement": f"import {alias.name}"
                                })

                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if target_module in module:
                            for alias in node.names:
                                reverse_deps.append({
                                    "file": full_path.replace(backend_root + "\\", "").replace(backend_root + "/", ""),
                                    "line": node.lineno,
                                    "type": "import_from",
                                    "statement": f"from {module} import {alias.name}"
                                })
            except Exception:
                pass

    return reverse_deps


def generate_dependency_graph(file_path: str, output_dir: str) -> Dict[str, Any]:
    """Generate complete dependency graph for a file."""
    backend_root = os.path.abspath(os.path.join(os.path.dirname(file_path), "..", ".."))

    analysis = analyze_file(file_path)
    reverse_deps = find_reverse_dependencies(file_path, backend_root)

    graph = {
        "component": file_path,
        "analysis": analysis,
        "outgoing_dependencies": {
            "imports": analysis.get("imports", []),
            "total": len(analysis.get("imports", []))
        },
        "incoming_dependencies": {
            "imported_by": reverse_deps,
            "total": len(reverse_deps)
        },
        "public_api": {
            "functions": [f for f in analysis.get("functions", []) if f.get("is_public", False)],
            "classes": analysis.get("classes", [])
        },
        "summary": {
            "total_imports": len(analysis.get("imports", [])),
            "total_functions": len(analysis.get("functions", [])),
            "public_functions": len([f for f in analysis.get("functions", []) if f.get("is_public", False)]),
            "total_classes": len(analysis.get("classes", [])),
            "imported_by_count": len(reverse_deps)
        }
    }

    output_file = os.path.join(output_dir, f"{Path(file_path).stem}_deps.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2)

    print(f"[OK] Dependency graph saved to: {output_file}")

    return graph


def print_summary(graph: Dict[str, Any]):
    """Print a human-readable summary of the dependency graph."""
    print("\n" + "="*80)
    print(f"DEPENDENCY GRAPH: {os.path.basename(graph['component'])}")
    print("="*80)

    summary = graph['summary']
    print(f"\n[Statistics]:")
    print(f"  - Total Imports: {summary['total_imports']}")
    print(f"  - Total Functions: {summary['total_functions']}")
    print(f"  - Public Functions: {summary['public_functions']}")
    print(f"  - Total Classes: {summary['total_classes']}")
    print(f"  - Imported By: {summary['imported_by_count']} files")

    print(f"\n[Outgoing Dependencies] ({summary['total_imports']} imports):")
    for imp in graph['outgoing_dependencies']['imports'][:10]:
        if imp['type'] == 'import':
            print(f"  - Line {imp['line']}: import {imp['module']}")
        else:
            print(f"  - Line {imp['line']}: from {imp['module']} import {imp['name']}")

    if len(graph['outgoing_dependencies']['imports']) > 10:
        print(f"  ... and {len(graph['outgoing_dependencies']['imports']) - 10} more")

    print(f"\n[Incoming Dependencies] ({summary['imported_by_count']} files):")
    for dep in graph['incoming_dependencies']['imported_by'][:10]:
        print(f"  - {dep['file']}:{dep['line']}")

    if len(graph['incoming_dependencies']['imported_by']) > 10:
        print(f"  ... and {len(graph['incoming_dependencies']['imported_by']) - 10} more")

    print(f"\n[Public API]:")
    public_funcs = graph['public_api']['functions']
    if public_funcs:
        print(f"  Functions ({len(public_funcs)}):")
        for func in public_funcs[:10]:
            args_str = ", ".join([f"{a['name']}" for a in func['args']])
            print(f"    - {func['name']}({args_str}) [Line {func['line']}]")
        if len(public_funcs) > 10:
            print(f"    ... and {len(public_funcs) - 10} more")

    classes = graph['public_api']['classes']
    if classes:
        print(f"  Classes ({len(classes)}):")
        for cls in classes:
            print(f"    - {cls['name']} [Line {cls['line']}]")

    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description="Generate dependency graph for Python components")
    parser.add_argument("--file", help="Path to a specific Python file")
    parser.add_argument("--output", default="docs/migration/dependency_graphs", help="Output directory")

    args = parser.parse_args()

    if not args.file:
        parser.error("--file must be specified")

    file_path = os.path.abspath(args.file)
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)

    graph = generate_dependency_graph(file_path, args.output)
    print_summary(graph)


if __name__ == "__main__":
    main()
