"""One read-only contract validator consumed by runtime assembly and Doctor."""
from blackbase.runtime import (
    AuthorityRegistry, FinalizationHooks, capture_runtime_snapshot, runtime_participants,
)
from blackbase.representation import representation_capabilities
from blackbase.plugin import PluginManager
from blackbase.preferences import PreferenceProvider


def inspect_runtime_contracts(solver):
    from ..adapters.algorithm_adapter import AlgorithmAdapter
    from ..adapters.multi_strategy import StrategyRouterAdapter
    from ..units.features import UnitFeature, FeatureUnit
    from ..units.operator_inputs import mutation_unit_spec
    issues = []
    pipeline = solver.representation_pipeline
    operators = [("default", getattr(pipeline, "mutator", None)),
                 *getattr(pipeline, "mutation_operators", {}).items()]
    for label, operator in operators:
        try:
            mutation_unit_spec(operator)
        except (TypeError, ValueError) as exc:
            issues.append(("unit-operator-contract-invalid", f"{label}: {exc}"))
    try:
        representation_capabilities(solver.representation_pipeline)
    except (TypeError, ValueError) as exc:
        issues.append(("representation-capabilities-invalid", str(exc)))
    if not isinstance(solver.finalization_hooks, FinalizationHooks):
        issues.append(("finalization-contract-invalid", "finalization_hooks must be FinalizationHooks"))
    if not isinstance(solver.authorities, AuthorityRegistry):
        issues.append(("authority-registry-invalid", "Solver requires AuthorityRegistry"))
    else:
        for registration in solver.authorities.registrations():
            try:
                registration.validate()
            except (TypeError, ValueError) as exc:
                issues.append(("authority-rollback-contract-invalid", f"{registration.fact}: {exc}"))
        for fact, expected in (("population", solver.population_authority),
                               ("candidates", solver.solution_pool),
                               ("progress", solver.run_session), ("result", solver.run_session)):
            try:
                if solver.authorities.owner(fact) is not expected:
                    issues.append(("authority-owner-conflict", f"{fact} has a different owner"))
            except KeyError:
                issues.append(("authority-owner-missing", f"{fact} has no registered owner"))
    from ..core.state.solution_pool import SolutionPool
    pool = solver.solution_pool
    if not isinstance(pool, SolutionPool) or pool.snapshots is not solver.snapshot_store:
        issues.append(("solution-pool-store-invalid", "SolutionPool must use the Solver SnapshotStore"))
    if not any(item is pool for item in solver._state_participants):
        issues.append(("solution-pool-participant-missing", "SolutionPool must participate in step rollback"))
    if isinstance(pool, SolutionPool) and pool.retention_policy is not None:
        from ..core.state.pool_retention import PoolRetentionPolicy
        try:
            if not isinstance(pool.retention_policy, PoolRetentionPolicy):
                raise TypeError("retention requires PoolRetentionPolicy")
            for refs in solver.solution_pool_retention_roots().values():
                for ref in refs:
                    pool._record(ref, allow_pending=True)
        except (TypeError, ValueError, AttributeError) as exc:
            issues.append(("solution-pool-retention-contract-invalid", str(exc)))
    participants = list(solver._state_participants)
    if getattr(solver, "adapter", None) is not None:
        participants.append(solver.adapter)
    seen = set()
    for participant in participants:
        name = str(getattr(participant, "name", ""))
        if not name or name in seen:
            issues.append(("runtime-participant-name-conflict", f"duplicate or empty participant name: {name}"))
        seen.add(name)
    try:
        resolved = runtime_participants(participants)
    except (TypeError, ValueError) as exc:
        issues.append(("runtime-participant-invalid", str(exc)))
    else:
        from ..core.joint_repair import inspect_joint_repair_contracts
        issues.extend(inspect_joint_repair_contracts(solver, resolved))
        for participant in resolved:
            if isinstance(participant, AlgorithmAdapter):
                from ..adapters.pool_tasks import PoolTaskAdapter
                if isinstance(participant, PoolTaskAdapter):
                    try:
                        participant.validate_pool_task(solver.adapter)
                    except (TypeError, ValueError) as exc:
                        issues.append(("solution-pool-task-contract-invalid", f"{participant.name}: {exc}"))
                modes = participant.pool_input_modes
                if not isinstance(modes, tuple) or any(mode not in {"initialize", "compete"} for mode in modes):
                    issues.append(("solution-pool-input-contract-invalid", f"{participant.name}: unknown input modes"))
                if participant.supports_pool_restart and type(participant).restart_search is AlgorithmAdapter.restart_search:
                    issues.append(("solution-pool-input-contract-invalid", f"{participant.name}: restart is declared but not implemented"))
                for flag in ("supports_pool_restart", "supports_objective_projection",
                             "publishes_projection_subpools", "publishes_subpools"):
                    if type(getattr(participant, flag)) is not bool:
                        issues.append(("solution-pool-input-contract-invalid", f"{participant.name}: {flag} must be boolean"))
                results = participant.get_pool_refinement_results
                if results is not None and not callable(results):
                    issues.append(("solution-pool-result-contract-invalid", f"{participant.name}: result delivery must be callable or None"))
                if participant.supports_objective_projection and (
                        "initialize" not in modes or not participant.supports_pool_restart):
                    issues.append(("solution-pool-input-contract-invalid", f"{participant.name}: projected refinement requires initialize and restart"))
                try:
                    delivery = participant.supports_population_state_delivery()
                    if type(delivery) is not bool:
                        raise TypeError("population state capability must return boolean")
                    if delivery and type(participant).get_population_solution_refs is AlgorithmAdapter.get_population_solution_refs:
                        raise ValueError("population identity delivery requires its ordered member-reference reader")
                except (TypeError, ValueError, AttributeError) as exc:
                    issues.append(("population-identity-contract-invalid", f"{participant.name}: {exc}"))
                try:
                    if participant.mutation_operator is not None and not participant.uses_pipeline_mutation:
                        raise ValueError("Adapter does not consume pipeline mutation")
                    if participant.uses_pipeline_mutation:
                        mutator = participant.get_mutation_operator(solver)
                        if mutator is None and getattr(pipeline, "mutation_operators", {}):
                            raise ValueError("pipeline has named mutations but consumer selected no default or name")
                        mutation_spec = mutation_unit_spec(mutator)
                        unit = participant.get_operator_unit()
                        if mutation_spec is not None and unit is not None:
                            mutation_spec.validate_for(unit)
                except (TypeError, ValueError) as exc:
                    issues.append(("unit-operator-contract-invalid", f"{participant.name}: {exc}"))
            declarations = getattr(participant, "unit_features", ())
            try:
                names = set()
                for spec in declarations:
                    unit = getattr(participant, "algorithm_unit", None)
                    if not isinstance(spec, UnitFeature) or not isinstance(unit, FeatureUnit):
                        raise TypeError("Unit features require a UnitFeature and a FeatureUnit owner")
                    if spec.name in names:
                        raise ValueError(f"duplicate Unit feature: {spec.name}")
                    names.add(spec.name)
                    spec.validate_for(unit)
            except (TypeError, ValueError) as exc:
                issues.append(("unit-feature-contract-invalid", f"{participant.name}: {exc}"))
            if isinstance(participant, StrategyRouterAdapter):
                try:
                    participant.validate_composition_contract()
                except (TypeError, ValueError, KeyError) as exc:
                    issues.append(("strategy-task-contract-invalid", f"{participant.name}: {exc}"))
            if isinstance(participant, AlgorithmAdapter) and not callable(
                getattr(participant, "on_proposal_repair", None)
            ):
                issues.append(("adapter-repair-hook-invalid", f"{participant.name}: on_proposal_repair must be callable"))
            try:
                capture_runtime_snapshot(participant)
            except Exception as exc:
                issues.append(("runtime-participant-snapshot-invalid", f"{participant.name}: {type(exc).__name__}: {exc}"))
    for plugin in solver.plugin_manager.plugins:
        try:
            PluginManager.validate_participation(plugin)
        except TypeError as exc:
            issues.append(("plugin-participation-invalid", f"{plugin.name}: {exc}"))
    bias = solver.bias_module
    validate_bias = getattr(bias, "validate_contract", None)
    if callable(validate_bias):
        try:
            validate_bias()
        except (TypeError, ValueError) as exc:
            issues.append(("bias-unit-preference-contract-invalid", str(exc)))
    if isinstance(bias, PreferenceProvider):
        keys = tuple(bias.preference_keys)
        if not keys or len(keys) != len(set(keys)):
            issues.append(("bias-preference-contract-invalid", "preference_keys must be nonempty and unique"))
        for key in keys:
            prefix, separator, index = str(key).partition(".")
            if prefix != "objectives" or not separator or not index.isdecimal():
                issues.append(("bias-preference-contract-invalid", f"unsupported preference key: {key}"))
    return tuple(issues)


def validate_runtime_contracts(solver):
    issues = inspect_runtime_contracts(solver)
    if issues:
        raise TypeError("; ".join(f"{code}: {message}" for code, message in issues))
