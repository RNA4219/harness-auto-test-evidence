import ast
import dataclasses
import importlib
import inspect
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "rust/downstream"
GROUPS = {
    "external": [
        "evaluation.real_repo.build_real_repo_evaluation_report",
        "policy_config.build_platform_policy_report",
        "plugins.sandbox.build_plugin_sandbox_report",
    ],
    "workflow": ["p1b.generate_workflow_mapping"],
    "readiness": ["p2p3.generate_product_readiness"],
    "release": ["compat.v0_2.handlers._assemble_release_candidate"],
    "grade": ["product_grade.generate_product_grade_reports"],
    "expansion": ["expansion_runner.run_expansion_suite"],
    "gap": ["gap_closure.generate_gap_closure_report"],
}


def resolve_name(name):
    module, fun = name.rsplit(".", 1)
    return getattr(importlib.import_module("hate." + module), fun)


@lru_cache
def tree(f):
    return ast.parse(textwrap.dedent(inspect.getsource(f))).body[0]


def ident(f):
    return f.__module__.removeprefix("hate.").replace(".", "__") + "__" + f.__qualname__.replace(".", "__").lstrip("_")


def closure(roots):
    funcs = {}
    constants = {}
    special = {}
    for f in roots:
        if f in funcs:
            continue
        n = tree(f)
        funcs[f] = n
        locs = {a.arg for a in n.args.args + n.args.kwonlyargs} | {
            node.id for node in ast.walk(n) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        for nm in {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)} - locs:
            val = f.__globals__.get(nm)
            if inspect.isfunction(val) and val.__module__.startswith("hate."):
                roots.append(val)
            elif inspect.isclass(val) and val.__module__.startswith("hate.") and dataclasses.is_dataclass(val):
                special[val] = 1
                for method in ("as_report", "to_report", "is_complete", "to_dict"):
                    if val.__name__ in (
                        "RateLimitDecision",
                        "TenantScope",
                        "RBACDecision",
                        "EntitlementDecision",
                        "GitHubIntegrationDecision",
                        "DiagnosticBundleResult",
                        "ObservabilityReport",
                        "TenantDecision",
                    ) and method in vars(val):
                        roots.append(getattr(val, method))
            elif val is not None and isinstance(val, (str, int, dict, tuple, list, set, frozenset)):
                constants[(f.__module__, nm)] = val

                def visit(v):
                    if inspect.isfunction(v) and v.__module__.startswith("hate."):
                        roots.append(v)
                    elif dataclasses.is_dataclass(v):
                        visit(list(vars(v).values()))
                    elif isinstance(v, dict):
                        visit(list(v.values()))
                    elif isinstance(v, (tuple, list)):
                        for x in v:
                            visit(x)

                visit(val)
    return funcs, constants, special
