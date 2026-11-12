"""Publish exact original source bytes; do not evaluate or adjust inventory."""
from pathlib import Path
import hashlib

from blackbase.resources import coerce_resource_context
from cases.supply_adjustment_nested.runtime.production_scheduling_bridge import load_production_case_data


class ProductionSourcesCase:
    def __init__(self, *, resource_context=None, bom=None, supply=None, machines=22,
                 materials=157, days=31, production_case_dir=None):
        self.resource_context = coerce_resource_context(resource_context)
        self.options = dict(bom_path=bom, supply_path=supply, machines=machines,
                            materials=materials, days=days, production_case_dir=production_case_dir)
        self.case_runtime = None

    def set_resource_context(self, context):
        self.resource_context = coerce_resource_context(context)
        return self

    def get_resource_context(self):
        return self.resource_context

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        return self

    def run(self):
        if self.case_runtime is None:
            raise RuntimeError("production source publication requires a formal Case runtime")
        self.case_runtime.checkpoint()
        data = load_production_case_data(**self.options)
        sources, refs = {}, {}
        for name, path in (("bom", data.bom_path), ("supply", data.supply_path)):
            path = Path(path)
            if path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
                raise ValueError("production source publication requires a supported source file suffix")
            content = path.read_bytes()
            refs[name] = self.case_runtime.publish_artifact(name, content, serializer="bytes",
                kind="production-source", metadata={"source_sha256": hashlib.sha256(content).hexdigest(),
                                                   "source_suffix": path.suffix.lower()})
            sources[name] = {"sha256": hashlib.sha256(content).hexdigest(), "suffix": path.suffix.lower()}
        return {"schema": "supply_adjustment_nested.source_publication/v1", "source": sources,
                "artifact_refs": refs, "evaluations": 0}
