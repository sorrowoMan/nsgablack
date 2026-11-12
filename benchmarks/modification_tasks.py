"""Controlled modification tasks, not a convergence or whole-runtime benchmark."""
from dataclasses import dataclass, field
from types import SimpleNamespace
import time
import numpy as np

from nsgablack.adapters import NSGA2Adapter
from nsgablack.units import PopulationUnit, UnitBinding, UnitSchema
from nsgablack.representation import PopulationUnitBuilder


@dataclass
class AgeUnit(PopulationUnit):
    age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("age",)
    schema = UnitSchema("benchmark.age", required_fields=(*PopulationUnit.schema.required_fields, "age"), candidate_projection=False)

    def on_members_changed(self, change):
        return {"age": np.asarray([0 if i is None else self.age[i] + int(change.operation == "selection")
                                   for i in change.previous_member_indices], dtype=int)}


class AgeBuilder(PopulationUnitBuilder):
    unit_type = AgeUnit
    compatible_schemas = (PopulationUnit.schema,)


def age_order(f, ages, count):
    """Older than two completed survivals loses eligibility priority; refill if needed."""
    return np.lexsort((np.arange(len(f)), f[:, 0], ages >= 2))[:count]


class AgeSelectingNSGA(NSGA2Adapter):
    # Explicitly counted extension: the ordinary SelectionRequest has no age field.
    def _select_survivors(self, candidates, objectives, violations, count, context, **kwargs):
        old = self.ensure_unit().age
        ages = np.concatenate((old, np.zeros(len(candidates)-len(old), dtype=int)))
        return age_order(objectives, ages, count)


def native_age(batches, use_age):
    cls = AgeSelectingNSGA if use_age else NSGA2Adapter
    adapter = cls(population_size=4, unit_binding=UnitBinding(AgeBuilder()))
    trace = []
    for batch in batches:
        identities = {id(x): f"c{int(x[0])}" for x in batch}
        control = SimpleNamespace(candidate_provenance_for=lambda x: SimpleNamespace(candidate_token=identities[id(x)]))
        adapter.update(control, batch, (np.asarray([[x[1], x[1]] for x in batch]), np.zeros(len(batch))), {})
        unit = adapter.algorithm_unit
        trace.append({"ids": list(unit.candidate_tokens), "age": unit.age.tolist()})
    return trace


def pymoo_age(batches, use_age, *, partial=False, reverse=False, restore_at=None):
    from pymoo.core.population import Population
    from pymoo.core.problem import Problem
    from pymoo.operators.survival.rank_and_crowding import RankAndCrowding

    class AgeSurvival(RankAndCrowding):
        def _do(self, problem, pop, n_survive, **kwargs):
            if use_age:
                selected = pop[age_order(pop.get("F"), pop.get("age"), n_survive)]
            else:
                selected = super()._do(problem, pop, n_survive=n_survive, **kwargs)
            if reverse: selected = selected[::-1]
            for item in selected:
                item.set("age", int(item.get("age")) + int(item.get("established")))
                item.set("established", True)
            return selected

    survival, problem, pop, trace = AgeSurvival(), Problem(n_var=2, n_obj=2), Population.empty(), []
    for batch_index, batch in enumerate(batches):
        if restore_at == batch_index:
            import pickle
            pop=pickle.loads(pickle.dumps(pop))
        if partial and batch_index: batch=[batch[i] for i in (1,3)]
        incoming = Population.new(X=np.asarray(batch), F=np.asarray([[x[1], x[1]] for x in batch]))
        for item in incoming:
            item.set("age", 0); item.set("established", False); item.set("identity", f"c{int(item.X[0])}")
        pop = survival.do(problem, Population.merge(pop, incoming), n_survive=4, random_state=np.random.default_rng(1))
        trace.append({"ids": pop.get("identity").tolist(), "age": pop.get("age").tolist()})
    return trace


def choose_age_pool(pool, *, members, ages, count):
    """Exact versions join Pool rows to this owner's member attributes."""
    if len(set(members)) != len(members):
        raise ValueError("this NSGA benchmark requires unique member references")
    lookup = dict(zip(members, ages, strict=True))
    offered_age = np.asarray([lookup.get(ref, 0) for ref in pool.refs])
    objectives, _ = pool.selection_feedback()
    return pool.take(age_order(objectives, offered_age, count))


