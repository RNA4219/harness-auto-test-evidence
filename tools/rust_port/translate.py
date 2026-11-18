"""互換版の帳票式と制御構文を、それぞれ serde_json の値操作と Rust の文に変換する。"""

import ast
import dataclasses
import inspect
import json
import re

from inspect_rules import GROUPS, OUT, closure, ident, resolve_name

groups = list(GROUPS)
funcs, constants, classes = closure([resolve_name(n) for g in groups for n in GROUPS[g]])
dest = OUT / "rules"
dest.mkdir(parents=True, exist_ok=True)


def var(s):
    if s == "self":
        return "record"
    return (
        "r#" + s
        if s
        in "as break const continue crate else enum extern false fn for if impl in let loop match mod move mut pub ref return static struct super trait true type unsafe use where while async await dyn try gen override final become abstract box typeof unsized virtual yield".split()
        else s
    )


def rs(s):
    return json.dumps(s, ensure_ascii=False)


def slug(s):
    return s.removeprefix("hate.").replace(".", "_")


def const(v):
    if v is None:
        return "Value::Null"
    if isinstance(v, bool):
        return "json!(" + str(v).lower() + ")"
    if isinstance(v, str):
        return "json!(" + rs(v) + ")"
    if isinstance(v, (int, float)):
        return "json!(" + str(v) + ")"
    if isinstance(v, re.Pattern):
        return const(v.pattern)
    if isinstance(v, type):
        return "json!(" + rs(v.__name__) + ")"
    if inspect.isfunction(v):
        return "json!(" + rs(ident(v)) + ")"
    raise ValueError(v)


def data(v):
    if isinstance(v, dict):
        return {str(k): data(x) for k, x in v.items()}
    if isinstance(v, (set, frozenset)):
        return [data(x) for x in sorted(v)]
    if isinstance(v, (tuple, list)):
        return [data(x) for x in v]
    if dataclasses.is_dataclass(v):
        return data(vars(v))
    if inspect.isfunction(v):
        return ident(v)
    return v


cache = {}


def constant(f, key, value):
    if not isinstance(value, (dict, list, tuple, set, frozenset)):
        return const(value)
    label = slug(f.__module__) + "_" + key
    cache[label] = data(value)
    return f"catalog({rs(label)})"


def args_for(f, args, keywords):
    sig = inspect.signature(f)
    bound = sig.bind(*args, **keywords)
    return [
        ("Value::Array(vec![" + ",".join(bound.arguments.get(k, ())) + "])")
        if v.kind == inspect.Parameter.VAR_POSITIONAL
        else bound.arguments[k]
        if k in bound.arguments
        else const(v.default)
        for k, v in sig.parameters.items()
    ]


def pth(x):
    return "to_path(&" + x + ")"


def txt(x):
    return "values::text(&" + x + ")"


def sprintf(n, exp):
    parts = []
    args = []
    for v in n.values:
        if isinstance(v, ast.Constant):
            parts.append(v.value.replace("{", "{{").replace("}", "}}"))
            continue
        spec = v.format_spec.values[0].value if v.format_spec else ""
        if spec in ("04d", "02d"):
            arg = "integer(&" + exp(v.value) + ")?"
            fmt = ":" + spec[:-1]
        elif spec == ".2f":
            arg = "number(&" + exp(v.value) + ")?"
            fmt = ":.2"
        elif not spec:
            arg = txt(exp(v.value))
            fmt = ""
        else:
            raise ValueError("format " + spec)
        parts.append("{" + fmt + "}")
        args.append(arg)
    return "json!(format!(" + ",".join([rs("".join(parts)), *args]) + "))"


type_methods = {}
for mod, method, instance, cls in [
    ("api.rate_limit", "as_report", "*", "RateLimitDecision"),
    ("api.rate_limit", "is_complete", "*", "TenantScope"),
    ("entitlement", "as_report", "*", "EntitlementDecision"),
    ("github_integration", "as_report", "*", "GitHubIntegrationDecision"),
    ("support_ops.diagnostics", "to_report", "*", "DiagnosticBundleResult"),
    ("tenant_isolation", "to_report", "*", "TenantDecision"),
    ("support_ops.observability", "to_dict", "*", "ObservabilityReport"),
    ("enterprise.control_packet", "to_dict", "evaluate_rbac(actor, request, source_refs)", "RBACDecision"),
]:
    clsobj = next((c for c in classes if c.__name__ == cls), None)
    if clsobj:
        type_methods[("hate." + mod, method, instance)] = getattr(clsobj, method)


