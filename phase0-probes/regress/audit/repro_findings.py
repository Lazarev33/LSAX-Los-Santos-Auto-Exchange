import os, sys, tempfile
ROOT='/mnt/data/lsax_audit/clean/LSAX-MASTER-SPEC-v1.0-DRAFT1/phase0-probes/sim'
sys.path.insert(0, ROOT)
from journal_timeline_ref import Gta, Lsax, Crash

# Finding A: C1 wallet collision
with tempfile.TemporaryDirectory() as td:
    db=os.path.join(td,'lsax.db')
    g=Gta(1)
    st={}
    l=Lsax(db,g,st)
    l.tick()
    try:
        l.submit('BUY','v1',20_000,'idem-t1','t1',crash_at='C1')
    except Crash as e:
        print('A crash', e)
    l.close(clean=False)
    # unrelated external action happens to make cash equal to expected LSAX after-value
    g.cash=180_000
    # same process/session context otherwise
    l2=Lsax(db,g,st)
    print('A reconcile', l2.rt('reconcile'))
    print('A active_ids', l2.active_ids())
    print('A projection', sorted(l2.projection()))
    print('A gta_applied', g.applied)
    print('A gta_garage', sorted(g.garage))
    print('A safety_match', l2.active_ids()==g.applied and l2.projection()==g.garage)
    print('A stats', st)
    l2.close(clean=False)

# Finding B: foreign save copied/changed while LSAX is down
with tempfile.TemporaryDirectory() as td:
    db=os.path.join(td,'lsax.db')
    g=Gta(1)
    st={}
    l=Lsax(db,g,st)
    l.tick()
    assert l.submit('BUY','v1',20_000,'idem-t1','t1')=='COMMITTED'
    # move time so a clean stop has an unambiguous window
    g.advance(5000)
    l.tick()
    l.close(clean=True)
    # During downtime, a foreign/copied save replaces slot 1. It is not descended from LSAX t1.
    # Its P lies within the inferred downtime window, and mtime occurs while LSAX is down.
    g.W += 5000
    g.ver += 1
    foreign_p = g.P + 1000  # inside stop_p .. stop_p + downtime + slack
    g.slots[1] = dict(P=foreign_p, cash=200_000, garage=frozenset(), applied=tuple(), ver=g.ver, mtime=g.W)
    # GTA then loads the foreign save; load() adds loading-screen wall time.
    g.load(1)
    # Model a process restart so continuation path is not the explanation; slot inference must anchor.
    g.proc += 1
    l2=Lsax(db,g,st)
    print('B reconcile', l2.rt('reconcile'))
    print('B active_ids', l2.active_ids())
    print('B projection', sorted(l2.projection()))
    print('B gta_applied', g.applied)
    print('B gta_garage', sorted(g.garage))
    print('B cash', g.cash)
    print('B safety_match', l2.active_ids()==g.applied and l2.projection()==g.garage)
    print('B stats', st)
    l2.close(clean=False)