def select_age_members(pool, *, count, reverse=False):
    chosen = pool.take(age_order(pool.objectives, pool.member_field("age", default=0), count))
    return chosen.take(range(len(chosen)-1, -1, -1)) if reverse else chosen


def pool_native_age(batches, use_age, *, context=None, checkpoint=lambda: None,
                    partial=False, reverse=False, restore_at=None, _payload=None, _start=0):
    """Real Solver evaluation and Pool selection; no Adapter overrides."""
    from nsgablack.core import BlackBoxProblem, ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    class Problem(BlackBoxProblem):
        def __init__(self): super().__init__(dimension=2, objectives=["min", "min"], bounds=[(-1000.,1000.)]*2)
        def evaluate(self, x): return [float(x[1])]*2
    class Stream:
        def __init__(self): self.position=0
        def next(self):
            values=[x for batch in batches for x in batch]
            x=values[self.position].copy(); self.position+=1
            return x
        def initialize(self, problem, context):
            from blackbase import UnknownState
            return UnknownState(self.next())
        def mutate(self, candidate, context): return self.next()
        def get_state(self): return {"position":self.position}
        def set_state(self, state): self.position=int(state["position"])
        def checkpoint_identity(self): return {"schema":"benchmark.fixed_candidate_stream/v1", "values":[x.tolist() for b in batches for x in b]}
    stream=Stream()
    initial=Stream()
    stream.position=len(batches[0])
    adapter=NSGA2Adapter(population_size=4, offspring_size=4, unit_binding=UnitBinding(AgeBuilder()))
    adapter.set_initializer(initial)
    solver=ComposableSolver(Problem(),adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=stream))
    if context is not None: solver.set_resource_context(context)
    if use_age:
        from functools import partial as bind_choice
        adapter.set_selector(bind_choice(select_age_members, reverse=reverse))
    if partial:
        from blackbase.contracts import BatchDisposition
        class Admission:
            def select(self, candidates, feedback, context):
                n=len(candidates.semantic_states)
                return BatchDisposition(n, tuple(range(n)) if adapter.algorithm_unit.objectives is None else (1,3))
        solver.set_evaluation_acceptance_policy(Admission())
    solver.set_random_seed(11)
    if _payload is not None:
        from nsgablack.plugins import CheckpointResumePlugin
        reader=CheckpointResumePlugin(); reader.attach(solver)
        solver.queue_restore_envelope(lambda: reader._restore_payload(solver=solver,payload=_payload))
    solver.setup()
    solver._apply_pending_restore_envelopes()
    trace=[]
    try:
        for index in range(_start,len(batches)):
            if restore_at == index:
                import pickle
                from nsgablack.plugins import CheckpointResumePlugin
                writer=CheckpointResumePlugin(); writer.attach(solver)
                payload=pickle.loads(pickle.dumps(writer._build_payload(solver=solver,reason="modification_task")))
                return trace+pool_native_age(batches,use_age,context=context,checkpoint=checkpoint,
                    partial=partial,reverse=reverse,_payload=payload,_start=index)
            checkpoint()
            assert solver.step().committed
            refs=adapter.get_population_solution_refs(solver)
            values=solver.read_solutions(refs).numeric_matrix
            unit=adapter.algorithm_unit
            np.testing.assert_array_equal(values,unit.population)
            trace.append({"ids":[f"c{int(x[0])}" for x in values],"age":unit.age.tolist()})
        assert solver.evaluation_count==sum(map(len,batches))
        return trace
    finally:
        solver.teardown()


