"""Analyze cloud-verified evidence copies; original Artifact identities remain cloud-scoped."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def nondominated(values):
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
    values=np.unique(np.asarray(values,dtype=float),axis=0)
    return values[NonDominatedSorting().do(values,only_non_dominated_front=True)]


def load_verified(folder):
    state=json.loads((folder/"run.json").read_text(encoding="utf-8"))
    if (state.get("status")!="succeeded" or len(state["runs"])!=len(state["jobs"])
            or len({r["group"] for r in state["runs"]})!=len(state["jobs"])
            or {r["group"] for r in state["runs"]}!={j["group"] for j in state["jobs"]}):
        raise ValueError("budget study is incomplete")
    result=[]
    for record in state["runs"]:
        path=folder/record["group"]/"verified_observations.npz"
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record["verified_arrays_sha256"]:
            raise ValueError("downloaded evidence differs from cloud verification receipt")
        with np.load(path,allow_pickle=False) as data:
            arrays={k:data[k].copy() for k in data.files}
        n=len(arrays["raw_violations"])
        if (record["status"]!="succeeded" or n!=record["budget"]
                or record["formal"]["evaluations"]!=n
                or record["formal"]["resource_binding_current"] is not True
                or record["formal"]["threads"]!=1 or record["formal"]["gpus"]!=0
                or arrays["raw_objectives"].shape!=(n,4)
                or arrays["batch_counts"].sum()!=n or arrays["cumulative_evaluations"][-1]!=n
                or record["metadata"]["initial_count"]!=48):
            raise ValueError("budget/initialization/resource evidence does not reconcile")
        if any(not np.isfinite(arrays[k]).all() for k in ("raw_objectives","raw_violations","delivered_raw_objectives")):
            raise ValueError("nonfinite raw evidence")
        result.append({"record":record,"arrays":arrays})
    return state,result


def summarize(entries):
    from pymoo.indicators.hv import HV
    from pymoo.indicators.igd import IGD
    by_seed={}
    for e in entries:by_seed.setdefault(e["record"]["seed"],[]).append(e)
    for seed,rows in by_seed.items():
        baseline=rows[0]["arrays"]
        for row in rows:
            for key in ("numeric_hashes","raw_objectives","raw_violations"):
                if not np.array_equal(row["arrays"][key][:48],baseline[key][:48]):
                    raise ValueError(f"initial candidate/raw feedback differs for seed={seed}")
    feasible=[e["arrays"]["raw_objectives"][e["arrays"]["raw_violations"]<=1e-9] for e in entries]
    if any(not len(f) for f in feasible):raise ValueError("no feasible raw observations")
    union=np.vstack(feasible);low,high=union.min(axis=0),union.max(axis=0)
    scale=np.where(high>low,high-low,1.)
    reference=nondominated((union-low)/scale)
    hv,igd=HV(ref_point=np.full(4,1.1)),IGD(reference)
    rows=[]
    prefix_checks=[]
    for e,good in zip(entries,feasible):
        r,a=e["record"],e["arrays"]
        delivered=a["delivered_raw_objectives"]
        # Match the production recommendation's tie break: same maximum
        # output -> lower daily CV, rather than whichever identity came first.
        observed_pick=int(np.lexsort((good[:,1],good[:,0]))[0])
        delivered_pick=int(np.lexsort((delivered[:,1],delivered[:,0]))[0])
        initial=a["raw_objectives"][:48][a["raw_violations"][:48]<=1e-9]
        f=nondominated((good-low)/scale);d=nondominated((delivered-low)/scale)
        rows.append({"group":r["group"],"seed":r["seed"],"policy":r["policy"],"budget":r["budget"],
            "observed_hv":float(hv.do(f)),"delivered_hv":float(hv.do(d)),
            "observed_igd":float(igd.do(f)),"delivered_igd":float(igd.do(d)),
            "initial_hv":float(hv.do(nondominated((initial-low)/scale))),
            "initial_best_output":float(-initial[:,0].min()),
            "observed_best_output":float(-good[:,0].min()),
            "delivered_best_output":float(-delivered[:,0].min()),
            "observed_best_output_raw_objectives":good[observed_pick].tolist(),
            "delivered_best_output_raw_objectives":delivered[delivered_pick].tolist(),
            "hard_feasible_fraction":float(np.mean(a["raw_violations"]<=1e-9)),
            "numeric_unique":len(set(a["numeric_hashes"].tolist())),
            "case_elapsed_seconds":r["formal"]["case_elapsed_seconds"],
            "verified_arrays_sha256":r["verified_arrays_sha256"]})
    for seed in by_seed:
        for policy in ("legacy","window"):
            group=sorted((e for e in entries if e["record"]["seed"]==seed and e["record"]["policy"]==policy),key=lambda e:e["record"]["budget"])
            for small,big in zip(group,group[1:]):
                n=small["record"]["budget"]
                prefix_checks.append({"seed":seed,"policy":policy,"smaller_budget":n,"larger_budget":big["record"]["budget"],
                    "same_numeric_and_raw_prefix":all(np.array_equal(small["arrays"][k],big["arrays"][k][:n])
                        for k in ("numeric_hashes","raw_objectives","raw_violations"))})
    means=[]
    for policy in ("legacy","window"):
        for budget in sorted({r["budget"] for r in rows}):
            subset=[r for r in rows if r["policy"]==policy and r["budget"]==budget]
            if len(subset)!=len(by_seed):raise ValueError("unpaired budget cells")
            means.append({"policy":policy,"budget":budget,"seeds":len(subset),**{k:float(np.mean([r[k] for r in subset]))
                for k in ("observed_hv","delivered_hv","observed_best_output","delivered_best_output","observed_igd","delivered_igd")}})
    return {"schema":"production.budget_comparison/v1","results":rows,"means":means,"prefix_checks":prefix_checks,
        "initial_candidates_and_raw_feedback_equal_within_seed":True,
        "normalization_low":low.tolist(),"normalization_high":high.tolist(),"hv_reference_point":[1.1]*4,
        "empirical_reference_front":reference.tolist(),
        "measurement":"common raw four-objective scale across all policies, seeds and budgets; observed proposals and delivered archive reported separately",
        "limitations":"three paired seeds; empirical reference not global optimum; search budget excludes existing post-search export audits; no speed claim"}


def plot_report(report, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    budgets=sorted({r["budget"] for r in report["results"]})
    fig,axes=plt.subplots(2,2,figsize=(11,7.3))
    fields=("delivered_hv","observed_hv","delivered_best_output","production_cv")
    titles=("Delivered archive: four-objective coverage","Evaluated candidates: four-objective coverage",
            "Maximum output actually delivered","Daily variation of maximum-output recommendation")
    labels=("Mean raw HV (dimensionless)","Mean raw HV (dimensionless)",
            "Mean production (units)","Mean daily CV (dimensionless)")
    for ax,field,title,label in zip(axes.flat,fields,titles,labels):
        for policy,color in (("legacy","#2864b3"),("window","#b35b23")):
            values=[]
            for budget in budgets:
                rows=[r for r in report["results"] if r["policy"]==policy and r["budget"]==budget]
                values.append(np.mean([np.sqrt(r["delivered_best_output_raw_objectives"][1])
                    if field=="production_cv" else r[field] for r in rows]))
            ax.plot(budgets,values,marker="o",linewidth=2,color=color,label=policy)
        ax.set_title(title,fontsize=11,loc="left")
        ax.set_xlabel("Search evaluations per run")
        ax.set_ylabel(label)
        ax.set_xticks(budgets)
        ax.grid(axis="y",alpha=.2)
        ax.spines[["top","right"]].set_visible(False)
    axes[0,0].legend(frameon=False)
    fig.suptitle("Production scheduling: budget-only cloud experiment",fontsize=14,x=.08,ha="left")
    fig.tight_layout(rect=(0,.07,1,.95))
    seeds=len({r["seed"] for r in report["results"]})
    fig.text(.08,.025,f"{seeds} paired seeds; one CPU per task. Shared raw four-objective scale across all {len(report['results'])} runs.\n"
        f"Source: {report['run_id']}. Existing post-search export audits excluded from search budget.",fontsize=8,color="#555555")
    fig.savefig(path,dpi=170)
    plt.close(fig)


def main(argv=None):
    import pymoo
    if pymoo.__version__!="0.6.2":raise ValueError("requires pymoo==0.6.2")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder",required=True,type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--plot",action="store_true")
    args=parser.parse_args(argv)
    state,entries=load_verified(args.folder)
    report={**summarize(entries),"run_id":state["run_id"],"inputs":state["inputs"],
        "cloud_environment":state["environment"],"pymoo":pymoo.__version__,
        "reporter_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "artifact_scope":"cloud collectors verified original Artifact bindings and exact candidate identities; local analysis reads hash-checked evidence copies, not remapped Artifact authorities"}
    output=args.output or args.folder/"comparison.json"
    with output.open("x",encoding="utf-8") as target:json.dump(report,target,ensure_ascii=False,indent=2,allow_nan=False)
    if args.plot:plot_report(report,output.with_suffix(".png"))
    print(json.dumps({"report":str(output),"means":report["means"],"all_prefixes_equal":all(x["same_numeric_and_raw_prefix"] for x in report["prefix_checks"])},ensure_ascii=False))
    return 0


if __name__=="__main__":raise SystemExit(main())
