"""正式导入 Case 的唯一装配入口，不启动优化器。"""
from .solver.case import SupplyPlanImportCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("supply_plan_import accepts explicit component_overrides only")
    options = dict(component_overrides or {})
    required = {"old_authority", "old_binding"}
    if not required.issubset(options) or set(options).difference(required | {"production_case_dir"}):
        raise ValueError("supply_plan_import requires old_authority and old_binding")
    return SupplyPlanImportCase(resource_context=resource_context, **options)
