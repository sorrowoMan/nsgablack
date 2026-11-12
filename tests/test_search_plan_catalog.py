"""Internal plan wrappers name a registered base without registering all subclasses."""
from __future__ import annotations

from abc import ABC
from pathlib import Path
from types import SimpleNamespace

import pytest

from nsgablack.adapters import PoolTaskAdapter
from nsgablack.adapters.search_plan import _PlanPoolTaskAdapter
from nsgablack.project.doctor_core.model import add_diagnostic
from nsgablack.project.doctor_core.rules.component_catalog import (
    check_component_catalog_registration,
)


class PublicComponent:
    pass


class OtherRegisteredComponent:
    pass


class VirtualRegisteredOwner(ABC):
    pass


def framework_type(name, bases=(PublicComponent,), **attributes):
    return type(name, bases, {"__module__": "nsgablack.adapters._catalog_test", **attributes})


def registration_diagnostics(component_class, *, paths=None, instance=None, strict=True):
    if instance is None:
        instance = object.__new__(component_class)
    if paths is None:
        paths = [f"{__name__}:PublicComponent", f"{__name__}:OtherRegisteredComponent"]
    entries = [SimpleNamespace(import_path=path) for path in paths]
    diagnostics = []
    check_component_catalog_registration(root=Path("."),
        solver=SimpleNamespace(adapter=instance), build_file=Path("build_solver.py"),
        diags=diagnostics, strict=strict, add=add_diagnostic,
        get_catalog_entries=lambda: entries, load_project_entries=lambda root: ())
    return [row for row in diagnostics if row.code == "framework-component-not-in-catalog"]


def test_real_private_plan_wrapper_is_owned_by_public_pool_task_catalog_entry():
    assert _PlanPoolTaskAdapter.__dict__["catalog_owner_type"] is PoolTaskAdapter
    assert not registration_diagnostics(_PlanPoolTaskAdapter,
        paths=["nsgablack.adapters:PoolTaskAdapter"])


def test_plain_subclass_of_registered_type_still_requires_its_own_registration():
    assert registration_diagnostics(framework_type("Unmarked"))


def test_owned_wrapper_declaration_does_not_implicitly_register_its_descendants():
    owned = framework_type("Owned", catalog_owner_type=PublicComponent)
    assert not registration_diagnostics(owned)
    assert registration_diagnostics(framework_type("UnmarkedDescendant", bases=(owned,)))


def test_descendant_can_explicitly_name_the_registered_real_ancestor():
    middle = framework_type("Middle")
    owned = framework_type("ExplicitDescendant", bases=(middle,), catalog_owner_type=PublicComponent)
    assert not registration_diagnostics(owned)


@pytest.mark.parametrize("marker", [None, "PublicComponent", PublicComponent(),
    OtherRegisteredComponent, property(lambda instance: PublicComponent)])
def test_invalid_owner_markers_do_not_waive_registration(marker):
    assert registration_diagnostics(framework_type("InvalidOwner", catalog_owner_type=marker))


def test_catalog_owner_cannot_name_the_implementation_itself():
    component = framework_type("SelfOwner")
    component.catalog_owner_type = component
    assert registration_diagnostics(component)


def test_owner_requires_resolved_catalog_object_identity_not_a_matching_class_name():
    lookalike = type(PublicComponent.__name__, (), {"__module__": PublicComponent.__module__})
    component = framework_type("LookalikeOwner", bases=(lookalike,), catalog_owner_type=lookalike)
    assert registration_diagnostics(component)


def test_real_base_not_registered_in_catalog_is_not_a_valid_owner():
    component = framework_type("UnregisteredOwner", catalog_owner_type=PublicComponent)
    assert registration_diagnostics(component, paths=[f"{__name__}:OtherRegisteredComponent"])
    assert registration_diagnostics(component, paths=["missing.catalog.module:PublicComponent"])


def test_virtual_subclass_is_not_an_owned_implementation_base():
    component = framework_type("VirtualSubclass", bases=(), catalog_owner_type=VirtualRegisteredOwner)
    VirtualRegisteredOwner.register(component)
    assert issubclass(component, VirtualRegisteredOwner)
    assert registration_diagnostics(component, paths=[f"{__name__}:VirtualRegisteredOwner"])


def test_instance_marker_cannot_register_an_unmarked_concrete_class():
    component = framework_type("InstanceOnly")
    instance = component()
    instance.catalog_owner_type = PublicComponent
    assert registration_diagnostics(component, instance=instance)


def test_spoofed_instance_class_does_not_replace_its_actual_component_type():
    component = framework_type("SpoofedClass", __class__=property(lambda instance: PublicComponent))
    assert registration_diagnostics(component)


def test_missing_owner_keeps_existing_strict_and_non_strict_diagnostic_levels():
    component = framework_type("Unmarked")
    assert registration_diagnostics(component)[0].level == "error"
    assert registration_diagnostics(component, strict=False)[0].level == "warn"
