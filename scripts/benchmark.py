"""Repeatable solver benchmark on a labelled synthetic hand trajectory."""
import argparse,json,time,platform
import numpy as np
from pc.protocol import Frame,Hand
from pc.reconstruction.model import Model,project
from pc.reconstruction.solver import Solver

def main():
    p=argparse.ArgumentParser();p.add_argument('--frames',type=int,default=120);a=p.parse_args()
    model=Model();solver=Solver();k=np.array([420,420,320,240]);rng=np.random.default_rng(19)
    times=[];errors=[];depth=[];rejected=0
    for i in range(a.frames):
        t=i/60;z=.6+.04*np.sin(t);x=np.r_[[.02*np.sin(t),0,z],[np.pi,.15*np.sin(t),.1*np.sin(t)],np.tile([0,.2,.3,.195],5)]
        joints=model.forward(x,2);uv=project(joints,k)+rng.normal(0,.6,(21,2))
        h=Hand(2,2,0,np.column_stack([uv/[640,480],np.ones(21)]));f=Frame(i,1,10+t,640,480,k,[h])
        try:o=solver.solve(h,f,2);times.append(o.solve_ms);errors.append(o.pixel_rmse);depth.append(abs(o.position[2]-z))
        except ValueError:rejected+=1
    result={'source':'synthetic template + 0.6px noise; not real camera accuracy','platform':platform.platform(),'frames':a.frames,'rejected':rejected,'mean_ms':float(np.mean(times)),'p95_ms':float(np.percentile(times,95)),'mean_reprojection_px':float(np.mean(errors)),'mean_depth_error_m':float(np.mean(depth))}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