def refiner_task(backend, kind, context, checkpoint):
    """Same user task; native algorithms differ, so no cross-backend quality claim."""
    if backend == "pymoo":
        from pymoo.algorithms.soo.nonconvex.pattern import PatternSearch
        from pymoo.algorithms.soo.nonconvex.nelder import NelderMead
        from pymoo.core.problem import Problem
        class Sphere(Problem):
            def __init__(self, weights):
                super().__init__(n_var=1, n_obj=1, xl=-10., xu=10.)
                self.weights=weights
            def _evaluate(self, x, out, **kwargs):
                raw=np.column_stack((x[:,0]**2,(x[:,0]-6.)**2))
                out["F"] = raw@self.weights
        outputs=[]; evaluations=0
        for weights in ([0.,1.],[1.,0.]):
            algorithm = (PatternSearch if kind == "pattern" else NelderMead)(x0=np.array([3.]))
            algorithm.setup(Sphere(np.asarray(weights)), termination=("n_eval", 30), seed=11)
            while algorithm.has_next():
                checkpoint(); algorithm.next()
            x=float(algorithm.result().X[0]); raw=[x*x,(x-6.)**2]
            assert np.isclose(float(algorithm.result().F[0]),np.dot(raw,weights))
            outputs.append({"x":x,"raw":raw,"weights":weights})
            evaluations+=int(algorithm.evaluator.n_eval)
        return {"algorithm": type(algorithm).__name__, "outputs":outputs,
                "evaluations": evaluations, "handoff": "two frozen weighted-sum Problems; result.X retains raw evaluation meaning"}
    from nsgablack.adapters import (MOEADAdapter, PatternSearchAdapter, SimulatedAnnealingAdapter,
        StrategyRouterAdapter, MultiStrategyConfig, RoleSpec, PoolTaskSpec, subpools)
    from nsgablack.core import BlackBoxProblem, ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    class Sphere(BlackBoxProblem):
        def __init__(self): super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-10.,10.)])
        def evaluate(self, x): return [float(x[0]**2),float((x[0]-6.)**2)]
    class Operator:
        def initialize(self, problem, context): return np.array([3.])
        def mutate(self, x, context): return x*.8
    source = MOEADAdapter(population_size=2, batch_size=2, neighborhood_size=2, decomposition="weighted_sum")
    local = PatternSearchAdapter(step_size=1.) if kind == "pattern" else SimulatedAnnealingAdapter(batch_size=2, random_seed=11)
    router = StrategyRouterAdapter(roles=[RoleSpec("source",source),RoleSpec("local",local,
        pool_task=PoolTaskSpec(subpools.all(source),steps=3,shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=8,adapt_weights=False,
            phase_policy=lambda ctx: "source" if ctx["step"]==0 else "refine",
            phase_roles={"source":["source"],"refine":["local"]}))
    operator=Operator()
    solver=ComposableSolver(Sphere(),adapter=router,representation_pipeline=RepresentationPipeline(initializer=operator,mutator=operator))
    solver.set_resource_context(context); solver.set_random_seed(11); solver.setup()
    try:
        task=router.units[1].adapter
        for _ in range(20):
            checkpoint()
            assert solver.step().committed
            if task.task_status.get("status")=="done":
                break
        assert task.task_status["status"]=="done"
        from nsgablack.adapters.subpools import adapter_path
        outputs=[]
        for name in solver.solution_pool.projection_subpools(adapter_path(solver.adapter,local)):
            refs=solver.solution_pool.subpool_refs(name)
            x=float(solver.read_solutions(refs).numeric_matrix[0,0])
            raw,_=solver.solution_pool.read_raw_feedback(refs)
            np.testing.assert_allclose(raw[0],[x*x,(x-6.)**2])
            outputs.append({"x":x,"raw":raw[0].tolist()})
        assert len(outputs)==2
        return {"algorithm":type(local).__name__,"evaluations":solver.evaluation_count,"outputs":outputs,
                "task_completed":True,"handoff":"same projected PoolTaskSpec for both refiners"}
    finally:
        solver.teardown()


def duplicate_slot_task():
    """Two occurrences of one candidate have independent member ages."""
    from blackbase.context import create_snapshot_store
    from blackbase.types import CandidateBatch
    from nsgablack.core.state.solution_pool import SolutionPool
    from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
    from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices
    from pymoo.core.population import Population
    control=SimpleNamespace(solution_pool=SolutionPool(create_snapshot_store(backend="memory"),run_id="slot-comparison"))
    refs=control.solution_pool.put(CandidateBatch.from_candidates([[1.],[2.]],candidate_tokens=("a","b")),
        stage="accepted",feedback=OptimizationFeedbackBatch.from_arrays([[1.,1.],[2.,2.]],[0.,0.]))
    ordered=(refs[0],refs[0],refs[1])
    unit=AgeUnit("slots")
    unit.initialize_population([[1.],[1.],[2.]],[[1.,1.],[1.,1.],[2.,2.]],[0.]*3,candidate_tokens=("a","a","b"))
    unit.age=np.array([1,5,2])
    with offered_pool(control,ordered,objectives=unit.objectives,violations=unit.violations,
                      unit=unit,member_rows=(0,1,2)) as pool:
        try: choose_age_pool(pool,members=ordered,ages=unit.age,count=2)
        except ValueError: ambiguous_join_rejected=True
        else: raise AssertionError("reference-only join must reject duplicate members")
        # Capture slot-aligned attributes BEFORE reordering; keep occurrence coordinates.
        selected=pool.chosen(lambda offered: offered.take(age_order(
            offered.objectives,offered.member_field("age", default=0),2)[::-1]))
        indices=pool_selection_indices(pool,selected)
        assert tuple(indices)==(1,0)
    unit.apply_selection(indices,np.empty((0,1)),np.empty((0,2)),np.empty(0),candidate_tokens=())
    pop=Population.new(X=np.array([[1.],[1.],[2.]]),F=np.array([[1.,1.],[1.,1.],[2.,2.]]))
    pop.set("age",[1,5,2]);pop.set("identity",["a","a","b"])
    selected=pop[age_order(pop.get("F"),pop.get("age"),2)[::-1]]
    selected.set("age",selected.get("age")+1)
    assert list(unit.candidate_tokens)==selected.get("identity").tolist()==["a","a"]
    assert unit.age.tolist()==selected.get("age").tolist()==[6,2]
    return {"reference_only_join_rejected":ambiguous_join_rejected,"indices":list(indices),
            "ids":list(unit.candidate_tokens),"ages":unit.age.tolist(),"equal":True,
            "scope":"slot-aligned Pool selection + Unit publication; not full MOEAD run"}


def run(options, *, context, checkpoint):
    import pymoo
    if pymoo.__version__ != "0.6.2": raise ValueError("requires pymoo 0.6.2")
    # Strictly ordered objectives avoid differences in crowding tie-breaks.
    batches = [[np.array([i, float(i)]) for i in range(4)]]
    for generation in range(1, 7):
        batches.append([np.array([generation*4+i, 10.+generation+i]) for i in range(4)])
    rows=[]
    for use_age in (False,True):
        results={}
        for name, function in (("nsgablack",native_age),("pymoo",pymoo_age)):
            timings=[]
            for _ in range(7):
                checkpoint(); start=time.perf_counter(); trace=function(batches,use_age)
                timings.append(time.perf_counter()-start)
            results[name]={"trace":trace,"median_seconds":float(np.median(timings[1:])),"samples_seconds":timings[1:]}
        if results["nsgablack"]["trace"] != results["pymoo"]["trace"]:
            raise AssertionError(results)
        rows.append({"task":"age_selection" if use_age else "age_state", "equal":True,"results":results})
    refiners=[]
    pool_rows=[]
    for use_age in (False,True):
        actual=pool_native_age(batches,use_age,context=context,checkpoint=checkpoint)
        expected=pymoo_age(batches,use_age)
        if actual != expected: raise AssertionError({"pool":actual,"pymoo":expected})
        pool_rows.append({"task":"age_selection" if use_age else "age_state", "equal":True,
                          "trace":actual,"evaluations":sum(map(len,batches)),"adapter_overridden":False})
    for name, settings in (("reorder",{"reverse":True}), ("partial",{"partial":True}),
                           ("reorder_partial_restore",{"reverse":True,"partial":True,"restore_at":3})):
        actual=pool_native_age(batches,True,context=context,checkpoint=checkpoint,**settings)
        expected=pymoo_age(batches,True,**settings)
        if actual != expected: raise AssertionError({"task":name,"pool":actual,"pymoo":expected})
        pool_rows.append({"task":name,"equal":True,"trace":actual,"adapter_overridden":False})
    for backend in ("nsgablack","pymoo"):
        for kind in ("pattern","alternative"):
            checkpoint(); refiners.append({"backend":backend,"variant":kind,**refiner_task(backend,kind,context,checkpoint)})
    return {"mode":"modification_tasks","rows":rows,"pool_rows":pool_rows,"refiners":refiners,
        "duplicate_slots":duplicate_slot_task(),
        "validation":{"status":"passed","failures":[]},
        "limits":["Age tasks exercise native environmental update components, not full solver runtime.",
            "Refiner task compares extension surfaces, NOT quality/speed: native alternatives and budgets differ.",
            "Learning time requires a human study; source size is not learning time."]}
