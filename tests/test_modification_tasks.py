import numpy as np
import pytest
from benchmarks.modification_tasks import native_age, pymoo_age, pool_native_age, age_order


@pytest.mark.parametrize("implementation", [native_age, pymoo_age, pool_native_age])
def test_age_is_member_survival_count_and_selection_changes_behavior(implementation):
    pytest.importorskip("pymoo")
    batches = [[np.array([i, float(i)]) for i in range(4)]]
    batches += [[np.array([4*g+i, 10.+g+i]) for i in range(4)] for g in range(1,4)]
    plain=implementation(batches,False)
    selected=implementation(batches,True)
    assert plain[0]=={"ids":["c0","c1","c2","c3"],"age":[0]*4}
    assert plain[-1]=={"ids":["c0","c1","c2","c3"],"age":[3]*4}
    assert selected[-1]=={"ids":["c12","c13","c14","c15"],"age":[0]*4}


def test_age_rule_refills_when_too_few_young_members_exist():
    f=np.array([[0.,0.],[1.,1.],[2.,2.],[3.,3.]])
    assert age_order(f,np.array([3,3,0,0]),3).tolist()==[2,3,0]


@pytest.mark.parametrize("settings", [{"reverse":True},{"partial":True},{"reverse":True,"partial":True,"restore_at":3}])
def test_complex_pool_path_matches_reference_and_uninterrupted(settings):
    batches=[[np.array([i,float(i)]) for i in range(4)]]
    batches += [[np.array([4*g+i,10.+g+i]) for i in range(4)] for g in range(1,7)]
    actual=pool_native_age(batches,True,**settings)
    assert actual==pymoo_age(batches,True,**settings)
    clean={k:v for k,v in settings.items() if k!='restore_at'}
    assert actual==pool_native_age(batches,True,**clean)
    if settings.get('partial'):
        # Rejected offspring 4,6,8,10,... never become members.
        assert all(not (int(x[1:])>=4 and int(x[1:])%4 in (0,2)) for row in actual for x in row['ids'])


def test_duplicate_candidate_retains_independent_slot_ages():
    from benchmarks.modification_tasks import duplicate_slot_task
    r=duplicate_slot_task()
    assert r['reference_only_join_rejected'] and r['equal']
    assert r['ids']==['a','a'] and r['ages']==[6,2]
