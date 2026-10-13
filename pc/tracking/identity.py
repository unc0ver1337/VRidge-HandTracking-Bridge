import numpy as np
from scipy.optimize import linear_sum_assignment

class Identity:
    """Two fixed semantic slots; motion/shape assignment resists chirality flicker.

    Fully occluded crossing is intrinsically ambiguous; unmatched stale slots expire.
    iOS observation IDs are hints, not a license to swap controller roles.
    """
    def __init__(self, retention=0.7): self.slots={}; self.retention=retention
    def update(self,hands,t):
        self.slots={s:v for s,v in self.slots.items() if t-v['t']<self.retention}
        output={}; used=set()
        sides=list(self.slots)
        if sides and hands:
            cost=np.zeros((len(sides),len(hands)))
            for i,s in enumerate(sides):
                old=self.slots[s]; dt=t-old['t']
                pred=old['p']+old['v']*min(dt,0.1)
                for j,h in enumerate(hands):
                    cost[i,j]=np.linalg.norm(h.points[0,:2]-pred)+0.06*(h.side not in (0,s))
            rows,cols=linear_sum_assignment(cost)
            for i,j in zip(rows,cols):
                if cost[i,j]<0.32: output[sides[i]]=hands[j]; used.add(j)
        for j,h in enumerate(hands):
            if j not in used and h.side in (1,2) and h.side not in output and h.side not in self.slots:
                output[h.side]=h
        for s,h in output.items():
            p=h.points[0,:2].copy(); old=self.slots.get(s)
            v=(p-old['p'])/max(t-old['t'],1e-3) if old else np.zeros(2)
            self.slots[s]={'p':p,'v':v,'t':t}
        return output
