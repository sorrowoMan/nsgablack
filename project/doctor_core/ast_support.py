"""Local reference tracking for Doctor; not interprocedural type inference."""
import ast


def mark_references(tree: ast.AST) -> None:
    """Track straight-line aliases and rebinding separately in each lexical scope."""
    class References(ast.NodeVisitor):
        def __init__(self):
            self.names = {"solver": "solver", **{name: "context" for name in
                          ("context", "ctx", "context_store", "ctx_store")}}

        def kind(self, node):
            if isinstance(node, ast.Name):
                return self.names.get(node.id)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
                if node.attr == "solver":
                    return "solver"
                if node.attr in {"context", "ctx", "context_store"}:
                    return "context"
            return None

        def visit(self, node):
            if isinstance(node, ast.expr):
                node._doctor_solver_ref = self.kind(node) == "solver"
                node._doctor_context_ref = self.kind(node) == "context"
            return super().visit(node)

        def visit_FunctionDef(self, node):
            previous = self.names
            self.names = dict(previous)
            args = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            for arg in args:
                self.names.pop(arg.arg, None)
                if arg.arg == "solver":
                    self.names[arg.arg] = "solver"
                elif arg.arg in {"context", "ctx", "context_store", "ctx_store"}:
                    self.names[arg.arg] = "context"
            # Local assignment shadows an outer alias throughout the function.
            for stmt in node.body:
                for target in ast.walk(stmt):
                    if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
                        self.names.pop(target.id, None)
            for stmt in node.body:
                self.visit(stmt)
            self.names = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            previous = self.names
            self.names = dict(previous)
            for stmt in node.body:
                self.visit(stmt)
            self.names = previous

        def visit_Assign(self, node):
            kind = self.kind(node.value)
            self.generic_visit(node)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.names.pop(target.id, None)
                    assigned_kind = kind or ("solver" if target.id == "solver" else
                                              "context" if target.id in {"context", "ctx", "context_store", "ctx_store"} else None)
                    if assigned_kind:
                        self.names[target.id] = assigned_kind

        def visit_AnnAssign(self, node):
            kind = self.kind(node.value)
            self.generic_visit(node)
            if isinstance(node.target, ast.Name) and node.value is not None:
                self.names.pop(node.target.id, None)
                assigned_kind = kind or ("solver" if node.target.id == "solver" else
                                          "context" if node.target.id in {"context", "ctx", "context_store", "ctx_store"} else None)
                if assigned_kind:
                    self.names[node.target.id] = assigned_kind

        def visit_If(self, node):
            self.visit(node.test)
            before = dict(self.names)
            for stmt in node.body:
                self.visit(stmt)
            yes = dict(self.names)
            self.names = dict(before)
            for stmt in node.orelse:
                self.visit(stmt)
            # Only definite aliases survive both branches.
            self.names = {k: v for k, v in yes.items() if self.names.get(k) == v}

    References().visit(tree)
