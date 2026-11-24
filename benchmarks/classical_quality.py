"""Independent pymoo algorithm baselines, with explicit common operators/budgets.

No claim of literature-level quality from this small diagnostic profile.
"""
from functools import partial
from pathlib import Path
import json
import numpy as np

from benchmarks.transparency_core import build_pair_solver
from benchmarks.transparency_population import specs, initial_population
from benchmarks.transparency_metrics import measure


def reference_run(algorithm, problem_name, seed, size, steps, checkpoint=None):
    from pymoo.core.crossover import Crossover
    from pymoo.core.mutation import Mutation
    from pymoo.core.population import Population
    from pymoo.problems import get_problem
    from pymoo.optimize import minimize
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.algorithms.moo.nsga3 import NSGA3
    from pymoo.algorithms.moo.moead import ParallelMOEAD
    from pymoo.decomposition.tchebicheff import Tchebicheff
    from pymoo.util.ref_dirs import get_reference_directions

    class Arithmetic(Crossover):
        def __init__(self): super().__init__(2,1,prob=1.)
        def _do(self,problem,x,random_state=None,**kwargs):
            alpha = random_state.random(x[0].shape)
            child = alpha*x[0]+(1-alpha)*x[1]
            use = random_state.random(len(child)) < .9
            return np.where(use[:,None],child,x[0])[None,:,:]

    class Gaussian(Mutation):
        def __init__(self): super().__init__(prob=1.)
        def _do(self,problem,x,random_state=None,**kwargs):
            return np.clip(x+random_state.normal(0.,.08,x.shape),0.,1.)

    class NoMutation(Mutation):
        def _do(self,problem,x,**kwargs): return x

    class Differential(Crossover):
        def __init__(self): super().__init__(4,1,prob=1.)
        def _do(self,problem,x,random_state=None,**kwargs):
            trial=x[1]+.5*(x[2]-x[3])
            mask=random_state.random(trial.shape)<.9
            mask[np.arange(len(mask)),random_state.integers(0,trial.shape[1],len(mask))]=True
            return np.clip(np.where(mask,trial,x[0]),0.,1.)[None,:,:]

    class BatchedMOEAD(ParallelMOEAD):
        # Only bind the current subproblem as DE target. Ideal-point updates
        # and replacement are owned by independent pymoo ParallelMOEAD.
        def _infill(self):
            indices=self.random_state.permutation(len(self.pop))
            parents=self.selection.do(self.problem,self.pop,len(indices),3,
                neighbors=self.neighbors[indices],random_state=self.random_state,to_pop=False)
            parents=self.pop[np.column_stack((indices,parents))]
            self.indices=indices
            return self.mating.do(self.problem,self.pop,len(indices),parents=parents,
                n_max_iterations=1,random_state=self.random_state)

    problem=get_problem(problem_name,n_var=8,**({"n_obj":3} if problem_name=="dtlz2" else {}))
    initial=initial_population(seed,size)
    common=dict(pop_size=size,sampling=initial,crossover=Arithmetic(),mutation=Gaussian(),
                eliminate_duplicates=False,n_offsprings=size)
    if algorithm=="nsga2":
        instance=NSGA2(**common)
        instance.tournament_type="comp_by_rank_and_crowding"
    elif algorithm=="nsga3":
        instance=NSGA3(ref_dirs=get_reference_directions("das-dennis",3,n_partitions=3),**common)
    else:
        refs=get_reference_directions("das-dennis",2,n_partitions=size-1)
        refs=np.clip(refs,1e-12,None)
        refs/=refs.sum(axis=1,keepdims=True)
        instance=BatchedMOEAD(ref_dirs=refs,n_neighbors=5,prob_neighbor_mating=1.,
            decomposition=Tchebicheff(),sampling=initial,crossover=Differential(),mutation=NoMutation(),n_offsprings=size)
    result=minimize(problem,instance,("n_eval",size*steps),seed=seed,verbose=False,
        **({"callback":lambda algorithm:checkpoint()} if checkpoint else {}))
    return result.pop.get("F"),int(result.algorithm.evaluator.n_eval)


def run(options, *, context, checkpoint, work_dir):
    size,steps=int(options.get("population_size",20)),int(options.get("steps",20))
    if size < 5 or steps < 2: raise ValueError("quality profile requires size>=5 and steps>=2")
    seeds=list(options.get("seeds",[11,29]))
    if not seeds: raise ValueError("quality profile requires seeds")
    registry={s.name:s for s in specs(population_size=size,steps=steps)}
    rows=[]
    for algorithm,problem in (("nsga2","zdt1"),("nsga3","dtlz2"),("moead","zdt1")):
        spec=registry[f"{algorithm}_{problem}"]
        for seed in seeds:
            solver,meter,trace,_=build_pair_solver(spec,seed,resource_context=context,
                runtime_checkpoint=checkpoint,capture_trace=False,record_calls=False)
            if algorithm=="moead":
                solver.adapter.cfg.delta=1.
                solver.adapter.cfg.nr=size
            solver.run(max_steps=steps)
            own_f=solver.adapter.get_population_snapshot()[1]
            own_v=solver.adapter.get_population_snapshot()[2]
            checkpoint()
            ref_f,calls=reference_run(algorithm,problem,seed,size,steps,checkpoint=checkpoint)
            if meter.call_count != size*steps or calls != size*steps:
                raise ValueError("independent algorithms did not use identical actual evaluation budgets")
            rows.append({"algorithm":algorithm,"problem":problem,"seed":seed,
                "population_size":size,"evaluations":meter.call_count,"reference_evaluations":calls,
                "framework":measure(problem,own_f,own_v),"independent_pymoo":measure(problem,ref_f,np.zeros(len(ref_f)))})
        Path(work_dir).mkdir(parents=True,exist_ok=True)
        (Path(work_dir)/"independent_quality_progress.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    return {"mode":"classical_quality","rows":rows,"validation":{"status":"passed"},
        "quality_status":"measured_not_literature_certified",
        "alignment":{"nsga2_nsga3":"common arithmetic crossover rate .9, Gaussian sigma .08, clipping, no duplicate removal; rank/crowding or CV/random mating respectively",
            "moead":"parallel full batch, common DE rand/1/bin F=.5 CR=.9, neighborhood5, delta1, unlimited replacements, same weights/initial population",
            "remaining_differences":"independent RNG draw order, tournament parent sampling/permutation and valid tie breaking differ; distribution comparison, not exact trajectory gate"},
        "limits":"two-seed low-budget diagnostic; not default SBX/PM recipes or a claim to match published best results"}
