import math
import os
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import rcParams

from f1_data import TEAMS, TIRES, TRACKS, TRACK_EVENT_ALIASES, WEATHER, build_track_from_points, load_reference_profile
from f1_fetch_real_data import build_reference

G, RHO = 9.81, 1.225
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fastf1_cache")

def clamp(x,a,b): return max(a,min(b,x))
def fmt_sec(s): m=int(s//60); return f"{m}:{(s-m*60):06.3f}"
def angle_wrap(a):
    while a>math.pi: a-=2*math.pi
    while a<-math.pi: a+=2*math.pi
    return a
def pit_sched(total,stops):
    if stops<=0: return []
    return [max(2,min(total-1,round(i*total/(stops+1)))) for i in range(1,stops+1)]

REAL_TRACKS={name:build_track_from_points(name) for name in TRACKS}

def track_layout(name):
    real=REAL_TRACKS.get(name)
    return real if real else TRACKS[name]

def reference_adjustments(track_name,team_name):
    ref=load_reference_profile(track_name)
    if not ref: return {}
    team_data=(ref.get("teams") or {}).get(team_name,{})
    track_data=ref.get("track",{})
    return dict(
        topSpeedKph=team_data.get("top_speed_kph"),
        avgLapKph=team_data.get("avg_speed_kph"),
        fuelPerLapKg=track_data.get("fuel_per_lap_kg"),
        pitLoss=track_data.get("pit_loss_s"),
    )

def integrate(params,seg,state,track):
    dist,dt=seg["distanceKm"]*1000,0.05
    base_radius={"straight":12000,"fast":170,"slow":72}[seg["type"]]
    x,v,t=0,max(22,state["vEntry"]),0
    top_speed=params["topSpeedMS"]*(0.985 if seg["type"]=="straight" else 0.88 if seg["type"]=="fast" else 0.72)
    while x<dist:
        m=params["mass"]+state["fuel"]
        tyre_state=max(0.72,1-0.0031*state["wear"])
        grip=max(0.78,params["gripEff"]*tyre_state)
        aero_downforce=0.5*RHO*params["downforce"]*v*v
        normal=m*G+aero_downforce
        traction=params["traction"]*grip*normal
        straight_drag_scale=0.92 if seg["type"]=="straight" and track["drsZones"]>0 else 1.0
        drag=0.5*RHO*params["dragEff"]*straight_drag_scale*v*v
        power_force=min((params["powerW"]+params["ersW"])/max(v,14),traction)
        rolling=0.014*m*G
        accel=(power_force-drag-rolling)/m
        if seg["type"]!="straight":
            vc=min(top_speed,math.sqrt(max(25,grip*G*base_radius))*params["cornerFactor"])
            if v>vc:
                brake=(params["brakeMS2"]+0.0045*aero_downforce/m)*(1.05 if seg["type"]=="slow" else 0.92)
                accel=-max(0.5,brake*(v-vc)/max(v,1))
        else:
            accel=min(accel,(params["topSpeedMS"]-v)/max(dt,1e-6))
        v=max(14,min(params["topSpeedMS"],v+accel*dt))
        x+=v*dt
        t+=dt
        if t>220: break
    return dict(t=t,vOut=v)

def simulate(cfg):
    w,tire,track=WEATHER[cfg["weather"]],TIRES[cfg["tireName"]],track_layout(cfg["trackName"])
    ref=reference_adjustments(cfg["trackName"],cfg["teamName"])
    top_speed_kph=ref.get("topSpeedKph") or cfg["topSpeedKph"]
    fuel_base=(ref.get("fuelPerLapKg") or track["fuelPerLapKg"])*w["fuelFactor"]
    pit_loss=ref.get("pitLoss") or track["pitLoss"]
    p=dict(
        powerW=cfg["power"]*1000,
        ersW=cfg["ers"]*120000,
        mass=cfg["mass"],
        dragEff=cfg["drag"]*w["dragFactor"],
        downforce=cfg["downforce"]*1.55,
        traction=cfg["traction"],
        brakeMS2=cfg["brake"]*11.8*track["brakeStress"],
        gripEff=tire["grip"]*w["gripFactor"]*tire["warmup"],
        cornerFactor=1.0+0.06*(cfg["downforce"]-1.0),
        topSpeedMS=(top_speed_kph*w["topSpeedFactor"])/3.6,
    )
    pits=pit_sched(cfg["laps"],cfg["stops"]); st=dict(fuel=cfg["fuel"],wear=0,vEntry=62); laps=[]
    for lap in range(1,cfg["laps"]+1):
        ld=dict(lap=lap,segV=dict(straight=0,fast=0,slow=0),segStats={k:dict(d=0,t=0) for k in("straight","fast","slow")},pit=False); lap_t=0; vc=st["vEntry"]
        for seg in track["segments"]:
            r=integrate(p,seg,dict(fuel=st["fuel"],wear=st["wear"],vEntry=vc),track); lap_t+=r["t"]; vc=r["vOut"]*(0.70 if seg["type"]=="slow" else 0.84 if seg["type"]=="fast" else 0.90)
            ld["segStats"][seg["type"]]["d"]+=seg["distanceKm"]*1000; ld["segStats"][seg["type"]]["t"]+=r["t"]
        for k,ss in ld["segStats"].items(): ld["segV"][k]=(ss["d"]/ss["t"])*3.6 if ss["t"]>0 else 0
        wear_gain=(tire["wear"]*cfg["degrade"]*w["degFactor"]*track["tyreStress"]*(0.78+0.0048*st["fuel"]))
        if cfg["weather"]=="wet" and cfg["tireName"] not in ("Intermedio","Lluvia extrema"): wear_gain*=1.15
        st["wear"]+=wear_gain
        st["fuel"]=max(0,st["fuel"]-(fuel_base*(0.985+0.00032*lap_t)))
        if lap in pits: lap_t+=pit_loss; st["wear"]=max(6,st["wear"]*0.18); ld["pit"]=True
        ld["time"],ld["wear"],ld["fuel"]=lap_t,st["wear"],st["fuel"]; laps.append(ld); st["vEntry"]=max(45,vc)
    avg={k:sum(l["segV"][k] for l in laps)/len(laps) for k in("straight","fast","slow")}
    return dict(laps=laps,total=sum(l["time"] for l in laps),best=min(l["time"] for l in laps),avgSegment=avg,pitLaps=pits)

def build_geo(name,w,h):
    if REAL_TRACKS.get(name):
        pts=REAL_TRACKS[name]["pointsMeters"]; mnx,mxx=min(p["x"] for p in pts),max(p["x"] for p in pts); mny,mxy=min(p["y"] for p in pts),max(p["y"] for p in pts)
        s=min((w-72)/max(1e-6,mxx-mnx),(h-72)/max(1e-6,mxy-mny)); ox=(w-(mxx-mnx)*s)*0.5; oy=(h-(mxy-mny)*s)*0.5
        m=[dict(x=ox+(p["x"]-mnx)*s,y=oy+(mxy-p["y"])*s) for p in pts]+[dict(x=ox+(pts[0]["x"]-mnx)*s,y=oy+(mxy-pts[0]["y"])*s)]
    else:
        pf={"Monza":(0.22,0.08,1.18,0.78,0.2,1.3),"Silverstone":(0.28,0.12,1.03,0.86,0.8,2.2),"Spa-Francorchamps":(0.34,0.14,1.05,0.82,0.55,1.85),"Interlagos":(0.18,0.16,0.98,0.83,1.2,2.65),"Suzuka":(0.30,0.20,1.02,0.88,2.0,0.3)}.get(name,(0.25,0.1,1,0.85,0,1))
        a1,a2,kx,ky,p1,p2=pf; n=900; cx,cy,sx,sy=w*0.5,h*0.52,w*0.34,h*0.33; m=[]
        for i in range(n+1):
            t=i/n*math.pi*2; r=1+a1*math.sin(2*t+p1)+a2*math.sin(3*t+p2)
            m.append(dict(x=cx+sx*r*kx*math.cos(t)+sx*0.08*math.sin(4*t+0.3),y=cy+sy*r*ky*math.sin(t)+sy*0.05*math.cos(3*t+1.1)))
    cum=[0]; tot=0
    for i in range(1,len(m)): tot+=math.hypot(m[i]["x"]-m[i-1]["x"],m[i]["y"]-m[i-1]["y"]); cum.append(tot)
    return dict(points=m,cum=cum,total=tot)

def point_at(geo,p):
    s=clamp(p,0,1)*geo["total"]; lo,hi=0,len(geo["cum"])-1
    while lo<hi:
        mid=(lo+hi)//2
        if geo["cum"][mid]<s: lo=mid+1
        else: hi=mid
    i=int(clamp(lo,1,len(geo["cum"])-1)); s0,s1=geo["cum"][i-1],geo["cum"][i]; k=(s-s0)/max(1e-6,s1-s0); p0,p1=geo["points"][i-1],geo["points"][i]
    return dict(x=p0["x"]+(p1["x"]-p0["x"])*k,y=p0["y"]+(p1["y"]-p0["y"])*k,ang=math.atan2(p1["y"]-p0["y"],p1["x"]-p0["x"]))

def state_at(res,track,tr):
    if tr<=0: f=res["laps"][0]; return dict(lap=1,pRace=0,speed=f["segV"]["straight"],pit=False)
    if tr>=res["total"]: l=res["laps"][-1]; return dict(lap=len(res["laps"]),pRace=1,speed=l["segV"]["slow"],pit=False)
    fr=[]; acc=0
    for s in track["segments"]: acc+=s["distanceKm"]/track["lapDistanceKm"]; fr.append((s["type"],acc))
    sm=0
    for i,lap in enumerate(res["laps"]):
        if sm+lap["time"]>=tr:
            p=(tr-sm)/lap["time"]; stype="slow"
            for tp,lim in fr:
                if p<=lim: stype=tp; break
            return dict(lap=i+1,pRace=(i+p)/len(res["laps"]),speed=lap["segV"][stype],pit=lap["pit"] and p>0.86)
        sm+=lap["time"]
    return dict(lap=len(res["laps"]),pRace=1,speed=0,pit=False)

class App:
    def __init__(self,r):
        self.r=r; r.title("F1 Strategy Lab - Python"); r.geometry("1520x940"); r.minsize(1280,780)
        self.resA=self.resB=self.geo=None; self.track_name="Monza"; self.vrun=True; self.vtime=0; self.last=None; self.after_id=None; self.loaded_ref=None
        self._ui(); self.apply_car(); self.apply_track_defaults()
    def _style(self):
        style=ttk.Style()
        try: style.theme_use("clam")
        except: pass
        bg="#07111f"; shell="#0f1b2d"; card="#14233a"; panel="#1a2d47"; accent="#ff6a3d"; accent_2="#2bd3c6"; ink="#f3f7ff"; muted="#93a9c8"; line="#2b4466"; track="#091423"; success="#49d17d"; warn="#ffb84d"
        self.palette=dict(bg=bg,shell=shell,card=card,accent=accent,accent_2=accent_2,ink=ink,muted=muted,line=line,panel=panel,track=track,success=success,warn=warn)
        self.r.configure(bg=bg)
        style.configure(".", background=bg, foreground=ink, font=("Segoe UI",10), fieldbackground=panel)
        style.configure("App.TFrame", background=bg)
        style.configure("Shell.TFrame", background=shell)
        style.configure("Card.TFrame", background=card, relief="flat")
        style.configure("Panel.TFrame", background=panel, relief="flat")
        style.configure("Card.TLabelframe", background=card, borderwidth=1, relief="solid", bordercolor=line, lightcolor=card, darkcolor=card)
        style.configure("Card.TLabelframe.Label", background=card, foreground=ink, font=("Segoe UI Semibold",10))
        style.configure("Title.TLabel", background=bg, foreground=ink, font=("Bahnschrift SemiBold",24))
        style.configure("Sub.TLabel", background=bg, foreground=muted, font=("Segoe UI",10))
        style.configure("Section.TLabel", background=card, foreground=accent_2, font=("Segoe UI Semibold",9))
        style.configure("CardTitle.TLabel", background=card, foreground=muted, font=("Segoe UI Semibold",9))
        style.configure("CardValue.TLabel", background=card, foreground=ink, font=("Bahnschrift SemiBold",18))
        style.configure("Status.TLabel", background=card, foreground=muted, font=("Segoe UI",9))
        style.configure("KPIAccent.TFrame", background="#10243b")
        style.configure("Accent.TButton", background=accent, foreground="white", borderwidth=0, focusthickness=3, focuscolor=accent, padding=(14,10), font=("Segoe UI Semibold",10))
        style.map("Accent.TButton", background=[("active","#ff7c55"),("pressed","#d9562f")])
        style.configure("Soft.TButton", background=panel, foreground=ink, bordercolor=line, lightcolor=panel, darkcolor=panel, padding=(11,9), font=("Segoe UI Semibold",10))
        style.map("Soft.TButton", background=[("active","#223a5b")])
        style.configure("App.TNotebook", background=bg, borderwidth=0, tabmargins=(0,0,0,0))
        style.configure("App.TNotebook.Tab", padding=(18,12), font=("Segoe UI Semibold",10), background=shell, foreground=muted)
        style.map("App.TNotebook.Tab", background=[("selected",card),("active",panel)], foreground=[("selected",ink),("active",ink)])
        style.configure("Data.Treeview", rowheight=32, font=("Segoe UI",9), background=card, fieldbackground=card, foreground=ink, bordercolor=line)
        style.configure("Data.Treeview.Heading", font=("Segoe UI Semibold",9), background=panel, foreground=ink, relief="flat")
        style.map("Data.Treeview", background=[("selected","#263452")], foreground=[("selected",ink)])
        style.configure("TEntry", padding=7, fieldbackground=panel, foreground=ink, bordercolor=line, lightcolor=panel, darkcolor=panel)
        style.configure("TCombobox", padding=6, fieldbackground=panel, foreground=ink, bordercolor=line, lightcolor=panel, darkcolor=panel, arrowsize=14)
        rcParams["font.family"]="Segoe UI"
    def _add_field(self,parent,label,key,val="",kind="entry",values=None,width=20):
        wrap=ttk.Frame(parent,style="Card.TFrame"); wrap.grid_columnconfigure(0,weight=1)
        ttk.Label(wrap,text=label.upper(),style="CardTitle.TLabel").grid(row=0,column=0,sticky="w")
        self.v[key]=tk.StringVar(value=val)
        if kind=="combo":
            w=ttk.Combobox(wrap,textvariable=self.v[key],values=values or [],state="readonly",width=width)
        else:
            w=ttk.Entry(wrap,textvariable=self.v[key],width=width)
        w.grid(row=1,column=0,sticky="ew",pady=(4,0))
        return wrap,w
    def _make_scrollable_panel(self,parent,frame_style,canvas_bg,padding=(0,0,0,0)):
        outer=ttk.Frame(parent,style=frame_style)
        outer.rowconfigure(0,weight=1); outer.columnconfigure(0,weight=1)
        canvas=tk.Canvas(outer,bg=canvas_bg,highlightthickness=0,bd=0)
        scroll=ttk.Scrollbar(outer,orient="vertical",command=canvas.yview)
        inner=ttk.Frame(canvas,style=frame_style,padding=padding)
        win=canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e: canvas.itemconfigure(win,width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0,column=0,sticky="nsew")
        scroll.grid(row=0,column=1,sticky="ns")
        self._bind_mousewheel(canvas,inner)
        return outer,canvas,inner
    def _bind_mousewheel(self,canvas,*widgets):
        targets=(canvas,*widgets)
        def on_wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta/120),"units")
            elif getattr(event,"num",None)==4:
                canvas.yview_scroll(-3,"units")
            elif getattr(event,"num",None)==5:
                canvas.yview_scroll(3,"units")
        for widget in targets:
            widget.bind("<Enter>",lambda _e: canvas.bind_all("<MouseWheel>",on_wheel))
            widget.bind("<Leave>",lambda _e: canvas.unbind_all("<MouseWheel>"))
    def _ui(self):
        self._style()
        self.v={}
        root=ttk.Frame(self.r,padding=14,style="App.TFrame"); root.pack(fill="both",expand=True)
        root.columnconfigure(1,weight=1); root.rowconfigure(1,weight=1)
        header=ttk.Frame(root,style="App.TFrame"); header.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,12))
        ttk.Label(header,text="F1 Strategy Lab",style="Title.TLabel").grid(row=0,column=0,sticky="w")
        ttk.Label(header,text="Telemetria real, comparacion de estrategias y una lectura mas clara de la carrera.",style="Sub.TLabel").grid(row=1,column=0,sticky="w",pady=(2,0))
        shell=ttk.Panedwindow(root,orient="horizontal"); shell.grid(row=1,column=0,columnspan=2,sticky="nsew")
        left_outer=ttk.Frame(shell,style="Shell.TFrame",width=360); right=ttk.Frame(shell,style="App.TFrame")
        shell.add(left_outer,weight=0); shell.add(right,weight=1)
        left_outer.rowconfigure(0,weight=1); left_outer.columnconfigure(0,weight=1)
        left_panel,left_canvas,left=self._make_scrollable_panel(left_outer,"Shell.TFrame",self.palette["shell"],padding=(10,10,12,10))
        left_panel.grid(row=0,column=0,sticky="nsew")
        left_canvas.configure(width=360)
        self.left_panel=left
        left.columnconfigure(0,weight=1)

        data_card=ttk.LabelFrame(left,text="Datos Reales",padding=12,style="Card.TLabelframe"); data_card.grid(row=0,column=0,sticky="ew",pady=(0,10)); data_card.columnconfigure((0,1),weight=1)
        self._add_field(data_card,"Temporada","year","2025")[0].grid(row=0,column=0,sticky="ew",padx=(0,6),pady=(0,8))
        self._add_field(data_card,"Sesion","session","Q","combo",["Q","R","FP1","FP2","FP3","SQ","S"])[0].grid(row=0,column=1,sticky="ew",pady=(0,8))
        event_values=[]
        for aliases in TRACK_EVENT_ALIASES.values():
            for alias in aliases:
                if alias not in event_values: event_values.append(alias)
        self._add_field(data_card,"Evento FastF1","event","Monza","combo",event_values,26)[0].grid(row=1,column=0,columnspan=2,sticky="ew",pady=(0,8))
        rf=ttk.Frame(data_card,style="Card.TFrame"); rf.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(0,8)); rf.columnconfigure((0,1),weight=1)
        ttk.Button(rf,text="Cargar Datos",command=self.fetch_real_data,style="Accent.TButton").grid(row=0,column=0,sticky="ew",padx=(0,4))
        ttk.Button(rf,text="Refrescar",command=lambda:self.fetch_real_data(force=True),style="Soft.TButton").grid(row=0,column=1,sticky="ew",padx=(4,0))
        self.real_status=tk.StringVar(value="Datos reales: no cargados")
        ttk.Label(data_card,text="LIVE DATA",style="Section.TLabel").grid(row=3,column=0,columnspan=2,sticky="w",pady=(2,2))
        ttk.Label(data_card,textvariable=self.real_status,style="Status.TLabel",wraplength=300,justify="left").grid(row=4,column=0,columnspan=2,sticky="ew")

        car_card=ttk.LabelFrame(left,text="Auto Y Circuito",padding=12,style="Card.TLabelframe"); car_card.grid(row=1,column=0,sticky="ew",pady=(0,10)); car_card.columnconfigure((0,1),weight=1)
        self._add_field(car_card,"Equipo 2026","car","Ferrari","combo",list(TEAMS.keys()),18)[0].grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,8))
        ttk.Button(car_card,text="Aplicar Equipo",command=self.apply_car,style="Soft.TButton").grid(row=1,column=0,columnspan=2,sticky="ew",pady=(0,8))
        self._add_field(car_card,"Circuito","track","Monza","combo",list(TRACKS.keys()),18)[0].grid(row=2,column=0,sticky="ew",padx=(0,6),pady=(0,8))
        self._add_field(car_card,"Clima","weather","dry","combo",list(WEATHER.keys()),18)[0].grid(row=2,column=1,sticky="ew",pady=(0,8))
        self._add_field(car_card,"Vueltas","laps",str(TRACKS["Monza"]["raceLaps"]))[0].grid(row=3,column=0,sticky="ew",padx=(0,6),pady=(0,8))
        ttk.Button(car_card,text="Aplicar Circuito",command=self.apply_track_defaults,style="Soft.TButton").grid(row=3,column=1,sticky="ew",pady=(0,8))
        perf=ttk.Frame(car_card,style="Card.TFrame"); perf.grid(row=4,column=0,columnspan=2,sticky="ew"); perf.columnconfigure((0,1),weight=1)
        fields=[("Potencia (kW)","power"),("Masa (kg)","mass"),("Drag CdA","drag"),("Carga aero","downforce"),("Traccion","traction"),("Frenado","brake"),("ERS","ers"),("Vel punta (km/h)","topSpeedKph")]
        for idx,(label,key) in enumerate(fields):
            widget=self._add_field(perf,label,key)[0]
            widget.grid(row=idx//2,column=idx%2,sticky="ew",padx=(0,6) if idx%2==0 else (6,0),pady=(0,8))

        strat_card=ttk.LabelFrame(left,text="Estrategias",padding=12,style="Card.TLabelframe"); strat_card.grid(row=2,column=0,sticky="ew",pady=(0,10)); strat_card.columnconfigure((0,1),weight=1)
        ttk.Label(strat_card,text="Plan A",style="CardTitle.TLabel").grid(row=0,column=0,sticky="w",pady=(0,6))
        ttk.Label(strat_card,text="Plan B",style="CardTitle.TLabel").grid(row=0,column=1,sticky="w",pady=(0,6))
        plan_a=ttk.Frame(strat_card,style="Card.TFrame"); plan_b=ttk.Frame(strat_card,style="Card.TFrame")
        plan_a.grid(row=1,column=0,sticky="nsew",padx=(0,6)); plan_b.grid(row=1,column=1,sticky="nsew",padx=(6,0))
        for idx,(label,key,val,values) in enumerate([("Neumatico","tireA","C3 Medium",list(TIRES.keys())),("Combustible","fuelA","100",None),("Paradas","stopsA","1",None),("Degradacion","degradeA","1.0",None)]):
            self._add_field(plan_a,label,key,val,"combo" if values else "entry",values,16)[0].grid(row=idx,column=0,sticky="ew",pady=(0,8))
        for idx,(label,key,val,values) in enumerate([("Neumatico","tireB","C4 Soft",list(TIRES.keys())),("Combustible","fuelB","100",None),("Paradas","stopsB","2",None),("Degradacion","degradeB","1.0",None)]):
            self._add_field(plan_b,label,key,val,"combo" if values else "entry",values,16)[0].grid(row=idx,column=0,sticky="ew",pady=(0,8))
        actions=ttk.Frame(left,style="Shell.TFrame"); actions.grid(row=3,column=0,sticky="ew",pady=(0,12)); actions.columnconfigure((0,1),weight=1)
        ttk.Button(actions,text="Simular",command=self.run,style="Accent.TButton").grid(row=0,column=0,sticky="ew",padx=(0,4))
        ttk.Button(actions,text="Intercambiar A/B",command=self.swap,style="Soft.TButton").grid(row=0,column=1,sticky="ew",padx=(4,0))

        right.columnconfigure(0,weight=1); right.rowconfigure(2,weight=1)
        k=ttk.Frame(right,style="App.TFrame"); k.grid(row=0,column=0,sticky="ew",pady=(0,10)); [k.columnconfigure(i,weight=1) for i in range(5)]
        self.k={n:tk.StringVar(value="-") for n in("ta","tb","df","ba","bb")}
        for i,(t,n) in enumerate([("Tiempo total A","ta"),("Tiempo total B","tb"),("Diferencia","df"),("Mejor vuelta A","ba"),("Mejor vuelta B","bb")]):
            f=ttk.Frame(k,style="KPIAccent.TFrame",padding=12); f.grid(row=0,column=i,sticky="ew",padx=4)
            bar=tk.Frame(f,bg=self.palette["accent"] if n in ("ta","ba") else self.palette["accent_2"] if n in ("tb","bb") else self.palette["success"],height=3)
            bar.pack(fill="x",side="top",anchor="n",pady=(0,10))
            ttk.Label(f,text=t.upper(),style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(f,textvariable=self.k[n],style="CardValue.TLabel").pack(anchor="w",pady=(8,0))
        summary=ttk.Frame(right,style="Card.TFrame",padding=12); summary.grid(row=1,column=0,sticky="ew",pady=(0,10))
        self.note=tk.StringVar(value="Listo para cargar una sesion real y comparar estrategias.")
        ttk.Label(summary,text="RACE BRIEF",style="Section.TLabel").pack(anchor="w")
        ttk.Label(summary,textvariable=self.note,style="Status.TLabel",wraplength=960,justify="left").pack(anchor="w",pady=(6,0))
        notebook=ttk.Notebook(right,style="App.TNotebook"); notebook.grid(row=2,column=0,sticky="nsew")
        sim_tab=ttk.Frame(notebook,style="App.TFrame",padding=2); analysis_tab=ttk.Frame(notebook,style="App.TFrame",padding=2)
        notebook.add(sim_tab,text="Simulacion"); notebook.add(analysis_tab,text="Analisis")
        sim_tab.columnconfigure(0,weight=1); sim_tab.rowconfigure(1,weight=1)
        vc=ttk.LabelFrame(sim_tab,text="Simulacion Visual",padding=10,style="Card.TLabelframe"); vc.grid(row=0,column=0,sticky="ew")
        top=ttk.Frame(vc,style="Card.TFrame"); top.pack(fill="x",pady=(0,8))
        self.play=ttk.Button(top,text="Pausar",command=self.toggle); self.play.pack(side="left",padx=(0,4)); ttk.Button(top,text="Reiniciar",command=self.restart_btn).pack(side="left")
        ttk.Label(top,text="Velocidad").pack(side="left",padx=(8,4)); self.speed=tk.StringVar(value="20"); cb=ttk.Combobox(top,textvariable=self.speed,values=["12","20","30","45"],state="readonly",width=8); cb.pack(side="left")
        self.cv=tk.Canvas(vc,height=320,bg=self.palette["track"],highlightthickness=1,highlightbackground="#32486e"); self.cv.pack(fill="x")
        self.vmsg=tk.StringVar(value="Listo para simular."); ttk.Label(vc,textvariable=self.vmsg,style="Status.TLabel").pack(anchor="w",pady=(8,0))
        analysis_panel,analysis_canvas,analysis_body=self._make_scrollable_panel(analysis_tab,"App.TFrame",self.palette["bg"],padding=(0,0,8,0))
        analysis_panel.pack(fill="both",expand=True)
        analysis_body.columnconfigure(0,weight=1)
        ch=ttk.LabelFrame(analysis_body,text="Graficos",padding=10,style="Card.TLabelframe"); ch.grid(row=0,column=0,sticky="ew",pady=(0,10))
        self.fig=Figure(figsize=(10,5),dpi=100); self.ax=[self.fig.add_subplot(221),self.fig.add_subplot(222),self.fig.add_subplot(223),self.fig.add_subplot(224)]; self.fig.tight_layout(pad=2)
        self.fc=FigureCanvasTkAgg(self.fig,master=ch); self.fc.get_tk_widget().pack(fill="both",expand=True)
        tb=ttk.LabelFrame(analysis_body,text="Detalle Por Vuelta",padding=10,style="Card.TLabelframe"); tb.grid(row=1,column=0,sticky="ew")
        cols=("lap","at","aw","af","ap","bt","bw","bf","bp"); self.tv=ttk.Treeview(tb,columns=cols,show="headings",height=11,style="Data.Treeview")
        for c,h,w in [("lap","Vuelta",60),("at","A tiempo",95),("aw","A desgaste",95),("af","A combustible",100),("ap","A parada",80),("bt","B tiempo",95),("bw","B desgaste",95),("bf","B combustible",100),("bp","B parada",80)]:
            self.tv.heading(c,text=h); self.tv.column(c,width=w,anchor="center")
        ys=ttk.Scrollbar(tb,orient="vertical",command=self.tv.yview); self.tv.configure(yscrollcommand=ys.set); self.tv.pack(side="left",fill="both",expand=True); ys.pack(side="left",fill="y",padx=(8,0))
    def apply_car(self):
        c=TEAMS[self.v["car"].get()]
        self.v["power"].set(str(c["power"])); self.v["mass"].set(str(c["mass"])); self.v["drag"].set(str(c["drag"]))
        self.v["downforce"].set(str(c["downforce"])); self.v["traction"].set(str(c["traction"])); self.v["brake"].set(str(c["brake"]))
        self.v["ers"].set(str(c["ers"])); self.v["topSpeedKph"].set(str(int(348-(c["drag"]-0.81)*80+(c["power"]-748)*0.9)))
    def apply_track_defaults(self):
        track=self.v["track"].get()
        t=track_layout(track); self.v["laps"].set(str(t["raceLaps"]))
        aliases=TRACK_EVENT_ALIASES.get(track,[track])
        if self.v["event"].get() not in aliases: self.v["event"].set(aliases[0])
    def cfg(self,s):
        try:
            return dict(teamName=self.v["car"].get(),power=float(self.v["power"].get()),mass=float(self.v["mass"].get()),drag=float(self.v["drag"].get()),downforce=float(self.v["downforce"].get()),traction=float(self.v["traction"].get()),brake=float(self.v["brake"].get()),ers=float(self.v["ers"].get()),topSpeedKph=float(self.v["topSpeedKph"].get()),trackName=self.v["track"].get(),laps=int(float(self.v["laps"].get())),weather=self.v["weather"].get(),tireName=self.v["tireA" if s=="A" else "tireB"].get(),fuel=float(self.v["fuelA" if s=="A" else "fuelB"].get()),stops=int(float(self.v["stopsA" if s=="A" else "stopsB"].get())),degrade=float(self.v["degradeA" if s=="A" else "degradeB"].get()))
        except: raise ValueError("Revisa los valores numericos.")
    def fetch_real_data(self,force=False):
        track=self.v["track"].get(); year=int(float(self.v["year"].get())); event=self.v["event"].get().strip(); session=self.v["session"].get().strip()
        if not force:
            ref=load_reference_profile(track)
            if ref and int(ref.get("year",0))==year and str(ref.get("session","")).upper()==session.upper():
                self.loaded_ref=ref
                self.real_status.set(f"Datos reales: {track} {year} {session} ya cargados")
                REAL_TRACKS[track]=build_track_from_points(track)
                return ref
        self.real_status.set(f"Cargando datos reales: {event} {year} {session} ...")
        self.r.update_idletasks()
        try:
            build_reference(year, event, session, CACHE_DIR, output_name=track)
            REAL_TRACKS[track]=build_track_from_points(track)
            ref=load_reference_profile(track)
            if not ref:
                raise RuntimeError("Se descargo la referencia pero no pudo leerse desde disco.")
            self.loaded_ref=ref
            self.real_status.set(f"Datos reales: {track} {year} {session} listos")
            return ref
        except Exception as e:
            self.real_status.set("Datos reales: error de carga")
            raise RuntimeError(
                "No se pudieron cargar datos reales con FastF1. "
                "Verifica que FastF1 este instalado y que haya acceso a internet."
            ) from e
    def run(self):
        try:
            self.fetch_real_data(force=False)
            a,b=self.cfg("A"),self.cfg("B"); assert a["laps"]>=1
            self.resA,self.resB=simulate(a),simulate(b)
        except Exception as e: messagebox.showerror("Error",str(e)); return
        d=self.resA["total"]-self.resB["total"]; f="A" if d<0 else "B"
        self.k["ta"].set(fmt_sec(self.resA["total"])); self.k["tb"].set(fmt_sec(self.resB["total"])); self.k["df"].set(f"{abs(d):.3f} s ({f} mas rapido)")
        self.k["ba"].set(fmt_sec(self.resA["best"])); self.k["bb"].set(fmt_sec(self.resB["best"]))
        pa=f"A para en vueltas {', '.join(map(str,self.resA['pitLaps']))}" if self.resA["pitLaps"] else "A no para"
        pb=f"B para en vueltas {', '.join(map(str,self.resB['pitLaps']))}" if self.resB["pitLaps"] else "B no para"
        ref=self.loaded_ref or load_reference_profile(a["trackName"]) or {}
        src=f"{ref.get('event',a['trackName'])} {ref.get('year',self.v['year'].get())} {ref.get('session',self.v['session'].get())}"
        self.note.set(f"Estrategia {f} gana por {abs(d):.2f} s. {pa}. {pb}. Datos reales: {src}.")
        self.draw_charts(); self.draw_table(); self.restart(a["trackName"])
    def draw_charts(self):
        self.fig.patch.set_facecolor(self.palette["card"])
        for x in self.ax:
            x.clear(); x.set_facecolor(self.palette["card"]); x.grid(color="#31415e",alpha=0.35,linewidth=0.8); x.tick_params(colors=self.palette["muted"]); [sp.set_color(self.palette["line"]) for sp in x.spines.values()]
            x.title.set_color(self.palette["ink"]); x.xaxis.label.set_color(self.palette["muted"]); x.yaxis.label.set_color(self.palette["muted"])
        xa,xb=range(1,len(self.resA["laps"])+1),range(1,len(self.resB["laps"])+1); ca,cb="#ff6961","#50d4ff"
        self.ax[0].plot(list(xa),[l["time"] for l in self.resA["laps"]],c=ca,label="Plan A",linewidth=2.2); self.ax[0].plot(list(xb),[l["time"] for l in self.resB["laps"]],c=cb,label="Plan B",linewidth=2.2); self.ax[0].set_title("Tiempo Por Vuelta"); self.ax[0].legend(frameon=False,labelcolor=self.palette["muted"])
        self.ax[1].plot(list(xa),[l["wear"] for l in self.resA["laps"]],c=ca,label="Plan A",linewidth=2.2); self.ax[1].plot(list(xb),[l["wear"] for l in self.resB["laps"]],c=cb,label="Plan B",linewidth=2.2); self.ax[1].set_title("Desgaste Neumatico"); self.ax[1].legend(frameon=False,labelcolor=self.palette["muted"])
        self.ax[2].plot(list(xa),[l["fuel"] for l in self.resA["laps"]],c=ca,label="Plan A",linewidth=2.2); self.ax[2].plot(list(xb),[l["fuel"] for l in self.resB["laps"]],c=cb,label="Plan B",linewidth=2.2); self.ax[2].set_title("Combustible Remanente"); self.ax[2].legend(frameon=False,labelcolor=self.palette["muted"])
        c=["straight","fast","slow"]; la=[self.resA["avgSegment"][k] for k in c]; lb=[self.resB["avgSegment"][k] for k in c]; xx=[0,1,2]; w=0.35
        self.ax[3].bar([i-w/2 for i in xx],la,w,color=ca,label="Plan A"); self.ax[3].bar([i+w/2 for i in xx],lb,w,color=cb,label="Plan B"); self.ax[3].set_xticks(xx,["Recta","Curva rapida","Curva lenta"]); self.ax[3].set_title("Velocidad Promedio Por Segmento"); self.ax[3].legend(frameon=False,labelcolor=self.palette["muted"])
        self.fig.tight_layout(pad=2); self.fc.draw_idle()
    def draw_table(self):
        [self.tv.delete(i) for i in self.tv.get_children()]; n=max(len(self.resA["laps"]),len(self.resB["laps"]))
        for i in range(n):
            a=self.resA["laps"][i] if i<len(self.resA["laps"]) else None; b=self.resB["laps"][i] if i<len(self.resB["laps"]) else None
            self.tv.insert("", "end", values=(i+1,f"{a['time']:.3f} s" if a else "-",f"{a['wear']:.1f} %" if a else "-",f"{a['fuel']:.1f} kg" if a else "-",("Si" if a and a["pit"] else "No"),f"{b['time']:.3f} s" if b else "-",f"{b['wear']:.1f} %" if b else "-",f"{b['fuel']:.1f} kg" if b else "-",("Si" if b and b["pit"] else "No")))
    def swap(self):
        a=(self.v["tireA"].get(),self.v["fuelA"].get(),self.v["stopsA"].get(),self.v["degradeA"].get())
        self.v["tireA"].set(self.v["tireB"].get()); self.v["fuelA"].set(self.v["fuelB"].get()); self.v["stopsA"].set(self.v["stopsB"].get()); self.v["degradeA"].set(self.v["degradeB"].get())
        self.v["tireB"].set(a[0]); self.v["fuelB"].set(a[1]); self.v["stopsB"].set(a[2]); self.v["degradeB"].set(a[3]); self.run()
    def restart(self,track):
        self.track_name=track; self.vtime=0; self.last=None; self.vrun=True; self.play.config(text="Pausar")
        self.geo=build_geo(track,int(self.cv.winfo_width() or 940),int(self.cv.winfo_height() or 300))
        if self.after_id: self.r.after_cancel(self.after_id); self.after_id=None
        self.frame()
    def restart_btn(self):
        if self.resA and self.resB: self.restart(self.track_name)
    def toggle(self): self.vrun=not self.vrun; self.play.config(text="Pausar" if self.vrun else "Reanudar")
    def frame(self):
        if not (self.resA and self.resB and self.geo): return
        tr=track_layout(self.track_name); tref=max(self.resA["total"],self.resB["total"]); now=int(self.r.tk.call("clock","milliseconds"))
        if self.vrun:
            if self.last is not None: self.vtime=min(tref,self.vtime+((now-self.last)/1000.0)*float(self.speed.get()))
            self.last=now
        else: self.last=now
        a,b=state_at(self.resA,tr,self.vtime),state_at(self.resB,tr,self.vtime); pa,pb=point_at(self.geo,a["pRace"]),point_at(self.geo,b["pRace"]); lane=6
        ax,ay=pa["x"]-math.sin(pa["ang"])*lane,pa["y"]+math.cos(pa["ang"])*lane; bx,by=pb["x"]+math.sin(pb["ang"])*lane,pb["y"]-math.cos(pb["ang"])*lane
        self.cv.delete("all"); pts=self.geo["points"]; flat=[v for p in pts for v in (p["x"],p["y"])]
        self.cv.create_line(*flat,fill="#1d2740",width=26,smooth=True,capstyle=tk.ROUND,joinstyle=tk.ROUND); self.cv.create_line(*flat,fill="#8898bb",width=16,smooth=True,capstyle=tk.ROUND,joinstyle=tk.ROUND)
        st=point_at(self.geo,0.02); self.cv.create_line(st["x"]-8,st["y"]-8,st["x"]+8,st["y"]+8,fill="white",width=2); self.cv.create_line(st["x"]-8,st["y"]+8,st["x"]+8,st["y"]-8,fill="white",width=2)
        for x,y,ang,c,l in[(ax,ay,pa["ang"],"#ff7b3f","A"),(bx,by,pb["ang"],"#33d9ff","B")]:
            self.cv.create_line(x-math.cos(ang)*8,y-math.sin(ang)*8,x+math.cos(ang)*8,y+math.sin(ang)*8,width=6,fill=c); self.cv.create_oval(x-4,y-4,x+4,y+4,fill=c,outline=""); self.cv.create_text(x,y-12,text=l,fill="#e7f0ff",font=("Segoe UI",9,"bold"))
        lead="A" if a["pRace"]>b["pRace"] else "B"; self.vmsg.set(f"t={self.vtime:.1f}s | A V{a['lap']} {a['speed']:.0f} km/h {'(BOX)' if a['pit'] else ''} | B V{b['lap']} {b['speed']:.0f} km/h {'(BOX)' if b['pit'] else ''} | Lider: {lead}")
        if self.vtime>=tref and self.vrun: self.vrun=False; self.play.config(text="Reanudar")
        self.after_id=self.r.after(16,self.frame)

if __name__=="__main__":
    root=tk.Tk()
    try: ttk.Style().theme_use("clam")
    except: pass
    App(root); root.mainloop()