def is_ref(f, param):
    return (
        f.__module__.endswith("plugins.sandbox")
        and param == "findings"
        or f.__module__.endswith("runtime_worker")
        and (
            param == "job"
            and f.__name__ in ("_apply_error", "_cancel_job", "_apply_worker_event")
            or param == "idempotency_seen"
        )
        or f.__name__ == "_escalate_fixture_budget_exceeded"
        and param == "report"
    )


class Port:
    def __init__(self, f, n):
        self.f, self.n = f, n
        self.gl = f.__globals__
        self.parameters = [a.arg for a in n.args.args + n.args.kwonlyargs] + (
            [n.args.vararg.arg] if n.args.vararg else []
        )
        self.ref_vars = {p for p in self.parameters if is_ref(f, p)}
        self.locals = set(self.parameters) | {
            e.id for e in ast.walk(n) if isinstance(e, ast.Name) and isinstance(e.ctx, ast.Store)
        }

    def expr(self, n):
        e = self.expr
        if isinstance(n, ast.Constant):
            return const(n.value)
        if isinstance(n, ast.Name):
            if n.id in self.locals:
                return var(n.id) + ".clone()"
            if n.id in self.gl:
                return constant(self.f, n.id, self.gl[n.id])
            raise ValueError(n.id)
        if isinstance(n, ast.JoinedStr):
            return sprintf(n, e)
        if isinstance(n, ast.Subscript):
            if isinstance(n.slice, ast.Slice):
                s = n.slice
                return (
                    "slice(&"
                    + e(n.value)
                    + ","
                    + (",".join("Some(integer(&" + e(x) + ")?)" if x else "None" for x in [s.lower, s.upper]))
                    + ")"
                )
            return "indexed(&" + e(n.value) + ",&" + e(n.slice) + ")?"
        if isinstance(n, ast.Attribute):
            if ast.unparse(n) == "uuid.NAMESPACE_URL":
                return 'json!("url")'
            if n.attr == "hex" and ast.unparse(n.value).startswith("uuid.uuid5"):
                return e(n.value)
            v = e(n.value)
            if n.attr in ["parent", "stem", "name"] and (
                n.attr in ("parent", "stem") or "path" in ast.unparse(n.value).lower() or "dir" in ast.unparse(n.value)
            ):
                return "path_part(&" + v + "," + rs(n.attr) + ")"
            if n.attr == "days":
                return v
            return "attr(&" + v + "," + rs(n.attr) + ")"
        if isinstance(n, ast.Dict):
            if all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in n.keys):
                if not n.keys:
                    return "json!({})"
                return (
                    "Value::Object(["
                    + ",".join("(" + rs(k.value) + ".into()," + e(v) + ")" for k, v in zip(n.keys, n.values))
                    + "].into_iter().collect())"
                )
            body = "let mut object=json!({});"
            for k, v in zip(n.keys, n.values):
                body += "merge(&mut object," + e(v) + ")?;" if k is None else "object[" + txt(e(k)) + "]=" + e(v) + ";"
            return "{" + body + "object}"
        if isinstance(n, (ast.List, ast.Tuple, ast.Set)):
            if any(isinstance(x, ast.Starred) for x in n.elts):
                body = "let mut collected_values=Vec::new();"
                for x in n.elts:
                    body += (
                        "collected_values.extend(sequence(&" + e(x.value) + ")?);"
                        if isinstance(x, ast.Starred)
                        else "collected_values.push(" + e(x) + ");"
                    )
                return "{" + body + "Value::Array(collected_values)}"
            inner = "vec![" + ",".join(e(x) for x in n.elts) + "]"
            return ("unique(" if isinstance(n, ast.Set) else "Value::Array(") + inner + ")"
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            obj = isinstance(n, ast.DictComp)
            intro = "let mut collected_values=" + ("json!({});" if obj else "Vec::new();")
            inner = (
                "collected_values[" + txt(e(n.key)) + "]=" + e(n.value) + ";"
                if obj
                else "collected_values.push(" + e(n.elt) + ");"
            )
            for g in reversed(n.generators):
                conds = "".join("if !(" + self.cond(x) + "){continue;}" for x in g.ifs)
                inner = self.forloop(g.target, g.iter, conds + inner)
            end = (
                "collected_values"
                if obj
                else "unique(collected_values)"
                if isinstance(n, ast.SetComp)
                else "Value::Array(collected_values)"
            )
            return "{" + intro + inner + end + "}"
        if isinstance(n, ast.IfExp):
            return "(if " + self.cond(n.test) + "{" + e(n.body) + "}else{" + e(n.orelse) + "})"
        if isinstance(n, (ast.UnaryOp, ast.Compare, ast.BoolOp)):
            if isinstance(n, ast.BoolOp):
                ar = [e(x) for x in n.values]
                acc = ar.pop()
                for x in reversed(ar):
                    acc = (
                        "{let first="
                        + x
                        + "; if "
                        + ("!" if isinstance(n.op, ast.And) else "")
                        + "truth(&first){first}else{"
                        + acc
                        + "}}"
                    )
                return acc
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
                return "arithmetic(&json!(0),&" + e(n.operand) + ',"-")?'
            return "json!(" + self.cond(n) + ")"
        if isinstance(n, ast.BinOp):
            path = isinstance(n.op, ast.Div) and (
                "path" in ast.unparse(n.left)
                or any(s in ast.unparse(n.left) for s in ["dir", "root", "base", "path", "store"])
            )
            if path:
                return "join_path(&" + e(n.left) + ",&" + e(n.right) + ")"
            op = {
                ast.Add: "+",
                ast.Sub: "-",
                ast.Mult: "*",
                ast.Div: "/",
                ast.FloorDiv: "//",
                ast.Mod: "%",
                ast.BitAnd: "&",
                ast.BitOr: "|",
            }[type(n.op)]
            return "arithmetic(&" + e(n.left) + ",&" + e(n.right) + "," + rs(op) + ")?"
        if isinstance(n, ast.Call):
            return self.call(n)
        raise ValueError("unsupported " + ast.dump(n)[:150])

    def cond(self, n):
        e = self.expr
        c = self.cond
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return "!(" + c(n.operand) + ")"
        if isinstance(n, ast.BoolOp):
            return (" && " if isinstance(n.op, ast.And) else " || ").join("(" + c(v) + ")" for v in n.values)
        if isinstance(n, ast.Compare):
            vs = [n.left, *n.comparators]
            parts = []
            for i, op in enumerate(n.ops):
                l, r = e(vs[i]), e(vs[i + 1])
                cls = type(op)
                if cls in (ast.In, ast.NotIn):
                    parts.append(("!" if cls == ast.NotIn else "") + "contains(&" + r + ",&" + l + ")")
                elif cls in (ast.Is, ast.IsNot, ast.Eq, ast.NotEq):
                    parts.append(("!" if cls in (ast.NotEq, ast.IsNot) else "") + "equal(&" + l + ",&" + r + ")")
                elif any(
                    isinstance(node, (ast.Set, ast.SetComp))
                    or isinstance(node, ast.Call)
                    and ast.unparse(node.func) == "set"
                    for node in vs[i : i + 2]
                ):
                    subset, superset = (r, l) if cls in (ast.Gt, ast.GtE) else (l, r)
                    parts.append(
                        "is_subset(&"
                        + subset
                        + ",&"
                        + superset
                        + ","
                        + ("true" if cls in (ast.Lt, ast.Gt) else "false")
                        + ")?"
                    )
                else:
                    parts.append(
                        "compare(&"
                        + l
                        + ",&"
                        + r
                        + ")."
                        + {ast.Lt: "is_lt", ast.Gt: "is_gt", ast.LtE: "is_le", ast.GtE: "is_ge"}[cls]
                        + "()"
                    )
            return " && ".join(parts)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "isinstance":
            classes = (
                n.args[1].elts
                if isinstance(n.args[1], ast.Tuple)
                else n.args[1].values
                if isinstance(n.args[1], ast.BoolOp)
                else [n.args[1]]
            )
            return (
                "("
                + " || ".join(
                    e(n.args[0])
                    + "."
                    + {
                        "dict": "is_object",
                        "list": "is_array",
                        "tuple": "is_array",
                        "str": "is_string",
                        "int": "is_i64",
                        "float": "is_number",
                        "bool": "is_boolean",
                    }.get(k.id, "is_object")
                    + "()"
                    for k in classes
                )
                + ")"
            )
        return "truth(&" + e(n) + ")"

    def bind(self, target, expr, declare=False):
        p = "let mut " if declare else ""
        if isinstance(target, ast.Name):
            return ("let " if declare and target.id == "_" else p) + var(target.id) + "=" + expr + ";"
        if isinstance(target, (ast.Tuple, ast.List)):
            body = "let bound_values=" + expr + ";"
            return body + "".join(
                self.bind(v, f"indexed(&bound_values,&json!({i}))?", declare) for i, v in enumerate(target.elts)
            )
        if isinstance(target, ast.Attribute):
            return self.bind(ast.Subscript(target.value, ast.Constant(target.attr)), expr)
        if isinstance(target, ast.Subscript):
            return (
                "{let incoming="
                + expr
                + ";let index="
                + self.expr(target.slice)
                + ";set_index("
                + self.mut(target.value)
                + ",&index,incoming)?;}"
            )
        raise ValueError("assign " + ast.unparse(target))

    def mut(self, n):
        if isinstance(n, ast.Name):
            return var(n.id) if n.id in self.ref_vars else "&mut " + var(n.id)
        if isinstance(n, ast.Attribute):
            return self.mut(ast.Subscript(n.value, ast.Constant(n.attr)))
        if isinstance(n, ast.Subscript):
            return "index_mut(" + self.mut(n.value) + ",&" + self.expr(n.slice) + ")?"
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "setdefault":
            return (
                "default_mut("
                + self.mut(n.func.value)
                + ",&"
                + self.expr(n.args[0])
                + ","
                + self.expr(n.args[1])
                + ")?"
            )
        raise ValueError("mutation " + ast.unparse(n))

    def forloop(self, name, it, body):
        return "for current in sequence(&" + self.expr(it) + ")?{" + self.bind(name, "current", True) + body + "}"

    def method(self, name, r, aa, kw):
        a = aa[0] if aa else "Value::Null"
        b = aa[1] if len(aa) > 1 else "Value::Null"
        if name == "get":
            return "get(&" + r + ",&" + a + ", " + b + ")"
        if name in ("is_file", "exists", "is_dir"):
            return "json!(" + pth(r) + "." + name + "())"
        if name == "as_posix":
            return "json!(" + txt(r) + ".replace('\\\\',\"/\"))"
        if name == "read_text":
            return "json!(std::fs::read_to_string(" + pth(r) + ")?)"
        if name == "write_text":
            return "{std::fs::write(" + pth(r) + "," + txt(a) + ")?;Value::Null}"
        if name == "mkdir":
            return "{std::fs::create_dir_all(" + pth(r) + ")?;Value::Null}"
        if name == "resolve":
            return "json!(crate::io::resolve(&" + pth(r) + ")?)"
        if name == "relative_to":
            return "json!(" + pth(r) + ".strip_prefix(" + pth(a) + ")?)"
        if name in ["to_dict", "as_dict", "as_report", "to_report"]:
            return r
        if name in ["items", "values", "keys"]:
            return "members(&" + r + "," + rs(name) + ")?"
        if name == "join":
            return "json!(strings(&" + a + ")?.join(&" + txt(r) + "))"
        if name in ["lower", "upper", "strip", "rstrip", "splitlines", "isdigit", "bit_length", "isoformat", "date"]:
            return "unary_method(&" + r + "," + rs(name) + ",&" + a + ")?"
        if name in [
            "startswith",
            "endswith",
            "split",
            "replace",
            "removesuffix",
            "removeprefix",
            "count",
            "intersection",
            "issubset",
            "glob",
            "group",
            "match",
            "search",
        ]:
            return "method(&" + r + "," + rs(name) + ",&" + a + ",&" + b + ")?"
        raise ValueError("method " + name)

    def call(self, n):
        name = ast.unparse(n.func)
        e = self.expr
        if name == "isinstance":
            return "json!(" + self.cond(n) + ")"
        if name in ("min", "max") and any(k.arg == "key" for k in n.keywords):
            key = next(k.value for k in n.keywords if k.arg == "key")
            self.locals.add(key.args.args[0].arg)
            return (
                "extrema(&"
                + e(n.args[0])
                + ",|"
                + var(key.args.args[0].arg)
                + ":&Value|->Result<Value>{Ok("
                + e(key.body)
                + ")},"
                + str(name == "max").lower()
                + ")?"
            )
        if name == "sorted":
            aa = e(n.args[0])
            key = next((x.value for x in n.keywords if x.arg == "key"), None)
            if isinstance(key, ast.Lambda):
                pname = var(key.args.args[0].arg)
                self.locals.add(key.args.args[0].arg)
                fun = "|" + pname + ":&Value|->Result<Value>{Ok(" + e(key.body) + ")}"
            elif isinstance(key, ast.Name) and key.id in self.gl and inspect.isfunction(self.gl[key.id]):
                fun = "|v:&Value|" + ident(self.gl[key.id]) + "(v.clone())"
            elif key is not None:
                raise ValueError(name + " key " + ast.unparse(key))
            else:
                fun = "|v:&Value|Ok(v.clone())"
            return (
                "sorted(&"
                + aa
                + ","
                + fun
                + ","
                + ("true" if any(k.arg == "reverse" and k.value.value for k in n.keywords) else "false")
                + ")?"
            )
        if name == "date.today":
            return "json!(values::today())"
        if name in (
            "datetime.now(UTC).replace(microsecond=0).isoformat().replace",
            "datetime.now(UTC).isoformat",
            "datetime.now().isoformat",
            "datetime.now(UTC).date",
            "datetime.now",
        ):
            return "json!(now())"
        if name == "PerformanceBudgetInput.from_dict":
            return "values::budget_input(&" + e(n.args[0]) + ")?"
        if name == "hashlib.sha256(content.encode('utf-8')).hexdigest":
            return "json!(hex::encode(<sha2::Sha256 as sha2::Digest>::digest(values::text(&content).as_bytes())))"
        if name == "dict.fromkeys":
            return "fromkeys(&" + e(n.args[0]) + ")?"
        if name == "json.dumps":
            pretty = any(k.arg == "indent" for k in n.keywords)
            return "json!(serde_json::" + ("to_string_pretty" if pretty else "to_string") + "(&" + e(n.args[0]) + ")?)"
        if name == "json.loads":
            return "serde_json::from_str::<Value>(&" + txt(e(n.args[0])) + ")?"
        if name == "re.findall":
            return "regex_findall(&" + e(n.args[0]) + ",&" + e(n.args[1]) + ")?"
        if name == "re.escape":
            return "json!(regex::escape(&" + txt(e(n.args[0])) + "))"
        if name in ("re.search", "re.compile", "uuid.uuid5", "datetime.strptime", "datetime.fromisoformat"):
            return "special(" + rs(name) + ",&[" + ",".join(e(v) for v in n.args) + "])?"
        args = [e(a) for a in n.args]
        kw = {k.arg: e(k.value) for k in n.keywords}
        if name == "reversed":
            return "{let mut values=sequence(&" + args[0] + ")?;values.reverse();Value::Array(values)}"
        if isinstance(n.func, ast.Attribute):
            fn_name = type_methods.get((self.f.__module__, n.func.attr, ast.unparse(n.func.value))) or type_methods.get(
                (self.f.__module__, n.func.attr, "*")
            )
            if fn_name:
                args = [e(n.func.value), *args]
                fn = fn_name
                return ident(fn) + "(" + ",".join(args_for(fn, args, kw)) + ")?"
            if (
                n.func.attr in ("items", "keys", "values")
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id in self.gl
                and isinstance(self.gl[n.func.value.id], dict)
            ):
                keys = list(self.gl[n.func.value.id])
                return (
                    "ordered_members(&"
                    + e(n.func.value)
                    + ","
                    + rs(n.func.attr)
                    + ",&["
                    + ",".join(rs(k) for k in keys)
                    + "])?"
                )
        if name == "ceil":
            return "json!(number(&" + args[0] + ")?.ceil() as i64)"
        if name == "deepcopy":
            return args[0]
        if name.endswith(".pop"):
            return (
                self.mut(n.func.value).replace("&mut ", "", 1)
                + '.as_object_mut().context("expected object")?.remove(&'
                + txt(args[0])
                + ').context("missing field")?'
            )
        if name in ("min", "max") and "default" in kw:
            return (
                "{let source="
                + args[0]
                + ";if truth(&source){builtin("
                + rs(name)
                + ",&[source])?}else{"
                + kw["default"]
                + "}}"
            )
        if isinstance(n.func, ast.Name):
            fn = self.gl.get(name)
            if inspect.isclass(fn) and dataclasses.is_dataclass(fn):
                if issubclass(fn, Exception):
                    raise ValueError(name)
                bound = inspect.signature(fn).bind(*args, **kw)
                return (
                    "Value::Object(["
                    + ",".join(
                        "("
                        + rs(k)
                        + ".into(),"
                        + (
                            bound.arguments[k]
                            if k in bound.arguments
                            else const(v.default)
                            if v.default is not dataclasses._HAS_DEFAULT_FACTORY
                            else "json!([])"
                        )
                        + ")"
                        for k, v in inspect.signature(fn).parameters.items()
                    )
                    + "].into_iter().collect())"
                )
            if inspect.isfunction(fn) and fn in funcs:
                params = list(inspect.signature(fn).parameters)
                bound = args_for(fn, args, kw)
                for i, p in enumerate(params):
                    if is_ref(fn, p):
                        bound[i] = self.mut(n.args[i])
                return ident(fn) + "(" + ",".join(bound) + ")?"
            if len(args) == 1 and name in ("str", "bool", "int", "float"):
                op = {"str": "values::text", "bool": "truth", "int": "integer", "float": "number"}[name]
                return "json!(" + op + "(&" + args[0] + ")" + ("?" if name in ("int", "float") else "") + ")"
            if name == "Path" and len(args) == 1:
                return args[0]
            if name in [
                "str",
                "len",
                "dict",
                "list",
                "bool",
                "set",
                "int",
                "float",
                "sum",
                "min",
                "max",
                "any",
                "all",
                "next",
                "iter",
                "enumerate",
                "Path",
                "range",
                "round",
                "tuple",
            ]:
                return "builtin(" + rs(name) + ",&[" + ",".join(args) + "])?"
            if name in self.locals:
                return "invoke(&" + var(name) + ",&[" + ",".join(args) + "])?"
            raise ValueError("call " + name)
        if isinstance(n.func, ast.Attribute):
            if name == "spec.builder":
                return (
                    'invoke(&attr(&spec,"builder"),&[' + ",".join([*args, kw["report_id"], kw["source_refs"]]) + "])?"
                )
            return self.method(n.func.attr, e(n.func.value), args, kw)
        raise ValueError("call " + name)

    def stmts(self, ls):
        return "\n".join(self.stmt(x) for x in ls)

    def stmt(self, n):
        e = self.expr
        if isinstance(n, ast.Expr):
            v = n.value
            if isinstance(v, ast.Constant):
                return ""
            if (
                isinstance(v, ast.Call)
                and isinstance(v.func, ast.Attribute)
                and v.func.attr in ["append", "extend", "add", "update", "setdefault"]
            ):
                # Evaluate incoming data before borrowing the target.
                arg = e(v.args[0])
                if v.func.attr == "setdefault":
                    return "default_mut(" + self.mut(v.func.value) + ",&" + arg + "," + e(v.args[1]) + ")?;"
                return (
                    "{let incoming="
                    + arg
                    + "; edit("
                    + self.mut(v.func.value)
                    + ","
                    + rs(v.func.attr)
                    + ",incoming)?;}"
                )
            return e(v) + ";"
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            if n.value is None:
                return ""
            return self.bind(n.targets[0] if isinstance(n, ast.Assign) else n.target, e(n.value))
        if isinstance(n, ast.AugAssign):
            b = ast.BinOp(n.target, n.op, n.value)
            return self.bind(n.target, e(b))
        if isinstance(n, ast.If):
            return (
                "if "
                + self.cond(n.test)
                + "{"
                + self.stmts(n.body)
                + "}"
                + ("else{" + self.stmts(n.orelse) + "}" if n.orelse else "")
            )
        if isinstance(n, ast.While):
            return "while " + self.cond(n.test) + "{" + self.stmts(n.body) + "}"
        if isinstance(n, ast.For):
            if (
                isinstance(n.target, ast.Name)
                and isinstance(n.iter, ast.Name)
                and any(
                    isinstance(q, ast.Subscript)
                    and isinstance(q.ctx, ast.Store)
                    and ast.unparse(q.value) == n.target.id
                    for s in n.body
                    for q in ast.walk(s)
                )
            ):
                return (
                    "for (i,current) in sequence(&"
                    + e(n.iter)
                    + ")?.into_iter().enumerate(){let mut "
                    + var(n.target.id)
                    + "=current;"
                    + self.stmts(n.body)
                    + "set_index(&mut "
                    + var(n.iter.id)
                    + ",&json!(i),"
                    + var(n.target.id)
                    + ")?;}"
                )
            return self.forloop(n.target, n.iter, self.stmts(n.body))
        if isinstance(n, ast.Return):
            return "return Ok(" + (e(n.value) if n.value else "Value::Null") + ");"
        if isinstance(n, ast.Continue):
            return "continue;"
        if isinstance(n, ast.Break):
            return "break;"
        if isinstance(n, ast.ImportFrom):
            return ""
        if isinstance(n, ast.Raise):
            err = n.exc
            if not isinstance(err, ast.Call):
                raise ValueError("except rethrow")
            nm = ast.unparse(err.func)
            prefix = {
                "WorkflowError": "HATE-E-WORKFLOW",
                "ProductError": "HATE-E-PRODUCT",
                "ReleaseError": "HATE-E-RELEASE",
                "ExpansionRunError": "HATE-E-EXPANSION",
                "GapClosureError": "HATE-E-GAP",
                "ProductGradeError": "HATE-E-PRODUCT-GRADE",
            }.get(nm, "HATE-E-CLI")
            code = next((str(k.value.value) for k in err.keywords if k.arg == "exit_code"), "2")
            report = next((k.value for k in err.keywords if k.arg in ["report", "pack"]), None)
            diag = e(report) + ".to_string()" if report else 'format!("' + prefix + ': {}",' + txt(e(err.args[0])) + ")"
            return f"return Err(failure({code},{diag}));"
        raise ValueError("stmt " + type(n).__name__)

    def emit(self):
        p = self.parameters
        # Variables shadowed within loops and comprehensions stay local to their iteration.
        assigned = {
            n.id
            for s in ast.walk(self.n)
            if isinstance(s, (ast.Assign, ast.AnnAssign, ast.AugAssign))
            for v in (s.targets if isinstance(s, ast.Assign) else [s.target])
            for n in ast.walk(v)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        pre = "\n".join("let mut " + var(s) + ":Value;" for s in sorted(assigned - set(p)))
        body = self.stmts(self.n.body)
        return (
            "pub(super) fn "
            + ident(self.f)
            + "("
            + ",".join(
                ("" if v in self.ref_vars else "mut ") + var(v) + (": &mut Value" if v in self.ref_vars else ": Value")
                for v in p
            )
            + ")->Result<Value>{"
            + pre
            + "\n"
            + body
            + "\n"
            + ("Ok(Value::Null)" if not isinstance(self.n.body[-1], ast.Return) else "")
            + "}\n"
        )
