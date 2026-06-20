"""
ANÁLISIS DE FALLAS EN PAVIMENTOS FLEXIBLES - MÉTODO MTC 2018
Manual de Carreteras: Mantenimiento o Conservación Vial
CORRECCIÓN: Baches (cod.7) detectados en columna de medidas/area_falla
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os, math, re, unicodedata
from datetime import datetime
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches

FALLAS_MTC = {
    1: "Piel de cocodrilo",
    2: "Fisuras longitudinales",
    3: "Deformacion por deficiencia estructural",
    4: "Ahuellamiento",
    5: "Reparaciones o parchados",
    6: "Peladura y desprendimiento",
    7: "Baches (Huecos)",
    8: "Fisuras Transversales",
    9: "Exudacion",
    10: "Danos puntuales",
    11: "Desnivel Calzada Berma",
}

CLASIFICACION = {1:"E",2:"E",3:"E",4:"E",5:"E",
                 6:"S",7:"S",8:"S",9:"S",
                 10:"B",11:"B"}

UNIDAD = {1:"m2",2:"m2",3:"m2",4:"m2",5:"m2",
          6:"m2",7:"und",8:"m2",9:"m2",
          10:"m2",11:"ml"}

GRAVEDADES = {1:"Leve",2:"Moderado",3:"Severo",
              "1":"Leve","2":"Moderado","3":"Severo",
              "L":"Leve","M":"Moderado","S":"Severo"}

PUNTAJE_RANGOS = {
    1:(10,30, 40,200,200),  2:(10,30, 20,100,100),
    3:(10,30, 20,100,100),  4:(10,30, 20,100,100),
    5:(10,30, 10, 50, 50),  6:(10,30, 10, 50, 50),
    7:( 4,10, 20,100,100),  8:(10,30, 10, 50, 50),
    9:(10,30, 20,100,100), 10:(10,30, 10, 50, 50),
   11:(10,30, 20,100,100),
}

ESCALA = [
    (801,1000,"#27ae60","CONDICION BUENO"),
    (300, 800,"#f39c12","CONDICION REGULAR"),
    (  0, 299,"#da3633","CONDICION MALO"),
]

C = {
    "window":"#eef1f5",
    "bg":"#eef1f5",
    "bg2":"#f6f8fb",
    "bg3":"#ffffff",
    "border":"#d8dee7",
    "accent":"#0a84ff",
    "accent2":"#1f2937",
    "accent3":"#34c759",
    "accent4":"#ff9f0a",
    "text":"#1f2937",
    "text_dim":"#6b7280",
    "text_bright":"#ffffff",
    "btn":"#0a84ff",
    "btn_h":"#3399ff",
    "danger":"#ff5f57",
    "warn":"#ff9f0a",
    "ok":"#34c759",
    "table_e":"#edf4ff",
    "table_s":"#edf9f1",
    "table_b":"#fff6e8",
    "table_me":"#dce9ff",
    "table_ms":"#dff5e5",
    "table_mb":"#ffeed1",
    "panel":"#f2f5f9",
    "panel_soft":"#fafbfd",
    "card":"#ffffff",
    "card_alt":"#f8fafc",
    "card_edge":"#dbe1e8",
    "input_bg":"#ffffff",
    "input_border":"#d5dce6",
    "focus":"#83bcff",
    "toolbar":"#f7f8fb",
    "titlebar":"#ffffff",
    "muted":"#eef2f7",
    "pill":"#eef4ff",
}
FT = ("Segoe UI",16,"bold"); FH = ("Segoe UI",10,"bold")
FB = ("Segoe UI",10);         FS = ("Segoe UI",9)
FM = ("Consolas",9)

BUTTON_VARIANTS = {
    "primary":   {"bg":C["btn"],    "hover":C["btn_h"],    "fg":C["text_bright"]},
    "secondary": {"bg":C["muted"],  "hover":"#e5eaf1",     "fg":C["text"]},
    "success":   {"bg":C["ok"],     "hover":"#5fd57f",     "fg":C["text_bright"]},
    "danger":    {"bg":C["danger"], "hover":"#ff7b75",     "fg":C["text_bright"]},
    "warn":      {"bg":C["warn"],   "hover":"#ffb84d",     "fg":C["text_bright"]},
    "ghost":     {"bg":C["card"],   "hover":C["muted"],    "fg":C["text_dim"]},
    "quiet":     {"bg":"#f3f6fb",   "hover":"#e7edf5",     "fg":C["accent"]},
}


def tooltip(w, t):
    tip=None
    def sh(e):
        nonlocal tip
        tip=tk.Toplevel(w); tip.wm_overrideredirect(True)
        tip.configure(bg=C["border"]); tip.wm_geometry(f"+{e.x_root+10}+{e.y_root+5}")
        tk.Label(tip,text=t,bg=C["bg3"],fg=C["text"],font=FS,padx=6,pady=3).pack()
    def hi(e):
        nonlocal tip
        if tip: tip.destroy(); tip=None
    w.bind("<Enter>",sh); w.bind("<Leave>",hi)


def style_button(btn, variant="secondary"):
    spec = BUTTON_VARIANTS.get(variant, BUTTON_VARIANTS["secondary"])
    base_bg = spec["bg"]
    hover_bg = spec["hover"]
    fg = spec["fg"]
    btn.configure(
        bg=base_bg,
        fg=fg,
        activebackground=hover_bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    btn.bind("<Enter>", lambda _e: btn.configure(bg=hover_bg), add="+")
    btn.bind("<Leave>", lambda _e: btn.configure(bg=base_bg), add="+")
    return btn


def make_button(parent, text, command, variant="secondary", font=FB, **kwargs):
    btn = tk.Button(parent, text=text, command=command, font=font, **kwargs)
    return style_button(btn, variant=variant)


def style_entry(widget):
    widget.configure(
        bg=C["input_bg"],
        fg=C["text"],
        insertbackground=C["text"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=C["input_border"],
        highlightcolor=C["focus"],
    )
    return widget


def style_text(widget, bg_key="card_alt"):
    widget.configure(
        bg=C[bg_key],
        fg=C["text"],
        insertbackground=C["text"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=C["card_edge"],
        highlightcolor=C["focus"],
    )
    return widget


def make_card(parent, bg_key="card", padx=0, pady=0):
    outer = tk.Frame(parent, bg=C["card_edge"], bd=0, highlightthickness=0)
    inner = tk.Frame(outer, bg=C[bg_key], bd=0, padx=padx, pady=pady)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner

def norm_grav(v):
    if v is None or (isinstance(v,float) and math.isnan(v)): return None
    s=str(v).strip().upper()
    if s in("1","L","LEVE"):return 1
    if s in("2","M","MODERADO","MOD"):return 2
    if s in("3","S","SEVERO","SEV"):return 3
    return None

def clasif_indice(v):
    if v > 800:  return "CONDICION BUENO",  "#27ae60"
    if v >= 300: return "CONDICION REGULAR", "#f39c12"
    return             "CONDICION MALO",     "#da3633"

def norm_txt(t):
    s=str(t).upper().strip()
    s=unicodedata.normalize('NFKD',s)
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=''.join(c if(c.isalnum() or c==' ')else ' ' for c in s)
    return ' '.join(s.split())

def _raiz(p):
    for sf in("ACION","ONES","URAS","CION","ADES","ADOS","IDOS","ADA","IDA","ES","AS","OS","S"):
        if p.endswith(sf) and len(p)-len(sf)>=4: return p[:len(p)-len(sf)]
    return p

def simil(a,b):
    na,nb=norm_txt(a),norm_txt(b)
    if na==nb:return 100
    if na in nb or nb in na:return 90
    stop={"DE","LA","EL","EN","Y","O","POR","A","LOS","LAS","SIN","CON","DEL"}
    pa={_raiz(p) for p in na.split() if len(p)>2 and p not in stop}
    pb={_raiz(p) for p in nb.split() if len(p)>2 and p not in stop}
    if not pa or not pb:return 0
    c=pa&pb
    cp=set()
    for ra in pa:
        for rb in pb:
            if(ra in rb or rb in ra)and ra not in cp:cp.add(ra);break
    return round(min(len(c|cp)/max(len(pa),len(pb))*80,89))

def buscar_cod(nombre):
    best=(None,0,"")
    for cod,nm in FALLAS_MTC.items():
        sc=simil(nombre,nm)
        if sc>best[1]:best=(cod,sc,nm)
    return best

def es_sin_fallas(valor):
    """Detecta si un valor indica ausencia de fallas (ej: 'SIN FALLAS', 'SIN FALLA', vacio)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return False
    s = norm_txt(str(valor))
    return s in ("SIN FALLAS", "SIN FALLA", "S F", "SF", "SIN DETERIORO",
                 "SIN DETERIOROS", "NINGUNA", "NINGUNO", "NO PRESENTA",
                 "NO HAY FALLAS", "NO HAY FALLA")

def estado_sc(sc):
    if sc>=95:return "✓",C["accent3"],"Exacto"
    if sc>=60:return "≈",C["accent4"],"Similar"
    return "✗",C["danger"],"No encontrado"


# ═══════════════════════════════════════════════════════════════════════════
# MOTOR MTC 2018
# ═══════════════════════════════════════════════════════════════════════════

PROG_RANGO_RE = re.compile(r"(\d+)\+(\d{1,3})_(\d+)\+(\d{1,3})", re.IGNORECASE)
PROG_PUNTO_RE = re.compile(r"(\d+)\+(\d{1,3})", re.IGNORECASE)


def prog_a_metros(valor):
    if valor is None:
        return None
    s = str(valor).strip().upper()
    if not s:
        return None
    m = PROG_PUNTO_RE.search(s)
    if m:
        return int(m.group(1)) * 1000 + int(m.group(2))
    s2 = "".join(ch for ch in s if ch.isdigit())
    if not s2:
        return None
    return int(s2)


def metros_a_prog(metros):
    if metros is None or (isinstance(metros, float) and math.isnan(metros)):
        return ""
    metros = int(round(float(metros)))
    km, m = divmod(metros, 1000)
    return f"{km:02d}+{m:03d}"


def extraer_rango_progresiva(texto):
    if texto is None:
        return None
    m = PROG_RANGO_RE.search(str(texto))
    if not m:
        return None
    ini = int(m.group(1)) * 1000 + int(m.group(2))
    fin = int(m.group(3)) * 1000 + int(m.group(4))
    if fin < ini:
        ini, fin = fin, ini
    return ini, fin


class AnalizadorProgresivas:
    KEYWORDS = (
        "archivo", "file", "imagen", "image", "nombre_archivo",
        "filename", "ruta", "path", "tif", "frame",
    )

    @classmethod
    def detectar_columna(cls, df):
        if df is None:
            return None
        cols = list(df.columns)
        for col in cols:
            txt = str(col).strip().lower()
            if any(k in txt for k in cls.KEYWORDS):
                return col
        for col in cols:
            serie = df[col].dropna().astype(str).head(30)
            if serie.empty:
                continue
            hits = sum(1 for val in serie if extraer_rango_progresiva(val))
            if hits >= max(1, min(5, len(serie))):
                return col
        return None

    @staticmethod
    def preparar_df(df, columna):
        if columna not in df.columns:
            raise ValueError(f"La columna '{columna}' no existe en el Excel.")
        base = df.copy()
        rangos = base[columna].apply(extraer_rango_progresiva)
        base["_prog_ini_m"] = rangos.apply(lambda x: x[0] if x else math.nan)
        base["_prog_fin_m"] = rangos.apply(lambda x: x[1] if x else math.nan)
        base["_prog_tramo"] = base.apply(
            lambda r: (
                f"{metros_a_prog(r['_prog_ini_m'])} - {metros_a_prog(r['_prog_fin_m'])}"
                if pd.notna(r["_prog_ini_m"]) and pd.notna(r["_prog_fin_m"])
                else ""
            ),
            axis=1,
        )
        return base

    @classmethod
    def filtrar_df(cls, df, columna, prog_ini=None, prog_fin=None):
        base = cls.preparar_df(df, columna)
        validos = base.dropna(subset=["_prog_ini_m", "_prog_fin_m"]).copy()
        if prog_ini is not None:
            validos = validos[validos["_prog_ini_m"] >= prog_ini]
        if prog_fin is not None:
            validos = validos[validos["_prog_fin_m"] <= prog_fin]
        return validos

    @classmethod
    def bloques_disponibles(cls, df, columna, tam_bloque, prog_ini=None, prog_fin=None):
        if tam_bloque <= 0:
            raise ValueError("El tamano del bloque debe ser mayor que cero.")
        base = cls.filtrar_df(df, columna, prog_ini, prog_fin)
        if base.empty:
            return [], base
        min_ini = int(base["_prog_ini_m"].min())
        inicio = prog_ini if prog_ini is not None else (min_ini // tam_bloque) * tam_bloque
        base["_bloque_ini"] = base["_prog_ini_m"].apply(
            lambda v: inicio + (int(v - inicio) // tam_bloque) * tam_bloque
        )
        bloques = []
        for bini in sorted(base["_bloque_ini"].dropna().astype(int).unique()):
            bfin = bini + tam_bloque
            blk = base[(base["_prog_ini_m"] >= bini) & (base["_prog_fin_m"] <= bfin)].copy()
            if blk.empty:
                continue
            bloques.append({
                "ini": bini,
                "fin": bfin,
                "n_reg": int(len(blk)),
                "n_img": int(blk[columna].astype(str).nunique()),
                "n_tramos": int(blk["_prog_tramo"].replace("", pd.NA).dropna().nunique()),
                "label": (
                    f"{metros_a_prog(bini)} - {metros_a_prog(bfin)}  |  "
                    f"{int(blk[columna].astype(str).nunique())} imgs"
                ),
            })
        return bloques, base

    @classmethod
    def tramos_disponibles(cls, df, columna, prog_ini=None, prog_fin=None):
        base = cls.filtrar_df(df, columna, prog_ini, prog_fin)
        if base.empty:
            return [], base
        tramos = []
        grupos = (
            base.dropna(subset=["_prog_ini_m", "_prog_fin_m"])
                .groupby(["_prog_ini_m", "_prog_fin_m"], sort=True)
        )
        for (ini, fin), blk in grupos:
            ini = int(ini)
            fin = int(fin)
            tramos.append({
                "ini": ini,
                "fin": fin,
                "n_reg": int(len(blk)),
                "n_img": int(blk[columna].astype(str).nunique()),
                "label": f"{metros_a_prog(ini)} - {metros_a_prog(fin)}",
            })
        return tramos, base


class Motor:

    @staticmethod
    def efij(af,As):
        return (af/As)*100.0 if As>0 and af>0 else 0.0

    @staticmethod
    def efp(recs):
        n=sum(a*e for a,e in recs); d=sum(a for a,e in recs)
        return n/d if d>0 else 0.0

    @staticmethod
    def interp(x,x0,x1,y0,y1):
        if x1==x0:return y0
        return y0+max(0.0,min(1.0,(x-x0)/(x1-x0)))*(y1-y0)

    @classmethod
    def puntaje(cls,cod,efp_val,n_bach=0):
        r=PUNTAJE_RANGOS.get(cod)
        if not r:return 0,"Sin deterioro",0.0
        ul,um,pl,pm,ps=r
        if cod==7:
            n=n_bach
            if n<=0:return 0,"Sin deterioro",0.0
            if n<ul:return 1,"Leve",round(cls.interp(n,0,ul,0,float(pl)),3)
            if n<=um:return 2,"Moderado",round(cls.interp(n,ul,um,float(pl),float(pm)),3)
            return 3,"Severo",float(ps)
        e=efp_val
        if e<=0:return 0,"Sin deterioro",0.0
        if e<ul:return 1,"Leve",round(cls.interp(e,0,float(ul),0,float(pl)),3)
        if e<um:return 2,"Moderado",round(cls.interp(e,float(ul),float(um),float(pl),float(pm)),3)
        return 3,"Severo",float(ps)

    @classmethod
    def procesar(cls, df, mapeo, as_global=None, overrides=None):
        rename={v:k for k,v in mapeo.items() if v and v!="(ninguna)"}
        dw=df.rename(columns=rename)

        if "area_falla" not in dw.columns or dw["area_falla"].isna().all():
            if "ancho_falla" in dw.columns and "largo_falla" in dw.columns:
                dw["area_falla"]=(pd.to_numeric(dw["ancho_falla"],errors="coerce").fillna(0)*
                                  pd.to_numeric(dw["largo_falla"],errors="coerce").fillna(0))
            else:dw["area_falla"]=0.0

        if "area_seccion" not in dw.columns or dw["area_seccion"].isna().all():
            if "ancho_seccion" in dw.columns and "largo_seccion" in dw.columns:
                dw["area_seccion"]=(pd.to_numeric(dw["ancho_seccion"],errors="coerce").fillna(0)*
                                    pd.to_numeric(dw["largo_seccion"],errors="coerce").fillna(0))
            elif as_global and as_global>0:dw["area_seccion"]=as_global
            else:dw["area_seccion"]=1.0

        if "num_deterioros" not in dw.columns:dw["num_deterioros"]=0
        for col in["area_falla","area_seccion","ancho_falla","largo_falla",
                   "ancho_seccion","largo_seccion","num_deterioros"]:
            if col in dw.columns:
                dw[col]=pd.to_numeric(dw[col],errors="coerce").fillna(0)

        if "codigo_falla" not in dw.columns:dw["codigo_falla"]=0
        dw["codigo_falla"]=(pd.to_numeric(dw["codigo_falla"],errors="coerce").fillna(0).astype(int))
        if "nombre_falla" not in dw.columns:
            dw["nombre_falla"]=dw["codigo_falla"].map(FALLAS_MTC).fillna("?")

        # ── Filtrar filas "SIN FALLAS": no deben participar en el cálculo ──
        _mask_sf = dw["nombre_falla"].apply(es_sin_fallas)
        if "codigo_falla" in dw.columns:
            _mask_sf = _mask_sf & (dw["codigo_falla"] == 0)
        dw = dw[~_mask_sf].copy()

        if overrides:
            def res_cod(row):
                cod=row["codigo_falla"]
                if cod==0:
                    nr=str(row.get("nombre_falla","")).strip()
                    if nr in overrides:return overrides[nr]
                    for k,v in overrides.items():
                        if norm_txt(k)==norm_txt(nr):return v
                return cod
            dw["codigo_falla"]=dw.apply(res_cod,axis=1)

        m0=dw["codigo_falla"]==0
        if m0.any() and "nombre_falla" in dw.columns:
            def inf(nm):
                cod,sc,_=buscar_cod(str(nm))
                return cod if cod and sc>=60 else 0
            dw.loc[m0,"codigo_falla"]=dw.loc[m0,"nombre_falla"].apply(inf)

        # ── Fisuras longitudinales (cod 2) y transversales (cod 8):
        #    Si area_falla es 0 pero largo_falla tiene valor, usar largo
        #    como medida directa (son fallas lineales).
        #    Si largo_falla no fue mapeado, se usa area_falla tal cual. ──
        if "largo_falla" in dw.columns:
            mf = dw["codigo_falla"].isin([2, 8]) & (dw["area_falla"] == 0) & (dw["largo_falla"] > 0)
            if mf.any():
                dw.loc[mf, "area_falla"] = dw.loc[mf, "largo_falla"]

        if "gravedad" not in dw.columns:dw["gravedad"]=1
        dw["grav_norm"]=dw["gravedad"].apply(norm_grav).fillna(1).astype(int)
        dw["efij_val"]=dw.apply(lambda r:cls.efij(r["area_falla"],r["area_seccion"]),axis=1)

        # ── Determinar si el usuario mapeó explícitamente num_deterioros ──
        num_det_mapeado = (
            "num_deterioros" in mapeo
            and mapeo["num_deterioros"] not in ("(ninguna)", None, "")
        )

        tabla_rows=[]; resumen=[]; detalle=[]; suma=0.0

        for cod in sorted(FALLAS_MTC.keys()):
            gc=dw[dw["codigo_falla"]==cod]
            nombre=FALLAS_MTC[cod]
            clas=CLASIFICACION.get(cod,"?")
            unid=UNIDAD.get(cod,"m2")

            dg={}
            for gv in[1,2,3]:
                gg=gc[gc["grav_norm"]==gv]
                if len(gg)==0:
                    dg[gv]={"area":0.0,"ndet":0,"efij":0.0,"as":0.0,
                             "ancho":0.0,"largo":0.0}
                else:
                    af=float(gg["area_falla"].sum())
                    As=float(gg["area_seccion"].mean())
                    nd=int(gg["num_deterioros"].sum())
                    aw=float(gg["ancho_seccion"].mean()) if "ancho_seccion" in gg.columns else 0.0
                    lw=float(gg["largo_seccion"].mean())  if "largo_seccion" in gg.columns else 0.0

                    # ══════════════════════════════════════════════════════
                    # CORRECCIÓN BACHES (Cod. 7)
                    # Si num_deterioros NO fue mapeado explícitamente por el
                    # usuario, o su suma es 0, se asume que el conteo de
                    # baches (und) está registrado en la misma columna de
                    # medidas (area_falla). Se usa ese valor como conteo.
                    # Si num_deterioros SÍ fue mapeado y tiene valor > 0,
                    # se respeta esa columna dedicada (comportamiento previo).
                    # ══════════════════════════════════════════════════════
                    if cod == 7:
                        if not num_det_mapeado or nd == 0:
                            nd = int(round(af)) if af > 0 else 0

                    dg[gv]={"area":af,"ndet":nd,"efij":cls.efij(af,As),
                             "as":As,"ancho":aw,"largo":lw}

            recs=[(dg[g]["area"],dg[g]["efij"]) for g in[1,2,3] if dg[g]["area"]>0]
            efp_v=cls.efp(recs) if recs else 0.0
            nb=sum(dg[g]["ndet"] for g in[1,2,3]) if cod==7 else 0

            cn,cl,pt=cls.puntaje(cod,efp_v,nb)
            suma+=pt

            As_cod=float(gc["area_seccion"].mean()) if len(gc)>0 else (as_global or 1.0)
            aw_cod=(float(gc["ancho_seccion"].mean())
                    if "ancho_seccion" in dw.columns and len(gc)>0 else 0.0)
            lw_cod=(float(gc["largo_seccion"].mean())
                    if "largo_seccion" in dw.columns and len(gc)>0 else 0.0)

            for gv in[1,2,3]:
                d=dg[gv]
                # Para cod 7: mostrar conteo de baches (ndet), no el area
                med=d["ndet"] if cod==7 else d["area"]
                is_m=(gv==2)
                p0=p1=p2=p3=""
                if is_m and pt>0:
                    if cn==0:p0=f"{pt:.2f}"
                    elif cn==1:p1=f"{pt:.2f}"
                    elif cn==2:p2=f"{pt:.2f}"
                    elif cn==3:p3=f"{pt:.2f}"
                tabla_rows.append({
                    "cod":cod,"clas":clas,"nombre":nombre,"grav":gv,"unidad":unid,
                    "medidas":round(med,3) if med>0 else "",
                    "ancho_s":round(aw_cod,2) if aw_cod>0 else "",
                    "largo_s":round(lw_cod,2) if lw_cod>0 else "",
                    "area_s":round(As_cod,2) if As_cod>0 else "",
                    "efij":f"{d['efij']:.2f}%" if d["efij"]>0 else "0.00%",
                    "efp":f"{efp_v:.2f}" if is_m else "",
                    "p0":p0,"p1":p1,"p2":p2,"p3":p3,
                    "resultante":f"{pt:.2f}" if is_m and pt>0 else "",
                    "_cn":cn,"_cl":cl,"_pt":pt,"_med":is_m,
                })

            resumen.append({
                "codigo":cod,"nombre":nombre,"clas":clas,
                "n_reg":len(gc),
                "n_bach":nb if cod==7 else None,
                "area_tot":round(sum(dg[g]["area"] for g in[1,2,3]),3),
                "area_sec":round(As_cod,3),
                "efp_pct":round(efp_v,3),
                "cond_num":cn,"cond_lbl":cl,"puntaje":pt,
            })
            for gv in[1,2,3]:
                d=dg[gv]
                rg=[(d["area"],d["efij"])] if d["area"]>0 else []
                detalle.append({
                    "codigo":cod,"nombre":nombre,"clas":clas,
                    "grav":gv,"grav_lbl":GRAVEDADES.get(gv,str(gv)),
                    "n_reg":len(gc[gc["grav_norm"]==gv]),
                    "area_f":round(d["area"],3),"area_s":round(d["as"],3),
                    "efij":round(d["efij"],3),
                    "efp_g":round(cls.efp(rg),3),
                    "cn":cn,"cl":cl,"pt":pt,
                })

        idx=round(max(0.0,1000.0-suma),2)
        clbl,ccol=clasif_indice(idx)
        glob={"indice":idx,"suma":round(suma,3),"cond":clbl,"color":ccol,
              "n":len(dw),"tipos":dw["codigo_falla"].nunique()}
        return tabla_rows,detalle,resumen,glob,dw


# ═══════════════════════════════════════════════════════════════════════════
# TABLA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

class TablaMTC(tk.Frame):
    COLS = [
        ("clas",    "Clas.",              52,  "center"),
        ("cod",     "Cod.",               42,  "center"),
        ("nombre",  "Deterioro / Falla", 228,  "w"),
        ("grav",    "G",                  32,  "center"),
        ("medidas", "Medidas",            88,  "center"),
        ("ancho_s", "Ancho Secc. (m)",   110,  "center"),
        ("largo_s", "Largo Secc. (m)",   110,  "center"),
        ("area_s",  "Area As (m2)",      104,  "center"),
        ("efij",    "EFij (%)",           84,  "center"),
        ("efp",     "EFp pond.",          92,  "center"),
        ("p0",      "P0: Sin det.",       98,  "center"),
        ("p1",      "P1: Leve <10%",     112,  "center"),
        ("p2",      "P2: Mod 10-30%",    122,  "center"),
        ("p3",      "P3: Sev >=30%",     114,  "center"),
        ("res",     "Puntaje Result.",   120,  "center"),
    ]

    def __init__(self, parent):
        super().__init__(parent, bg=C["card"], highlightbackground=C["card_edge"], highlightthickness=1, bd=0)
        self._build()

    def _build(self):
        self.cv=tk.Canvas(self,bg=C["panel"],height=34,highlightthickness=0)
        self.cv.pack(fill="x")

        fw=tk.Frame(self,bg=C["card"]); fw.pack(fill="both",expand=True)
        cols=[c[0] for c in self.COLS]
        self.tree=ttk.Treeview(fw,columns=cols,show="headings",style="MTC.Treeview")
        for cid,lbl,w,anc in self.COLS:
            self.tree.heading(cid,text=lbl)
            self.tree.column(cid,width=w,anchor=anc,minwidth=w-4,stretch=False)

        vsb=ttk.Scrollbar(fw,orient="vertical",  command=self.tree.yview)
        hsb=ttk.Scrollbar(fw,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set,xscrollcommand=hsb.set)
        self.tree.grid(row=0,column=0,sticky="nsew")
        vsb.grid(row=0,column=1,sticky="ns")
        hsb.grid(row=1,column=0,sticky="ew")
        fw.rowconfigure(0,weight=1); fw.columnconfigure(0,weight=1)

        self.tree.tag_configure("E",  background=C["table_e"])
        self.tree.tag_configure("S",  background=C["table_s"])
        self.tree.tag_configure("B",  background=C["table_b"])
        self.tree.tag_configure("mE", background=C["table_me"],foreground=C["accent4"])
        self.tree.tag_configure("mS", background=C["table_ms"],foreground=C["accent4"])
        self.tree.tag_configure("mB", background=C["table_mb"],foreground=C["accent4"])
        self.tree.tag_configure("sep",background=C["panel"],foreground=C["panel"])
        self.tree.tag_configure("tot",background=C["panel"],foreground=C["accent2"],
                                 font=("Segoe UI",9,"bold"))
        self.tree.tag_configure("p1t",foreground=C["accent3"])
        self.tree.tag_configure("p2t",foreground=C["accent4"])
        self.tree.tag_configure("p3t",foreground=C["danger"])

        self.tree.bind("<Configure>", lambda e: self.after(60,self._superhead))
        self.cv.bind("<Configure>",   lambda e: self.after(60,self._superhead))

    def _superhead(self):
        c=self.cv; c.delete("all")
        W=c.winfo_width(); H=34
        if W<10: return
        xs=[0]
        for cid,_,_,_ in self.COLS:
            xs.append(xs[-1]+self.tree.column(cid,"width"))
        grupos=[
            # Solo mostrar el grupo grande; las columnas simples
            # ya tienen etiqueta en el encabezado del Treeview
            ("Puntaje de condicion segun extension de cada tipo de deterioro / falla", 10,14,True),
        ]
        for txt,ci,cf,grande in grupos:
            if cf>len(xs)-1: continue
            x0=xs[ci]; x1=xs[cf]; cx=(x0+x1)/2
            bg=C["panel"] if grande else C["panel_soft"]
            fg=C["accent2"] if grande else C["text_dim"]
            c.create_rectangle(x0+1,1,x1-1,H-1,fill=bg,outline=C["border"])
            c.create_text(cx,H//2,text=txt,fill=fg,
                          font=("Segoe UI",7,"bold" if grande else "normal"),
                          justify="center",width=max(24,x1-x0-4))

    def poblar(self, rows, suma, fallas_ok=None, gravs_ok=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        if not rows: return
        fok=set(fallas_ok) if fallas_ok else set(FALLAS_MTC.keys())
        gok=set(gravs_ok)  if gravs_ok  else {1,2,3}
        prev=None
        for r in rows:
            if r["cod"] not in fok: continue
            if r["grav"] not in gok: continue
            if prev is not None and r["cod"]!=prev:
                self.tree.insert("","end",values=tuple([""]*15),tags=("sep",))
            prev=r["cod"]
            clas=r["clas"]; is_m=r["_med"]; cn=r["_cn"]
            tag="m"+clas if is_m else clas
            tags=(tag,)
            if is_m and cn==1: tags=(tag,"p1t")
            elif is_m and cn==2: tags=(tag,"p2t")
            elif is_m and cn==3: tags=(tag,"p3t")
            self.tree.insert("","end",values=(
                clas,r["cod"],r["nombre"],f"G{r['grav']}",
                r["medidas"] if r["medidas"]!="" else "-",
                r["ancho_s"] if r["ancho_s"]!="" else "",
                r["largo_s"] if r["largo_s"]!="" else "",
                r["area_s"]  if r["area_s"]!=""  else "",
                r["efij"],r["efp"],
                r["p0"],r["p1"],r["p2"],r["p3"],r["resultante"],
            ),tags=tags)
        self.tree.insert("","end",values=(
            "","",">> SUMA TOTAL","","","","","","","",
            "","","","",f"{suma:.2f}"),tags=("tot",))
        self.after(120,self._superhead)


# ═══════════════════════════════════════════════════════════════════════════
# PANEL FILTROS
# ═══════════════════════════════════════════════════════════════════════════

class PanelProgresivas(tk.Frame):
    MODOS = {
        "Todo el archivo": "todo",
        "Rango manual": "manual",
        "Tramos detectados": "tramos",
        "Bloques automaticos": "bloques",
    }

    def __init__(self, parent):
        super().__init__(parent, bg=C["card"], highlightbackground=C["card_edge"], highlightthickness=1, bd=0)
        self.df = None
        self.cols = []
        self.tramos = []
        self.bloques = []
        self._build()

    def _build(self):
        tk.Label(self, text="  PROGRESIVAS", bg=C["card"], fg=C["accent"], font=FH).pack(anchor="w", pady=(6, 3), padx=6)
        body = tk.Frame(self, bg=C["card"])
        body.pack(fill="x", padx=8, pady=(0, 6))

        tk.Label(body, text="Columna:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=0, column=0, sticky="w")
        self.v_col = tk.StringVar(value="(auto)")
        self.cb_col = ttk.Combobox(body, textvariable=self.v_col, values=["(auto)", "(ninguna)"], width=28, state="readonly", font=FB)
        self.cb_col.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(4, 8), pady=1)
        self.cb_col.bind("<<ComboboxSelected>>", lambda e: self._detectar_bloques(silent=True))

        tk.Label(body, text="Modo:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=1, column=0, sticky="w")
        self.v_modo = tk.StringVar(value="Todo el archivo")
        self.cb_modo = ttk.Combobox(body, textvariable=self.v_modo, values=list(self.MODOS.keys()), width=20, state="readonly", font=FB)
        self.cb_modo.grid(row=1, column=1, sticky="w", padx=(4, 8), pady=1)

        tk.Label(body, text="Desde:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=2, column=0, sticky="w")
        self.v_ini = tk.StringVar()
        ent_ini=tk.Entry(body, textvariable=self.v_ini, width=12, font=FB)
        style_entry(ent_ini)
        ent_ini.grid(row=2, column=1, sticky="w", padx=(4, 8), pady=1, ipady=3)

        tk.Label(body, text="Hasta:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=2, column=2, sticky="w")
        self.v_fin = tk.StringVar()
        ent_fin=tk.Entry(body, textvariable=self.v_fin, width=12, font=FB)
        style_entry(ent_fin)
        ent_fin.grid(row=2, column=3, sticky="w", padx=(4, 0), pady=1, ipady=3)

        tk.Label(body, text="Bloque (m):", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=3, column=0, sticky="w")
        self.v_bloque = tk.StringVar(value="200")
        ent_bloque=tk.Entry(body, textvariable=self.v_bloque, width=12, font=FB)
        style_entry(ent_bloque)
        ent_bloque.grid(row=3, column=1, sticky="w", padx=(4, 8), pady=1, ipady=3)
        btn_detectar=make_button(body, "Detectar tramos / bloques", self._detectar_bloques,
            variant="quiet", font=FS, padx=10, pady=4)
        btn_detectar.grid(row=3, column=2, columnspan=2, sticky="w", padx=(4, 0), pady=1)

        tk.Label(body, text="Tramo inicial:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=4, column=0, sticky="w")
        self.v_tramo_ini = tk.StringVar()
        self.cb_tramo_ini = ttk.Combobox(body, textvariable=self.v_tramo_ini, values=[], width=16, state="readonly", font=FB)
        self.cb_tramo_ini.grid(row=4, column=1, sticky="ew", padx=(4, 8), pady=1)

        tk.Label(body, text="Tramo final:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=4, column=2, sticky="w")
        self.v_tramo_fin = tk.StringVar()
        self.cb_tramo_fin = ttk.Combobox(body, textvariable=self.v_tramo_fin, values=[], width=16, state="readonly", font=FB)
        self.cb_tramo_fin.grid(row=4, column=3, sticky="ew", padx=(4, 0), pady=1)

        tk.Label(body, text="Bloque:", bg=C["card"], fg=C["text_dim"], font=FS).grid(row=5, column=0, sticky="w")
        self.v_bloque_sel = tk.StringVar()
        self.cb_bloque = ttk.Combobox(body, textvariable=self.v_bloque_sel, values=[], width=36, state="readonly", font=FB)
        self.cb_bloque.grid(row=5, column=1, columnspan=3, sticky="ew", padx=(4, 0), pady=1)

        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)

        self.li = tk.Label(self, text="  Sin analisis por progresiva.", bg=C["card"], fg=C["text_dim"], font=FS, justify="left")
        self.li.pack(fill="x", padx=8, pady=(0, 6))

    def configurar(self, df=None, mapeo=None):
        self.df = df
        self.cols = list(df.columns) if df is not None else []
        opts = ["(auto)", "(ninguna)"] + self.cols
        self.cb_col.configure(values=opts)

        col_mapeada = None
        if mapeo:
            col_mapeada = mapeo.get("archivo_progresiva")
            if col_mapeada in ("(ninguna)", "", None) or col_mapeada not in opts:
                col_mapeada = None
        col_auto = col_mapeada or AnalizadorProgresivas.detectar_columna(df)
        actual = self.v_col.get()
        if col_mapeada:
            self.v_col.set(col_mapeada)
        elif actual not in opts:
            self.v_col.set(col_auto or "(auto)")
        elif actual == "(auto)" and col_auto:
            self.v_col.set("(auto)")
        self._detectar_bloques(silent=True)

    def resetear(self):
        self.df = None
        self.cols = []
        self.tramos = []
        self.bloques = []
        self.v_col.set("(auto)")
        self.v_modo.set("Todo el archivo")
        self.v_ini.set("")
        self.v_fin.set("")
        self.v_bloque.set("200")
        self.v_tramo_ini.set("")
        self.v_tramo_fin.set("")
        self.v_bloque_sel.set("")
        self.cb_tramo_ini.configure(values=[])
        self.cb_tramo_fin.configure(values=[])
        self.cb_bloque.configure(values=[])
        self.li.config(text="  Sin analisis por progresiva.", fg=C["text_dim"])

    def _columna_actual(self):
        val = self.v_col.get()
        if val == "(ninguna)":
            return None
        if val == "(auto)":
            return AnalizadorProgresivas.detectar_columna(self.df)
        return val or None

    def _parse_limites(self):
        ini_txt = self.v_ini.get().strip()
        fin_txt = self.v_fin.get().strip()
        ini = prog_a_metros(ini_txt) if ini_txt else None
        fin = prog_a_metros(fin_txt) if fin_txt else None
        if ini is not None and fin is not None and fin <= ini:
            raise ValueError("La progresiva final debe ser mayor que la inicial.")
        return ini, fin

    def _parse_bloque(self):
        txt = self.v_bloque.get().strip()
        if not txt:
            return 200
        tam = int(float(txt.replace(",", ".")))
        if tam <= 0:
            raise ValueError("El bloque debe ser mayor que cero.")
        return tam

    def _detectar_bloques(self, silent=False):
        self.tramos = []
        self.bloques = []
        self.v_tramo_ini.set("")
        self.v_tramo_fin.set("")
        self.v_bloque_sel.set("")
        self.cb_tramo_ini.configure(values=[])
        self.cb_tramo_fin.configure(values=[])
        self.cb_bloque.configure(values=[])
        if self.df is None or self.df.empty:
            self.li.config(text="  Cargue un Excel para detectar progresivas.", fg=C["text_dim"])
            return
        col = self._columna_actual()
        if not col:
            self.li.config(text="  Seleccione la columna con el nombre del archivo o imagen.", fg=C["warn"])
            return
        try:
            ini, fin = self._parse_limites()
            tam = self._parse_bloque()
            tramos, _ = AnalizadorProgresivas.tramos_disponibles(self.df, col, ini, fin)
            bloques, base = AnalizadorProgresivas.bloques_disponibles(self.df, col, tam, ini, fin)
        except Exception as e:
            if not silent:
                messagebox.showerror("Progresivas", str(e), parent=self.winfo_toplevel())
            self.li.config(text=f"  {e}", fg=C["danger"])
            return
        if base.empty:
            self.li.config(text=f"  No se detectaron progresivas validas en '{col}'.", fg=C["warn"])
            return
        self.tramos = tramos
        tramo_labels = [t["label"] for t in tramos]
        self.cb_tramo_ini.configure(values=tramo_labels)
        self.cb_tramo_fin.configure(values=tramo_labels)
        if tramo_labels:
            self.v_tramo_ini.set(tramo_labels[0])
            self.v_tramo_fin.set(tramo_labels[-1])
        self.bloques = bloques
        labels = [b["label"] for b in bloques]
        self.cb_bloque.configure(values=labels)
        if labels:
            self.v_bloque_sel.set(labels[0])
            self.li.config(
                text=(
                    f"  Columna: {col}  |  Tramos detectados: "
                    f"{len(tramo_labels)}  |  "
                    f"Bloques: {len(labels)}"
                ),
                fg=C["accent3"],
            )
        else:
            self.li.config(
                text=(
                    f"  Columna: {col}  |  Tramos detectados: {len(tramo_labels)}  |  "
                    f"No se generaron bloques para {tam} m."
                ),
                fg=C["warn"],
            )

    def _buscar_tramo(self, label):
        if not label:
            return None
        for item in self.tramos:
            if item["label"] == label:
                return item
        return None

    def obtener_config(self):
        ini, fin = self._parse_limites()
        tam = self._parse_bloque()
        modo = self.MODOS.get(self.v_modo.get(), "todo")
        bloque = None
        if self.v_bloque_sel.get():
            for item in self.bloques:
                if item["label"] == self.v_bloque_sel.get():
                    bloque = item
                    break
        return {
            "modo": modo,
            "columna": self._columna_actual(),
            "ini": ini,
            "fin": fin,
            "tam_bloque": tam,
            "bloque": bloque,
            "tramo_ini": self._buscar_tramo(self.v_tramo_ini.get()),
            "tramo_fin": self._buscar_tramo(self.v_tramo_fin.get()),
        }


class PanelFiltros(tk.Frame):
    def __init__(self,parent,cb):
        super().__init__(parent,bg=C["card"],highlightbackground=C["card_edge"],highlightthickness=1,bd=0)
        self.cb=cb; self._build()
    def _build(self):
        tk.Label(self,text="  FILTROS",bg=C["card"],fg=C["accent"],font=FH).pack(anchor="w",pady=(6,3),padx=6)
        g=tk.Frame(self,bg=C["card"]); g.pack(fill="x",pady=(0,6),padx=8)
        tk.Label(g,text="Fallas:",bg=C["card"],fg=C["text_dim"],font=FS).grid(row=0,column=0,sticky="nw",padx=(0,10))
        ff=tk.Frame(g,bg=C["card"]); ff.grid(row=0,column=1,sticky="w")
        self.vf={}
        col_clas={"E":C["accent2"],"S":C["accent3"],"B":C["accent4"]}
        for idx,(cod,nm) in enumerate(FALLAS_MTC.items()):
            v=tk.BooleanVar(value=True); self.vf[cod]=v
            r,c=idx//3,idx%3
            cl=CLASIFICACION.get(cod,""); fg=col_clas.get(cl,C["text"])
            tk.Checkbutton(ff,text=f"[{cl}]{cod}.{nm[:18]}",variable=v,
                bg=C["card"],fg=fg,selectcolor=C["card_alt"],
                activebackground=C["card"],activeforeground=fg,
                font=FS,anchor="w",command=self._ch).grid(row=r,column=c,sticky="w",padx=4,pady=1)
        tk.Label(g,text="Gravedad:",bg=C["card"],fg=C["text_dim"],font=FS).grid(row=1,column=0,sticky="nw",padx=(0,10),pady=(4,0))
        gvf=tk.Frame(g,bg=C["card"]); gvf.grid(row=1,column=1,sticky="w",pady=(4,0))
        self.vg={}
        for gv,lbl,col in[(1,"1-Leve",C["accent3"]),(2,"2-Moderado",C["accent4"]),(3,"3-Severo",C["accent"])]:
            v=tk.BooleanVar(value=True); self.vg[gv]=v
            tk.Checkbutton(gvf,text=lbl,variable=v,bg=C["card"],fg=col,
                selectcolor=C["card_alt"],activebackground=C["card"],activeforeground=col,
                font=FB,anchor="w",command=self._ch).pack(side="left",padx=8)
        bf=tk.Frame(self,bg=C["card"]); bf.pack(anchor="e",padx=8,pady=(0,6))
        for txt,val in[("Sel.Todos",True),("Desel.Todos",False)]:
            make_button(bf,txt,lambda v=val:self._all(v),variant="ghost",font=FS,
                padx=10,pady=4).pack(side="left",padx=3)
    def _all(self,v):
        for x in self.vf.values():x.set(v)
        self._ch()
    def _ch(self):self.cb(self.fallas(),self.gravs())
    def fallas(self):return[c for c,v in self.vf.items() if v.get()]
    def gravs(self): return[g for g,v in self.vg.items() if v.get()]
    def get(self):   return self.fallas(),self.gravs()


# ═══════════════════════════════════════════════════════════════════════════
# PANEL RESUMEN
# ═══════════════════════════════════════════════════════════════════════════

class PanelResumen(tk.Frame):
    def __init__(self,parent):
        super().__init__(parent,bg=C["card"],highlightbackground=C["card_edge"],highlightthickness=1,bd=0); self._build()
    def _build(self):
        self.li=tk.Label(self,text="-",bg=C["card"],fg=C["text_dim"],
            font=("Segoe UI",52,"bold"))
        self.li.pack(pady=(12,0))
        tk.Label(self,text="/ 1000",bg=C["card"],fg=C["text_dim"],
            font=("Segoe UI",16)).pack()
        self.lc=tk.Label(self,text="SIN DATOS",bg=C["card"],fg=C["text_dim"],
            font=("Segoe UI",14,"bold"))
        self.lc.pack(pady=(4,0))
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=12,padx=20)
        self.li2=tk.Label(self,text="",bg=C["card"],fg=C["text"],font=FB,justify="left")
        self.li2.pack(anchor="w",padx=26)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=12,padx=20)
        tk.Label(self,text="FORMULA MTC 2018:",
            bg=C["card"],fg=C["text_dim"],font=FS).pack(anchor="w",padx=26)
        tk.Label(self,
            text=("  EFij   = (Aij / As) x 100\n"
                  "  EFp    = S(EFij x Aij) / S(Aij)\n"
                  "  Puntaj = interpolacion lineal s/ EFp\n"
                  "           (o N baches para cod.7)\n"
                  "  Indice = 1000 - S Puntajes"),
            bg=C["card"],fg=C["accent2"],
            font=("Courier New",10,"bold"),justify="left").pack(anchor="w",padx=26,pady=6)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=10,padx=20)
        tk.Label(self,text="ESCALA  (base 1000):",
            bg=C["card"],fg=C["text_dim"],font=FS).pack(anchor="w",padx=26)
        for rango,lbl,col in[
            (" 800-1000","CONDICION BUENO",  C["accent3"]),
            (" 300- 800","CONDICION REGULAR", C["accent4"]),
            ("   0- 299","CONDICION MALO  (<300)",    C["danger"])]:
            f=tk.Frame(self,bg=C["card"]); f.pack(anchor="w",padx=26,pady=2)
            tk.Label(f,text="|",bg=C["card"],fg=col,font=("Consolas",14,"bold")).pack(side="left")
            tk.Label(f,text=f"  {rango}  ->  {lbl}",bg=C["card"],fg=C["text"],
                font=FB).pack(side="left")
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=10,padx=20)
        tk.Label(self,text="CLASIFICACION:",
            bg=C["card"],fg=C["text_dim"],font=FS).pack(anchor="w",padx=26)
        for clas,desc,col in[
            ("E","Deterioros o fallas Estructurales (1-5)",  C["accent2"]),
            ("S","Deterioros o fallas Superficiales (6-9)",  C["accent3"]),
            ("B","BERMAS Pavimentadas y no pavimentadas (10-11)",C["accent4"])]:
            f=tk.Frame(self,bg=C["card"]); f.pack(anchor="w",padx=26,pady=2)
            tk.Label(f,text=f" {clas} ",bg=col,fg=C["text_bright"],
                font=("Segoe UI",10,"bold")).pack(side="left",padx=(0,6))
            tk.Label(f,text=desc,bg=C["card"],fg=C["text"],font=FS).pack(side="left")
        return
        tk.Label(self,text="INDICE DE CONDICION VIAL",
            bg=C["bg2"],fg=C["text_dim"],font=FS).pack(pady=(14,0))
        self.li=tk.Label(self,text="—",bg=C["bg2"],fg=C["text_dim"],
            font=("Consolas",52,"bold")); self.li.pack()
        tk.Label(self,text="/ 1000",bg=C["bg2"],fg=C["text_dim"],
            font=("Consolas",16)).pack()
        self.lc=tk.Label(self,text="SIN DATOS",bg=C["bg2"],fg=C["text_dim"],
            font=("Consolas",14,"bold")); self.lc.pack(pady=(4,0))
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=12,padx=20)
        self.li2=tk.Label(self,text="",bg=C["bg2"],fg=C["text"],font=FB,justify="left")
        self.li2.pack(anchor="w",padx=26)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=12,padx=20)
        tk.Label(self,text="FORMULA MTC 2018:",
            bg=C["bg2"],fg=C["text_dim"],font=FS).pack(anchor="w",padx=26)
        tk.Label(self,
            text=("  EFij   = (Aij / As) x 100\n"
                  "  EFp    = S(EFij x Aij) / S(Aij)\n"
                  "  Puntaj = interpolacion lineal s/ EFp\n"
                  "           (o N baches para cod.7)\n"
                  "  Indice = 1000 - S Puntajes"),
            bg=C["bg2"],fg=C["accent2"],
            font=("Courier New",10,"bold"),justify="left").pack(anchor="w",padx=26,pady=6)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=10,padx=20)
        tk.Label(self,text="ESCALA  (base 1000):",
            bg=C["bg2"],fg=C["text_dim"],font=FS).pack(anchor="w",padx=26)
        for rango,lbl,col in[
            (" 800-1000","CONDICION BUENO",  C["accent3"]),
            (" 300- 800","CONDICION REGULAR", C["accent4"]),
            ("   0- 299","CONDICION MALO  (<300)",    C["danger"])]:
            f=tk.Frame(self,bg=C["bg2"]); f.pack(anchor="w",padx=26,pady=2)
            tk.Label(f,text="█",bg=C["bg2"],fg=col,font=("Consolas",14)).pack(side="left")
            tk.Label(f,text=f"  {rango}  ->  {lbl}",bg=C["bg2"],fg=C["text"],
                font=FB).pack(side="left")
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=10,padx=20)
        tk.Label(self,text="CLASIFICACION:",
            bg=C["bg2"],fg=C["text_dim"],font=FS).pack(anchor="w",padx=26)
        for clas,desc,col in[
            ("E","Deterioros o fallas Estructurales (1-5)",  C["accent2"]),
            ("S","Deterioros o fallas Superficiales (6-9)",  C["accent3"]),
            ("B","BERMAS Pavimentadas y no pavimentadas (10-11)",C["accent4"])]:
            f=tk.Frame(self,bg=C["bg2"]); f.pack(anchor="w",padx=26,pady=2)
            tk.Label(f,text=f" {clas} ",bg=col,fg=C["bg"],
                font=("Consolas",10,"bold")).pack(side="left",padx=(0,6))
            tk.Label(f,text=desc,bg=C["bg2"],fg=C["text"],font=FS).pack(side="left")

    def actualizar(self,g):
        col=g["color"]
        self.li.config(text=f"{g['indice']:.1f}",fg=col)
        self.lc.config(text=g["cond"],fg=col)
        self.li2.config(text=(
            f"  Registros     : {g['n']}\n"
            f"  Tipos falla   : {g['tipos']}\n"
            f"  S Puntajes    : {g['suma']:.3f}\n"
            f"  Indice = 1000-{g['suma']:.3f} = {g['indice']:.2f}\n"
            f"  Fecha         : {datetime.now():%Y-%m-%d %H:%M}"))


# ═══════════════════════════════════════════════════════════════════════════
# TABLA DETALLE
# ═══════════════════════════════════════════════════════════════════════════

class TablaDetalle(tk.Frame):
    COLS=[("cl","Cl.",44),("cod","Cod.",50),("nombre","Tipo de Falla",215),
          ("grav","Gravedad",90),("n","N Reg.",60),
          ("af","Area Falla\n(m2) / N Bach",132),("as","Area Seccion\n(m2)",112),
          ("efij","SEFij\n(%)",75),("efpg","EFp Grav.\n(%)",80),
          ("cn","Cond. Cod.",105),("pt","Puntaje\nCodigo",85)]
    def __init__(self,parent):
        super().__init__(parent,bg=C["card"],highlightbackground=C["card_edge"],highlightthickness=1,bd=0); self._build()
    def _build(self):
        cols=[c[0] for c in self.COLS]
        self.tree=ttk.Treeview(self,columns=cols,show="headings",style="MTC.Treeview")
        for cid,lbl,w in self.COLS:
            self.tree.heading(cid,text=lbl)
            self.tree.column(cid,width=w,anchor="center",minwidth=w)
        vsb=ttk.Scrollbar(self,orient="vertical",  command=self.tree.yview)
        hsb=ttk.Scrollbar(self,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set,xscrollcommand=hsb.set)
        self.tree.grid(row=0,column=0,sticky="nsew")
        vsb.grid(row=0,column=1,sticky="ns"); hsb.grid(row=1,column=0,sticky="ew")
        self.rowconfigure(0,weight=1); self.columnconfigure(0,weight=1)
        self.tree.tag_configure("g1",foreground=C["accent3"])
        self.tree.tag_configure("g2",foreground=C["accent4"])
        self.tree.tag_configure("g3",foreground=C["accent"])
    def poblar(self,det):
        for i in self.tree.get_children():self.tree.delete(i)
        for r in det:
            self.tree.insert("","end",values=(
                r["clas"],r["codigo"],r["nombre"],
                f"{r['grav']}-{r['grav_lbl']}",r["n_reg"],
                f"{r['area_f']:.3f}",f"{r['area_s']:.3f}",
                f"{r['efij']:.3f}%",f"{r['efp_g']:.3f}%",
                f"{r['cn']}-{r['cl']}",f"{r['pt']:.3f}"),
                tags=({1:"g1",2:"g2",3:"g3"}.get(r["grav"],"g1"),))


# ═══════════════════════════════════════════════════════════════════════════
# VALIDACION NOMBRES
# ═══════════════════════════════════════════════════════════════════════════

class VentanaValidacion(tk.Toplevel):
    def __init__(self,parent,df,col_nom,col_cod,cb):
        super().__init__(parent)
        self.df=df;self.col_nom=col_nom;self.col_cod=col_cod;self.cb=cb;self.filas=[]
        self.title("Validacion de Nombres MTC 2018")
        self.configure(bg=C["bg"]); self.geometry("1040x600"); self.grab_set()
        self._build(); self._cargar()
        self.update_idletasks()
        x=parent.winfo_x()+(parent.winfo_width()-self.winfo_width())//2
        y=parent.winfo_y()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _build(self):
        hdr=tk.Frame(self,bg=C["bg2"],pady=10);hdr.pack(fill="x")
        tk.Label(hdr,text="VALIDACION DE NOMBRES DE FALLA",
            bg=C["bg2"],fg=C["accent4"],font=FT).pack(side="left",padx=20)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        ley=tk.Frame(self,bg=C["bg"],padx=16,pady=6);ley.pack(fill="x")
        for ic,col,tx in[("✓",C["accent3"],"Exacto"),("≈",C["accent4"],"Similar"),("✗",C["danger"],"No encontrado")]:
            f=tk.Frame(ley,bg=C["bg"]);f.pack(side="left",padx=12)
            tk.Label(f,text=ic,bg=C["bg"],fg=col,font=("Consolas",12,"bold")).pack(side="left")
            tk.Label(f,text=f" {tx}",bg=C["bg"],fg=C["text_dim"],font=FS).pack(side="left")
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        ch=tk.Frame(self,bg=C["bg2"],padx=8,pady=5);ch.pack(fill="x")
        for txt,w in[("Est.",4),("Nombre Excel",28),("N",5),("Codigo MTC",22),("Nombre MTC",26),("Tipo",14),("Ignorar",8)]:
            tk.Label(ch,text=txt,bg=C["bg2"],fg=C["accent"],font=FH,width=w,anchor="w").pack(side="left",padx=4)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        cont=tk.Frame(self,bg=C["bg"]);cont.pack(fill="both",expand=True)
        canvas=tk.Canvas(cont,bg=C["bg"],highlightthickness=0)
        vsb=ttk.Scrollbar(cont,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left",fill="both",expand=True);vsb.pack(side="right",fill="y")
        self.sf=tk.Frame(canvas,bg=C["bg"])
        self.sw=canvas.create_window((0,0),window=self.sf,anchor="nw")
        canvas.bind("<Configure>",lambda e:canvas.itemconfig(self.sw,width=e.width))
        self.sf.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>",lambda e:canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        foot=tk.Frame(self,bg=C["bg2"],pady=10);foot.pack(fill="x")
        self.lr=tk.Label(foot,text="",bg=C["bg2"],fg=C["text_dim"],font=FS)
        self.lr.pack(side="left",padx=20)
        bf=tk.Frame(foot,bg=C["bg2"]);bf.pack(side="right",padx=20)
        tk.Button(bf,text="Auto-asignar",bg=C["bg3"],fg=C["accent4"],font=FB,
            relief="flat",bd=0,padx=12,pady=5,cursor="hand2",
            command=self._auto).pack(side="left",padx=(0,8))
        tk.Button(bf,text="Cancelar",bg=C["bg3"],fg=C["text_dim"],font=FB,
            relief="flat",bd=0,padx=12,pady=5,cursor="hand2",
            command=self.destroy).pack(side="left",padx=(0,8))
        tk.Button(bf,text="Aplicar correcciones",bg=C["btn"],fg=C["text_bright"],
            font=FH,relief="flat",bd=0,padx=16,pady=5,cursor="hand2",
            command=self._aplicar).pack(side="left")

    def _cargar(self):
        nrs=[]
        if self.col_nom and self.col_nom!="(ninguna)":
            nrs=self.df[self.col_nom].dropna().unique().tolist()
        if not nrs:
            tk.Label(self.sf,text="Sin nombres.",bg=C["bg"],fg=C["danger"],font=FB).pack(pady=20);return
        n_ex=n_si=n_no=0
        opts=["(ninguna)"]+[f"{cod} - {FALLAS_MTC[cod]}" for cod in FALLAS_MTC]
        for i,nr in enumerate(sorted(nrs,key=str)):
            ns=str(nr).strip(); ce=0
            if self.col_cod and self.col_cod!="(ninguna)":
                mk=self.df[self.col_nom]==nr
                v2=pd.to_numeric(self.df.loc[mk,self.col_cod],errors="coerce").dropna()
                if not v2.empty:ce=int(v2.iloc[0])
            cs,sc,nm=buscar_cod(ns)
            if ce in FALLAS_MTC:cs=ce;nm=FALLAS_MTC[ce];sc=simil(ns,nm)
            ic,cc,et=estado_sc(sc)
            if et=="Exacto":n_ex+=1
            elif et=="Similar":n_si+=1
            else:n_no+=1
            nc=int((self.df[self.col_nom]==nr).sum())
            bg_f=C["bg"] if i%2==0 else C["bg2"]
            ff=tk.Frame(self.sf,bg=bg_f,pady=4);ff.pack(fill="x",padx=4,pady=1)
            tk.Label(ff,text=f" {ic} ",bg=bg_f,fg=cc,font=("Consolas",12,"bold"),width=4,anchor="center").pack(side="left",padx=4)
            tk.Label(ff,text=ns,bg=bg_f,fg=C["text"],font=FB,width=28,anchor="w").pack(side="left",padx=4)
            tk.Label(ff,text=str(nc),bg=bg_f,fg=C["text_dim"],font=FS,width=4,anchor="center").pack(side="left",padx=4)
            vc=tk.StringVar()
            if cs in FALLAS_MTC:vc.set(f"{cs} - {FALLAS_MTC[cs]}")
            else:vc.set("(ninguna)")
            cb2=ttk.Combobox(ff,textvariable=vc,values=opts,width=22,state="readonly",font=FB)
            cb2.pack(side="left",padx=6)
            ln=tk.Label(ff,text=nm[:28] if nm else "—",bg=bg_f,fg=C["accent2"],font=FS,width=26,anchor="w")
            ln.pack(side="left",padx=4)
            tm=UNIDAD.get(cs,"?")
            lt=tk.Label(ff,text=f"{CLASIFICACION.get(cs,'?')} | {tm}",bg=bg_f,fg=C["accent3"],font=FS,width=14,anchor="w")
            lt.pack(side="left",padx=4)
            vi=tk.BooleanVar(value=False)
            tk.Checkbutton(ff,variable=vi,bg=bg_f,fg=C["danger"],selectcolor=C["bg3"],
                activebackground=bg_f,text="Ignorar",font=FS).pack(side="left",padx=6)
            tk.Label(ff,text=f" {sc:3d}%",bg=bg_f,fg=cc,font=FS).pack(side="left",padx=2)
            def _oc(ev,vc2=vc,ln2=ln,lt2=lt,bg2=bg_f):
                s=vc2.get()
                if s and s!="(ninguna)":
                    try:
                        cd=int(s.split("-")[0].strip())
                        ln2.config(text=FALLAS_MTC.get(cd,"")[:28])
                        lt2.config(text=f"{CLASIFICACION.get(cd,'?')} | {UNIDAD.get(cd,'?')}")
                    except:pass
                else:ln2.config(text="—");lt2.config(text="—")
            cb2.bind("<<ComboboxSelected>>",_oc)
            self.filas.append((ns,vc,vi,sc,et))
        self.lr.config(text=f"  Exactos:{n_ex}  Similares:{n_si}  No encontrados:{n_no}")

    def _auto(self):
        for ns,vc,vi,sc,et in self.filas:
            if et=="Similar" and sc>=60:
                c,_,_=buscar_cod(ns)
                if c in FALLAS_MTC:vc.set(f"{c} - {FALLAS_MTC[c]}")
        messagebox.showinfo("Auto","Codigos asignados (>=60%).",parent=self)

    def _aplicar(self):
        ov={};ign=[];sc2=[]
        for ns,vc,vi,sc,et in self.filas:
            if vi.get():ign.append(ns);continue
            s=vc.get()
            if s and s!="(ninguna)":
                try:ov[ns]=int(s.split("-")[0].strip())
                except:sc2.append(ns)
            else:sc2.append(ns)
        if sc2:
            if not messagebox.askyesno("Sin codigo",
                f"Sin codigo:\n{chr(10).join(sc2[:5])}\n\n¿Continuar?",parent=self):return
        self.destroy();self.cb(ov,ign)


# ═══════════════════════════════════════════════════════════════════════════
# VALIDACION GRAVEDADES
# ═══════════════════════════════════════════════════════════════════════════

GRAVEDADES_VALIDAS = {
    "1":"Leve","2":"Moderado","3":"Severo",
    "L":"Leve","M":"Moderado","S":"Severo",
    "LEVE":"Leve","MODERADO":"Moderado","SEVERO":"Severo",
}

def estado_grav(val_raw):
    """Devuelve (icono, color, texto_estado, norm) para un valor de gravedad."""
    if val_raw is None or (isinstance(val_raw,float) and math.isnan(val_raw)):
        return "✗",C["danger"],"Vacío",None
    s=str(val_raw).strip().upper()
    if s in GRAVEDADES_VALIDAS:
        g=norm_grav(val_raw)
        lbl=GRAVEDADES.get(g,s)
        return "✓",C["accent3"],f"{g} - {lbl}",g
    return "✗",C["danger"],f'No reconocido: "{val_raw}"',None

class VentanaValidacionGravedad(tk.Toplevel):
    """
    Ventana para verificar los valores únicos de la columna gravedad,
    análoga a VentanaValidacion para nombres de falla.
    Permite reasignar manualmente cualquier valor no reconocido.
    """
    def __init__(self,parent,df,col_grav,cb):
        super().__init__(parent)
        self.df=df; self.col_grav=col_grav; self.cb=cb; self.filas=[]
        self.title("Validacion de Gravedades MTC 2018")
        self.configure(bg=C["bg"]); self.geometry("860x480"); self.grab_set()
        self._build(); self._cargar()
        self.update_idletasks()
        x=parent.winfo_x()+(parent.winfo_width()-self.winfo_width())//2
        y=parent.winfo_y()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _build(self):
        hdr=tk.Frame(self,bg=C["bg2"],pady=10); hdr.pack(fill="x")
        tk.Label(hdr,text="VALIDACION DE GRAVEDADES",
            bg=C["bg2"],fg=C["accent4"],font=FT).pack(side="left",padx=20)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        # Leyenda
        ley=tk.Frame(self,bg=C["bg"],padx=16,pady=6); ley.pack(fill="x")
        for ic,col,tx in[("✓",C["accent3"],"Reconocido"),("✗",C["danger"],"No reconocido / Vacío")]:
            f=tk.Frame(ley,bg=C["bg"]); f.pack(side="left",padx=12)
            tk.Label(f,text=ic,bg=C["bg"],fg=col,font=("Consolas",12,"bold")).pack(side="left")
            tk.Label(f,text=f" {tx}",bg=C["bg"],fg=C["text_dim"],font=FS).pack(side="left")
        tk.Label(ley,text="  Valores válidos: 1/L/Leve | 2/M/Moderado | 3/S/Severo",
            bg=C["bg"],fg=C["accent2"],font=FS).pack(side="left",padx=20)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        # Cabecera columnas
        ch=tk.Frame(self,bg=C["bg2"],padx=8,pady=5); ch.pack(fill="x")
        for txt,w in[("Est.",4),("Valor en Excel",20),("N filas",7),
                     ("Estado MTC",18),("Corregir a",16),("Ignorar",8)]:
            tk.Label(ch,text=txt,bg=C["bg2"],fg=C["accent"],font=FH,
                width=w,anchor="w").pack(side="left",padx=4)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        # Área scrollable
        cont=tk.Frame(self,bg=C["bg"]); cont.pack(fill="both",expand=True)
        cv=tk.Canvas(cont,bg=C["bg"],highlightthickness=0)
        vsb=ttk.Scrollbar(cont,orient="vertical",command=cv.yview)
        cv.configure(yscrollcommand=vsb.set)
        cv.pack(side="left",fill="both",expand=True); vsb.pack(side="right",fill="y")
        self.sf=tk.Frame(cv,bg=C["bg"])
        self.sw=cv.create_window((0,0),window=self.sf,anchor="nw")
        cv.bind("<Configure>",lambda e:cv.itemconfig(self.sw,width=e.width))
        self.sf.bind("<Configure>",lambda e:cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<MouseWheel>",lambda e:cv.yview_scroll(int(-1*(e.delta/120)),"units"))
        # Footer
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        foot=tk.Frame(self,bg=C["bg2"],pady=10); foot.pack(fill="x")
        self.lr=tk.Label(foot,text="",bg=C["bg2"],fg=C["text_dim"],font=FS)
        self.lr.pack(side="left",padx=20)
        bf=tk.Frame(foot,bg=C["bg2"]); bf.pack(side="right",padx=20)
        tk.Button(bf,text="Cancelar",bg=C["bg3"],fg=C["text_dim"],font=FB,
            relief="flat",bd=0,padx=12,pady=5,cursor="hand2",
            command=self.destroy).pack(side="left",padx=(0,8))
        tk.Button(bf,text="Aplicar correcciones",bg=C["btn"],fg=C["text_bright"],
            font=FH,relief="flat",bd=0,padx=16,pady=5,cursor="hand2",
            command=self._aplicar).pack(side="left")

    def _cargar(self):
        if not self.col_grav or self.col_grav=="(ninguna)":
            tk.Label(self.sf,text="Columna de gravedad no seleccionada.",
                bg=C["bg"],fg=C["danger"],font=FB).pack(pady=20); return
        vals=self.df[self.col_grav].dropna().unique().tolist()
        # También incluir NaN si hay filas sin valor
        n_nan=int(self.df[self.col_grav].isna().sum())
        n_ok=n_nok=0
        opts=["(ninguna)","1 - Leve","2 - Moderado","3 - Severo"]
        for i,vr in enumerate(sorted(vals,key=str)):
            ic,cc,estado,gn=estado_grav(vr)
            nc=int((self.df[self.col_grav]==vr).sum())
            if gn: n_ok+=1
            else:  n_nok+=1
            bg_f=C["bg"] if i%2==0 else C["bg2"]
            ff=tk.Frame(self.sf,bg=bg_f,pady=5); ff.pack(fill="x",padx=4,pady=1)
            tk.Label(ff,text=f" {ic} ",bg=bg_f,fg=cc,
                font=("Consolas",12,"bold"),width=4,anchor="center").pack(side="left",padx=4)
            tk.Label(ff,text=str(vr),bg=bg_f,fg=C["text"],
                font=FB,width=20,anchor="w").pack(side="left",padx=4)
            tk.Label(ff,text=str(nc),bg=bg_f,fg=C["text_dim"],
                font=FS,width=7,anchor="center").pack(side="left",padx=4)
            tk.Label(ff,text=estado,bg=bg_f,fg=cc,
                font=FB,width=18,anchor="w").pack(side="left",padx=4)
            # Combobox solo activo si no reconocido
            vc=tk.StringVar(value="(ninguna)" if not gn else f"{gn} - {GRAVEDADES[gn]}")
            state="readonly" if not gn else "disabled"
            cb2=ttk.Combobox(ff,textvariable=vc,values=opts,width=16,state=state,font=FB)
            cb2.pack(side="left",padx=8)
            vi=tk.BooleanVar(value=False)
            tk.Checkbutton(ff,variable=vi,bg=bg_f,fg=C["danger"],selectcolor=C["bg3"],
                activebackground=bg_f,text="Ignorar",font=FS).pack(side="left",padx=6)
            self.filas.append((vr,vc,vi,gn))
        if n_nan>0:
            n_nok+=1
            bg_f=C["bg2"]
            ff=tk.Frame(self.sf,bg=bg_f,pady=5); ff.pack(fill="x",padx=4,pady=1)
            tk.Label(ff,text=" ✗ ",bg=bg_f,fg=C["danger"],
                font=("Consolas",12,"bold"),width=4).pack(side="left",padx=4)
            tk.Label(ff,text="(vacío / NaN)",bg=bg_f,fg=C["text"],
                font=FB,width=20,anchor="w").pack(side="left",padx=4)
            tk.Label(ff,text=str(n_nan),bg=bg_f,fg=C["text_dim"],
                font=FS,width=7,anchor="center").pack(side="left",padx=4)
            tk.Label(ff,text="Vacío → se asignará Leve(1)",
                bg=bg_f,fg=C["accent4"],font=FS,width=26,anchor="w").pack(side="left",padx=4)
        self.lr.config(text=f"  Reconocidos: {n_ok}   No reconocidos: {n_nok}   (NaN: {n_nan})")

    def _aplicar(self):
        overrides={}; ign=[]
        for vr,vc,vi,gn in self.filas:
            if vi.get(): ign.append(vr); continue
            if gn: continue  # ya reconocido, no necesita override
            s=vc.get()
            if s and s!="(ninguna)":
                try: overrides[str(vr)]=int(s.split("-")[0].strip())
                except: pass
        self.destroy(); self.cb(overrides,ign)


# ═══════════════════════════════════════════════════════════════════════════
# MAPEO COLUMNAS
# ═══════════════════════════════════════════════════════════════════════════

class VentanaMapeo(tk.Toplevel):
    CAMPOS=[
        ("codigo_falla",  "Codigo de Falla (1-11)",       "Numero del tipo de falla"),
        ("nombre_falla",  "Nombre de Falla  !",           "Descripcion textual"),
        ("gravedad",      "Gravedad (1/2/3 o L/M/S)",     "1=Leve 2=Moderado 3=Severo"),
        ("archivo_progresiva", "Archivo / Imagen",        "Nombre del tif para detectar progresivas"),
        ("ancho_falla",   "Ancho de Falla (m)",           "Ancho del deterioro"),
        ("largo_falla",   "Largo de Falla (m)",           "Largo del deterioro"),
        ("area_falla",    "Area/Medida Falla  [N Baches si cod.7]", "m2 para fallas; und para Baches (Huecos)"),
        ("num_deterioros","* N Deterioros (opcional, prioridad cod.7)",    "Si se mapea, tiene prioridad sobre area para baches"),
        ("ancho_seccion", "Ancho Seccion Evaluada (m)",   "Ancho total de la seccion"),
        ("largo_seccion", "Largo Seccion Evaluada (m)",   "Largo total de la seccion"),
        ("area_seccion",  "Area Seccion As (m2)",         "Area total de la seccion"),
    ]
    KW={
        "codigo_falla":   ["cod","codigo","code"],
        "nombre_falla":   ["nombre","name","falla","descripcion","tipo"],
        "gravedad":       ["grav","sever","nivel"],
        "archivo_progresiva": ["archivo","file","imagen","image","ruta","path","tif","frame"],
        "ancho_falla":    ["ancho_f","width_f"],
        "largo_falla":    ["largo_f","length_f"],
        "area_falla":     ["area_f","aij","area deterioro","medida"],
        "num_deterioros": ["num_det","nbaches","n_bach","cantidad","num bach"],
        "ancho_seccion":  ["ancho_s","ancho sec"],
        "largo_seccion":  ["largo_s","largo sec"],
        "area_seccion":   ["area_s","area sec","as "],
    }
    def __init__(self,parent,cols,cb,df=None,area_global_inicial=0.0):
        super().__init__(parent)
        self.cols=cols;self.cb=cb;self.df=df
        self._area_global_ini=area_global_inicial
        self.ov={};self.ign=[];self.vs={}
        self.ov_grav={};self.ign_grav=[]
        self.title("Mapeo de Columnas")
        self.configure(bg=C["bg"]);self.resizable(True,False);self.grab_set()
        self._build()
        self.update_idletasks()
        pw=parent.winfo_x()+(parent.winfo_width()-self.winfo_width())//2
        ph=parent.winfo_y()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{max(0,pw)}+{max(0,ph)}")

    def _build(self):
        hdr=tk.Frame(self,bg=C["bg2"],pady=12);hdr.pack(fill="x")
        tk.Label(hdr,text="MAPEO DE COLUMNAS DEL EXCEL",
            bg=C["bg2"],fg=C["accent2"],font=FT).pack(side="left",padx=20)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        body=tk.Frame(self,bg=C["bg"],padx=20,pady=14);body.pack(fill="both",expand=True)
        opts=["(ninguna)"]+list(self.cols)
        for ci,(tx,w) in enumerate([("CAMPO REQUERIDO",38),("COLUMNA EN EL EXCEL",30),("DESCRIPCION",48)]):
            tk.Label(body,text=tx,bg=C["bg"],fg=C["accent"],font=FH,width=w,anchor="w").grid(row=0,column=ci,padx=(0,10),pady=(0,8))
        tk.Frame(body,bg=C["border"],height=1).grid(row=1,column=0,columnspan=3,sticky="ew",pady=(0,8))
        for i,(campo,label,desc) in enumerate(self.CAMPOS):
            row=i+2
            bg2=C["bg"] if i%2==0 else C["bg2"]
            fg2=C["accent4"] if campo in("num_deterioros","area_falla") else C["text"]
            frm=tk.Frame(body,bg=bg2,pady=5)
            frm.grid(row=row,column=0,columnspan=3,sticky="ew",pady=1)
            tk.Label(frm,text=f"  {label}",bg=bg2,fg=fg2,font=FB,width=40,anchor="w").pack(side="left")
            v=tk.StringVar(value="(ninguna)");self.vs[campo]=v
            cb2=ttk.Combobox(frm,textvariable=v,values=opts,width=30,state="readonly",font=FB)
            cb2.pack(side="left",padx=8)
            if campo=="nombre_falla":
                tk.Button(frm,text=" ! ",bg=C["warn"],fg=C["bg"],
                    font=("Consolas",9,"bold"),relief="flat",bd=0,padx=8,pady=3,
                    cursor="hand2",command=self._validar).pack(side="left",padx=4)
                self.le=tk.Label(frm,text="  (sin verificar)",bg=bg2,fg=C["text_dim"],font=FS)
                self.le.pack(side="left")
            if campo=="gravedad":
                tk.Button(frm,text=" ! ",bg=C["ok"],fg=C["text_bright"],
                    font=("Consolas",9,"bold"),relief="flat",bd=0,padx=8,pady=3,
                    cursor="hand2",command=self._validar_grav).pack(side="left",padx=4)
                self.lg=tk.Label(frm,text="  (sin verificar)",bg=bg2,fg=C["text_dim"],font=FS)
                self.lg.pack(side="left")
            for col in self.cols:
                cl=str(col).lower()
                for kw in self.KW.get(campo,[]):
                    if kw in cl:v.set(col);break
            tk.Label(frm,text=f"  <- {desc}",bg=bg2,fg=C["text_dim"],font=FS,anchor="w").pack(side="left")
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x",pady=(5,0))
        foot=tk.Frame(self,bg=C["bg2"],pady=12);foot.pack(fill="x")
        fa=tk.Frame(foot,bg=C["bg2"]);fa.pack(side="left",padx=20)
        tk.Label(fa,text="Area seccion global As(m2):",bg=C["bg2"],fg=C["text_dim"],font=FS).pack(side="left",padx=(0,6))
        ag_init = f"{self._area_global_ini:.2f}" if self._area_global_ini > 0 else ""
        self.vag=tk.StringVar(value=ag_init)
        tk.Entry(fa,textvariable=self.vag,width=14,bg=C["bg3"],fg=C["text"],
            insertbackground=C["text"],font=FB,relief="flat",bd=4).pack(side="left")
        bf=tk.Frame(foot,bg=C["bg2"]);bf.pack(side="right",padx=20)
        tk.Button(bf,text="Cancelar",bg=C["bg3"],fg=C["text_dim"],font=FB,
            relief="flat",bd=0,padx=14,pady=6,cursor="hand2",command=self.destroy).pack(side="left",padx=(0,8))
        tk.Button(bf,text="Aplicar Mapeo",bg=C["btn"],fg=C["text_bright"],font=FH,
            relief="flat",bd=0,padx=18,pady=6,cursor="hand2",command=self._aplicar).pack(side="left")

    def _validar(self):
        cn=self.vs["nombre_falla"].get()
        if cn=="(ninguna)":
            messagebox.showwarning("Aviso","Seleccione primero la columna Nombre de Falla.",parent=self);return
        if self.df is None:
            messagebox.showwarning("Aviso","No hay datos cargados.",parent=self);return
        def rec(ov,ign):
            self.ov=ov;self.ign=ign
            self.le.config(text=f"  {len(ov)} asignados  {len(ign)} ignorados",fg=C["accent3"])
        VentanaValidacion(self,df=self.df,col_nom=cn,
            col_cod=self.vs["codigo_falla"].get(),cb=rec)

    def _validar_grav(self):
        cg=self.vs["gravedad"].get()
        if cg=="(ninguna)":
            messagebox.showwarning("Aviso","Seleccione primero la columna Gravedad.",parent=self);return
        if self.df is None:
            messagebox.showwarning("Aviso","No hay datos cargados.",parent=self);return
        def rec(ov_g,ign_g):
            self.ov_grav=ov_g; self.ign_grav=ign_g
            self.lg.config(
                text=f"  {len(ov_g)} corregidos  {len(ign_g)} ignorados",
                fg=C["accent3"])
        VentanaValidacionGravedad(self,df=self.df,col_grav=cg,cb=rec)

    def _aplicar(self):
        m={campo:v.get() for campo,v in self.vs.items()}
        if m["codigo_falla"]=="(ninguna)" and m["nombre_falla"]=="(ninguna)":
            messagebox.showwarning("Incompleto","Mapee Codigo o Nombre de Falla.",parent=self);return
        if(m["area_falla"]=="(ninguna)" and
           not(m["ancho_falla"]!="(ninguna)" and m["largo_falla"]!="(ninguna)")):
            messagebox.showwarning("Incompleto","Mapee Area de Falla o Ancho+Largo.",parent=self);return
        ag=0.0
        v2=self.vag.get().strip()
        if v2:
            try:ag=float(v2.replace(",","."))
            except:messagebox.showerror("Error","Area global debe ser numero.",parent=self);return
        self.destroy();self.cb(m,ag,self.ov,self.ign,self.ov_grav,self.ign_grav)


# ═══════════════════════════════════════════════════════════════════════════
# VENTANA AYUDA
# ═══════════════════════════════════════════════════════════════════════════

AYUDA="""
GUIA DE USO — ANALISIS DE PAVIMENTOS MTC 2018
================================================
FLUJO: 1.Cargar Excel -> 2.Mapear Columnas -> 3.Analizar -> 4.Exportar

ANALISIS POR PROGRESIVAS
  Puede mapear una columna "Archivo / Imagen" con nombres como:
    TRAMO_01_Progresiva_01+175_01+200_000000.tif
  Luego, en el panel PROGRESIVAS:
    - Todo el archivo: analiza todo el Excel
    - Rango manual: ingrese Desde y Hasta, por ejemplo 01+200 a 01+400
    - Tramos detectados: seleccione tramo inicial y tramo final para
      analizar todo el rango continuo detectado
    - Bloques automaticos: defina un bloque, por ejemplo 200 m,
      y el sistema analiza secuencialmente 01+000-01+200,
      01+200-01+400, 01+400-01+600, etc. segun el rango activo

CLASIFICACION DE DETERIOROS/FALLAS
  E - Deterioros o fallas Estructurales
      1 Piel de cocodrilo             m2
      2 Fisuras longitudinales         m2
      3 Deformacion por def. estruct.  m2
      4 Ahuellamiento                  m2
      5 Reparaciones o parchados       m2

  S - Deterioros o fallas Superficiales
      6 Peladura y desprendimiento     m2
      7 Baches (Huecos)               und  <- N de baches
      8 Fisuras Transversales          m2
      9 Exudacion                      m2

  B - BERMAS Pavimentadas y no pavimentadas
     10 Danos puntuales                m2
     11 Desnivel Calzada Berma         ml

BACHES (Cod.7) — IMPORTANTE:
  El conteo de baches (und) puede estar en la misma columna de
  medidas que las demas fallas. El sistema lo maneja así:

  CASO A — columna compartida (situacion mas comun):
    Mapee esa columna como "Area/Medida Falla".
    El sistema detecta automaticamente cod.7 y usa ese valor
    como conteo de baches (no como area).

  CASO B — columna dedicada:
    Si tiene una columna separada de cantidad/baches, mapee
    tambien "N Deterioros". Cuando esta columna tiene valores
    > 0, toma prioridad sobre el area_falla para cod.7.

METODO DE CALCULO  (MTC 2018)
  EFij(%)  = (Area_ij / As) x 100
  EFp      = S(EFij x Aij) / S(Aij)   [extension ponderada]
  Puntaje  = interpolacion lineal segun EFp (o N baches para cod.7)
  Indice   = 1000 - S(Puntajes)

PUNTAJE POR CONDICION
  0: Sin deterioro  EFp = 0          -> puntaje = 0
  1: Leve           0 < EFp < L      -> interpolado (0, p_L)
  2: Moderado       L <= EFp < M     -> interpolado [p_L, p_M)
  3: Severo         EFp >= M         -> puntaje = p_sev

  * Cod.7 Baches: < 4 baches=Leve | 4-10=Moderado | >10=Severo

RANGOS POR CODIGO
  Cod  Limites     P.Leve    P.Mod.  P.Sev.
   1   L<10%,M<30%  (0,40)  [40,200)  =200
   2   L<10%,M<30%  (0,20)  [20,100)  =100
   3   L<10%,M<30%  (0,20)  [20,100)  =100
   4   L<10%,M<30%  (0,20)  [20,100)  =100
   5   L<10%,M<30%  (0,10)  [10, 50)  = 50
   6   L<10%,M<30%  (0,10)  [10, 50)  = 50
   7*  <4,4-10      (0,20)  [20,100)  =100  *N baches
   8   L<10%,M<30%  (0,10)  [10, 50)  = 50
   9   L<10%,M<30%  (0,20)  [20,100)  =100
  10   L<10%,M<30%  (0,10)  [10, 50)  = 50
  11   L<10%,M<30%  (0,20)  [20,100)  =100

ESCALA DE CONDICION VIAL  (base 1000)
  800-1000 -> CONDICION BUENO
  300- 800 -> CONDICION REGULAR  (300 <= v <= 800)
      < 300 -> CONDICION MALO
"""

class VentanaAyuda(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent)
        self.title("Ayuda MTC 2018")
        self.configure(bg=C["window"]); self.geometry("720x600"); self.grab_set()
        hdr=tk.Frame(self,bg=C["titlebar"],pady=12,padx=18);hdr.pack(fill="x")
        tk.Label(hdr,text="GUIA MTC 2018",bg=C["titlebar"],fg=C["accent2"],font=FT).pack(side="left")
        txt=tk.Text(self,font=FM,wrap="word",padx=14,pady=10)
        style_text(txt)
        sb=ttk.Scrollbar(self,command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.insert("end",AYUDA); txt.config(state="disabled")
        txt.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        foot=tk.Frame(self,bg=C["titlebar"],pady=10);foot.pack(fill="x")
        make_button(foot,"  Cerrar  ",self.destroy,variant="primary",font=FB,padx=14,pady=7).pack()


# ═══════════════════════════════════════════════════════════════════════════
# APLICACION PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

class AppMTC(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analisis de Pavimentos Flexibles — Metodo MTC 2018")
        self.configure(bg=C["window"]); self.geometry("1540x940"); self.minsize(1200,720)
        self.option_add("*tearOff", False)
        self.option_add("*TCombobox*Listbox.font", FB)
        self.df_orig=self.df_w=None
        self.mapeo={}; self.ov={}; self.ign=[]
        self.ov_grav={}; self.ign_grav=[]
        self.tabla_rows=[]; self.detalle=[]; self.resumen=[]; self.glob={}
        self.resultado_principal=None
        self.resultados_tramos=[]
        self.resultados_bloques=[]
        self.resultado_selector_map={}
        self.v_resultado_sel=tk.StringVar(value="")
        self.ag=0.0
        self.prog_ctx={"modo":"todo","desc":"Archivo completo","columna":"","ini":None,"fin":None}
        self.main=tk.Frame(self,bg=C["window"],padx=10,pady=8)
        self._styles(); self._build_ui()

    def _styles(self):
        style=ttk.Style(); style.theme_use("clam")
        style.configure(".",
            background=C["bg"],
            foreground=C["text"],
            font=FB)
        style.configure("TCombobox",
            padding=6,
            fieldbackground=C["input_bg"],
            background=C["input_bg"],
            foreground=C["text"],
            bordercolor=C["input_border"],
            lightcolor=C["input_border"],
            darkcolor=C["input_border"],
            arrowcolor=C["text_dim"])
        style.map("TCombobox",
            fieldbackground=[("readonly",C["input_bg"]),("disabled",C["muted"])],
            background=[("readonly",C["input_bg"]),("disabled",C["muted"])],
            foreground=[("readonly",C["text"]),("disabled",C["text_dim"])],
            bordercolor=[("focus",C["focus"])],
            lightcolor=[("focus",C["focus"])],
            darkcolor=[("focus",C["focus"])],
            arrowcolor=[("readonly",C["accent"]),("disabled",C["text_dim"])])
        style.configure("Vertical.TScrollbar",
            background=C["muted"],
            troughcolor=C["bg"],
            bordercolor=C["bg"],
            lightcolor=C["muted"],
            darkcolor=C["muted"],
            arrowcolor=C["text_dim"])
        style.configure("Horizontal.TScrollbar",
            background=C["muted"],
            troughcolor=C["bg"],
            bordercolor=C["bg"],
            lightcolor=C["muted"],
            darkcolor=C["muted"],
            arrowcolor=C["text_dim"])
        style.configure("MTC.Treeview",
            background=C["card"],foreground=C["text"],rowheight=24,
            fieldbackground=C["card"],font=FM,borderwidth=0)
        style.configure("MTC.Treeview.Heading",
            background=C["panel"],foreground=C["accent2"],font=FH,relief="flat",
            borderwidth=0,padding=(4,6))
        style.map("MTC.Treeview",
            background=[("selected",C["btn"])],
            foreground=[("selected",C["text_bright"])])
        style.configure("MTC.TNotebook",background=C["bg"],borderwidth=0,tabmargins=(8,6,8,0))
        style.configure("MTC.TNotebook.Tab",
            background=C["muted"],foreground=C["text_dim"],
            font=FB,padding=[14,8],borderwidth=0)
        style.map("MTC.TNotebook.Tab",
            background=[("selected",C["card"]),("active","#e7edf5")],
            foreground=[("selected",C["text"]),("active",C["text"])])

    def _build_ui(self):
        self.main.pack(fill="both",expand=True)
        self._header(); self._toolbar()
        self._datos_carretera()
        self._body(); self._statusbar()

    def _header(self):
        shell, hdr = make_card(self.main, "titlebar", padx=12, pady=10)
        shell.pack(fill="x", pady=(0, 8))
        title_wrap=tk.Frame(hdr,bg=C["titlebar"])
        title_wrap.pack(side="left",fill="x",expand=True)
        tk.Label(title_wrap,
            text="ANALISIS DE FALLAS EN PAVIMENTOS FLEXIBLES",
            bg=C["titlebar"],fg=C["accent2"],font=("Segoe UI",15,"bold")).pack(side="left")
        tk.Label(title_wrap,
            text="  |  Metodo MTC 2018  |  Manual de Carreteras: Mantenimiento o Conservacion Vial",
            bg=C["titlebar"],fg=C["text_dim"],font=FS).pack(side="left",padx=(6,0))
        tk.Label(hdr,
            text="Miguel Bernardino Quispe Arias  |  Briza Edith Catachura Aycaya",
            bg=C["muted"],fg=C["text_dim"],font=FS,padx=10,pady=4).pack(side="right")
        return
        hdr=tk.Frame(self,bg=C["bg2"]); hdr.pack(fill="x")
        tk.Label(hdr,text="  ANALISIS DE FALLAS EN PAVIMENTOS FLEXIBLES — METODO MTC 2018",
            bg=C["bg2"],fg=C["accent2"],font=("Consolas",14,"bold")).pack(side="left",pady=(10,0))
        tk.Label(hdr,text="Manual de Carreteras: Mantenimiento o Conservacion Vial  ",
            bg=C["bg2"],fg=C["text_dim"],font=FS).pack(side="right",pady=(10,0))
        hdr2=tk.Frame(self,bg=C["bg2"]); hdr2.pack(fill="x")
        tk.Label(hdr2,
            text="  Bach. Miguel Bernardino Quispe Arias  |  Bach. Briza Edith Catachura Aycaya",
            bg=C["bg2"],fg=C["accent4"],font=("Consolas",9)).pack(side="left",pady=(0,8),padx=8)

    def _datos_carretera(self):
        """Barra de datos generales de la carretera (llenado manual) — 2 filas."""
        shell, outer = make_card(self.main, "card", padx=10, pady=8)
        shell.pack(fill="x", pady=(0, 8))
        tk.Label(outer,text="DATOS DE LA CARRETERA Y MUESTRA",
            bg=C["card"],fg=C["accent"],font=FH).pack(anchor="w",pady=(0,4))
        fila=tk.Frame(outer,bg=C["card"]); fila.pack(fill="x")
        campos=[("Nombre","v_nombre",22),("Tramo","v_tramo",12),
            ("Km Inicial","v_km_ini",8),("Km Final","v_km_fin",8),
            ("Ancho (m)","v_ancho",6),("Largo (m)","v_largo",6),
            ("Unidad de Muestreo","v_unidad",14),("Fecha","v_fecha",10)]
        for lbl,attr,w in campos:
            tk.Label(fila,text=lbl+":",bg=C["card"],fg=C["text_dim"],font=FS).pack(side="left",padx=(0,3))
            v=tk.StringVar(); setattr(self,attr,v)
            ent=tk.Entry(fila,textvariable=v,width=w,font=FB)
            style_entry(ent)
            ent.pack(side="left",padx=(0,6),ipady=3)
        tk.Label(fila,text="Area (m2):",bg=C["card"],fg=C["accent4"],font=FS).pack(side="left",padx=(0,3))
        self.v_area_calc=tk.StringVar(value="0.00")
        self.l_area_calc=tk.Label(fila,textvariable=self.v_area_calc,bg=C["pill"],fg=C["accent3"],
            font=("Segoe UI",10,"bold"),width=10,anchor="center",relief="flat",bd=0,padx=8,pady=4)
        self.l_area_calc.pack(side="left",padx=(0,4))
        self.v_ancho.trace_add("write", lambda *_: self._actualizar_area())
        self.v_largo.trace_add("write", lambda *_: self._actualizar_area())
        return
        outer=tk.Frame(self,bg=C["bg2"],pady=4); outer.pack(fill="x")
        # Fila 1
        r1=tk.Frame(outer,bg=C["bg2"]); r1.pack(fill="x",pady=(2,1))
        tk.Label(r1,text="  CARRETERA:",bg=C["bg2"],fg=C["accent2"],
            font=("Consolas",8,"bold")).pack(side="left",padx=(8,10))
        f1=[("Nombre","v_nombre",32),("Tramo","v_tramo",20),
            ("Km Inicial","v_km_ini",10),("Km Final","v_km_fin",10),
            ("Ancho (m)","v_ancho",8),("Largo (m)","v_largo",8)]
        for lbl,attr,w in f1:
            tk.Label(r1,text=lbl+":",bg=C["bg2"],fg=C["text_dim"],font=FS).pack(side="left",padx=(0,3))
            v=tk.StringVar(); setattr(self,attr,v)
            tk.Entry(r1,textvariable=v,width=w,bg=C["bg3"],fg=C["text"],
                insertbackground=C["accent2"],font=FB,relief="flat",bd=3).pack(side="left",padx=(0,12))
        # Area calculada = Ancho x Largo
        tk.Label(r1,text="Area (m²):",bg=C["bg2"],fg=C["accent4"],font=FS).pack(side="left",padx=(0,3))
        self.v_area_calc=tk.StringVar(value="0.00")
        self.l_area_calc=tk.Label(r1,textvariable=self.v_area_calc,bg=C["bg3"],fg=C["accent3"],
            font=("Consolas",10,"bold"),width=12,anchor="center",relief="flat",bd=3)
        self.l_area_calc.pack(side="left",padx=(0,12))
        self.v_ancho.trace_add("write", lambda *_: self._actualizar_area())
        self.v_largo.trace_add("write", lambda *_: self._actualizar_area())
        # Fila 2
        r2=tk.Frame(outer,bg=C["bg2"]); r2.pack(fill="x",pady=(1,2))
        tk.Label(r2,text="  MUESTRA:  ",bg=C["bg2"],fg=C["accent2"],
            font=("Consolas",8,"bold")).pack(side="left",padx=(8,10))
        f2=[("Unidad de Muestreo","v_unidad",24),("Fecha","v_fecha",14)]
        for lbl,attr,w in f2:
            tk.Label(r2,text=lbl+":",bg=C["bg2"],fg=C["text_dim"],font=FS).pack(side="left",padx=(0,3))
            v=tk.StringVar(); setattr(self,attr,v)
            tk.Entry(r2,textvariable=v,width=w,bg=C["bg3"],fg=C["text"],
                insertbackground=C["accent2"],font=FB,relief="flat",bd=3).pack(side="left",padx=(0,12))

    def _actualizar_area(self):
        """Calcula Area = Ancho x Largo y actualiza ag (area global)."""
        try:
            ancho = float(self.v_ancho.get().replace(",","."))
            largo = float(self.v_largo.get().replace(",","."))
            area = ancho * largo
            self.v_area_calc.set(f"{area:.2f}")
            self.ag = area if area > 0 else 0.0
            self.l_area_calc.config(fg=C["accent3"] if area > 0 else C["text_dim"])
        except (ValueError, AttributeError):
            self.v_area_calc.set("0.00")
            self.l_area_calc.config(fg=C["text_dim"])

    def _get_datos_carretera(self):
        """Devuelve dict con los datos de la carretera ingresados."""
        return {
            "Nombre Carretera":    self.v_nombre.get().strip(),
            "Tramo":               self.v_tramo.get().strip(),
            "Km Inicial":          self.v_km_ini.get().strip(),
            "Km Final":            self.v_km_fin.get().strip(),
            "Ancho (m)":           self.v_ancho.get().strip(),
            "Largo (m)":           self.v_largo.get().strip(),
            "Area (m2)":           self.v_area_calc.get().strip(),
            "Unidad de Muestreo":  self.v_unidad.get().strip(),
            "Fecha Evaluacion":    self.v_fecha.get().strip(),
        }

    def _toolbar(self):
        shell, tb = make_card(self.main, "toolbar", padx=10, pady=8)
        shell.pack(fill="x", pady=(0, 8))
        def btn(tx,cmd,tip="",variant="secondary"):
            b=make_button(tb,tx,cmd,variant=variant,font=FB,padx=12,pady=6)
            b.pack(side="left",padx=3)
            if tip:tooltip(b,tip)
            return b
        btn("Cargar Excel",    self._cargar,    "Abrir archivo Excel",         "primary")
        btn("Mapear Columnas", self._mapear,    "Definir columnas del Excel",  "secondary")
        btn("Analizar",        self._analizar,  "Calcular EFij, EFp e Indice", "success")
        btn("Exportar",        self._exportar,  "Exportar resultados a Excel", "secondary")
        btn("Limpiar",         self._limpiar,   "Limpiar datos",               "danger")
        btn("Ayuda",           self._ayuda,     "Guia de uso y formulas",      "ghost")
        self.la=tk.Label(tb,text="Sin archivo cargado",bg=C["toolbar"],fg=C["text_dim"],font=FS,
            padx=10,pady=6)
        self.la.pack(side="left",padx=(8,4))
        self.lm=tk.Label(tb,text="Mapeo: pendiente",bg=C["pill"],fg=C["warn"],font=FS,
            padx=10,pady=6)
        self.lm.pack(side="left")
        return
        tb=tk.Frame(self,bg=C["bg3"],pady=6); tb.pack(fill="x")
        def btn(tx,cmd,tip="",col=C["btn"]):
            es_neutro = col in {C["bg"], C["bg2"], C["bg3"], C["border"]}
            fg = C["text"] if es_neutro else C["text_bright"]
            active_bg = C["bg2"] if es_neutro else C["btn_h"]
            b=tk.Button(tb,text=tx,command=cmd,bg=col,fg=fg,font=FB,
                relief="flat",bd=0,padx=14,pady=6,cursor="hand2",
                activebackground=active_bg,activeforeground=fg)
            b.pack(side="left",padx=4)
            if tip:tooltip(b,tip)
            return b
        btn("Cargar Excel",    self._cargar,    "Abrir archivo Excel")
        btn("Mapear Columnas", self._mapear,    "Definir columnas del Excel",     col=C["bg3"])
        btn("Analizar",        self._analizar,  "Calcular EFij, EFp e Indice",    col=C["ok"])
        btn("Exportar",        self._exportar,  "Exportar resultados a Excel",    col=C["bg3"])
        btn("Limpiar",         self._limpiar,   "Limpiar datos",                  col=C["danger"])
        btn("Ayuda",           self._ayuda,     "Guia de uso y formulas",         col=C["bg3"])
        self.la=tk.Label(tb,text="  Sin archivo cargado",bg=C["bg3"],fg=C["text_dim"],font=FS)
        self.la.pack(side="left",padx=12)
        self.lm=tk.Label(tb,text="  |  Mapeo: pendiente",bg=C["bg3"],fg=C["warn"],font=FS)
        self.lm.pack(side="left")

    def _body(self):
        pw=tk.PanedWindow(self.main,orient="horizontal",bg=C["window"],sashwidth=6,
            sashrelief="flat",bd=0)
        pw.pack(fill="both",expand=True)

        lf=tk.Frame(pw,bg=C["card"],highlightbackground=C["card_edge"],
            highlightthickness=1,bd=0)
        pw.add(lf,minsize=280)
        self.progs=PanelProgresivas(lf)
        self.progs.pack(fill="x",padx=8,pady=(8,6))
        self.filtros=PanelFiltros(lf,self._filtrar)
        self.filtros.pack(fill="x",padx=8,pady=(0,6))
        fp=tk.Frame(lf,bg=C["card"])
        fp.pack(fill="both",expand=True,padx=8,pady=(0,8))
        tk.Label(fp,text="VISTA PREVIA",bg=C["card"],fg=C["accent"],font=FH).pack(anchor="w",pady=(2,4))
        self.tp=tk.Text(fp,font=FM,state="disabled",wrap="none")
        style_text(self.tp)
        sv=ttk.Scrollbar(fp,command=self.tp.yview)
        self.tp.configure(yscrollcommand=sv.set)
        self.tp.pack(side="left",fill="both",expand=True)
        sv.pack(side="left",fill="y",padx=(8,0))

        rf=tk.Frame(pw,bg=C["card"],highlightbackground=C["card_edge"],
            highlightthickness=1,bd=0)
        pw.add(rf,minsize=760)
        selr=tk.Frame(rf,bg=C["card"],pady=8,padx=10)
        selr.pack(fill="x")
        tk.Label(selr,text="RESULTADO:",bg=C["card"],fg=C["accent"],font=FH).pack(side="left")
        self.cb_resultado=ttk.Combobox(
            selr,textvariable=self.v_resultado_sel,values=[],
            width=38,state="readonly",font=FB)
        self.cb_resultado.pack(side="left",padx=(8,12))
        self.cb_resultado.bind("<<ComboboxSelected>>",lambda e:self._on_resultado_selected())
        self.lr_resultado=tk.Label(
            selr,text="Sin resultados calculados.",bg=C["pill"],
            fg=C["text_dim"],font=FS,padx=10,pady=4)
        self.lr_resultado.pack(side="left")
        self.l_indice_resultado=tk.Label(
            selr,text="Indice de condicion del pavimento: -",bg=C["card_alt"],
            fg=C["text_dim"],font=FS,padx=10,pady=4)
        self.l_indice_resultado.pack(side="left",padx=(0,8))
        nb=ttk.Notebook(rf,style="MTC.TNotebook")
        nb.pack(fill="both",expand=True)

        t1=tk.Frame(nb,bg=C["card"]); nb.add(t1,text="  Puntaje de Condicion  ")
        self.tabla=TablaMTC(t1)
        self.tabla.pack(fill="both",expand=True,padx=10,pady=10)

        t2=tk.Frame(nb,bg=C["card"]); nb.add(t2,text="  Detalle por Gravedad  ")
        self.tdet=TablaDetalle(t2)
        self.tdet.pack(fill="both",expand=True,padx=10,pady=10)

        t3=tk.Frame(nb,bg=C["card"]); nb.add(t3,text="  Indice de Condicion  ")
        self.resumen_panel=PanelResumen(t3)
        self.resumen_panel.pack(fill="both",expand=True,padx=12,pady=10)

        t_torta=tk.Frame(nb,bg=C["card"]); nb.add(t_torta,text="  Diagrama de Fallas  ")
        th=tk.Frame(t_torta,bg=C["card"]); th.pack(fill="x",pady=(6,0),padx=10)
        make_button(th,"  Exportar PNG  ",self._exportar_png,
            variant="quiet",font=FB,padx=14,pady=6).pack(side="right")
        self.torta_frame=tk.Frame(t_torta,bg=C["card"])
        self.torta_frame.pack(fill="both",expand=True,padx=10,pady=(0,10))
        self.torta_canvas_widget=None
        tk.Label(self.torta_frame,
            text="Ejecute el Analisis para generar el diagrama.",
            bg=C["card"],fg=C["text_dim"],font=FB).pack(expand=True)

        t4=tk.Frame(nb,bg=C["card"]); nb.add(t4,text="  Reporte Tecnico  ")
        self.trep=tk.Text(t4,font=FM,state="disabled",wrap="none")
        style_text(self.trep)
        sr=ttk.Scrollbar(t4,command=self.trep.yview)
        self.trep.configure(yscrollcommand=sr.set)
        self.trep.pack(side="left",fill="both",expand=True,padx=(10,0),pady=10)
        sr.pack(side="right",fill="y",padx=(6,10),pady=10)
        return
        pw=tk.PanedWindow(self,orient="horizontal",bg=C["border"],sashwidth=3)
        pw.pack(fill="both",expand=True)

        lf=tk.Frame(pw,bg=C["bg"]); pw.add(lf,minsize=330)
        self.progs=PanelProgresivas(lf)
        self.progs.pack(fill="x")
        tk.Frame(lf,bg=C["border"],height=1).pack(fill="x")
        self.filtros=PanelFiltros(lf,self._filtrar)
        self.filtros.pack(fill="x")
        tk.Frame(lf,bg=C["border"],height=1).pack(fill="x")
        fp=tk.Frame(lf,bg=C["bg"]); fp.pack(fill="both",expand=True)
        tk.Label(fp,text="  VISTA PREVIA",bg=C["bg"],fg=C["accent"],font=FH).pack(anchor="w",pady=(6,2))
        self.tp=tk.Text(fp,bg=C["bg3"],fg=C["text"],font=FM,relief="flat",state="disabled",wrap="none")
        sv=ttk.Scrollbar(fp,command=self.tp.yview)
        self.tp.configure(yscrollcommand=sv.set)
        self.tp.pack(side="left",fill="both",expand=True); sv.pack(side="left",fill="y")

        rf=tk.Frame(pw,bg=C["bg"]); pw.add(rf,minsize=880)
        selr=tk.Frame(rf,bg=C["bg2"],pady=6)
        selr.pack(fill="x")
        tk.Label(selr,text="  RESULTADO:",bg=C["bg2"],fg=C["accent"],font=FH).pack(side="left")
        self.cb_resultado=ttk.Combobox(
            selr,textvariable=self.v_resultado_sel,values=[],
            width=38,state="readonly",font=FB)
        self.cb_resultado.pack(side="left",padx=(8,12))
        self.cb_resultado.bind("<<ComboboxSelected>>",lambda e:self._on_resultado_selected())
        self.lr_resultado=tk.Label(
            selr,text="Sin resultados calculados.",bg=C["bg2"],
            fg=C["text_dim"],font=FS)
        self.lr_resultado.pack(side="left")
        nbs=ttk.Style()
        nbs.configure("MTC.TNotebook",background=C["bg"])
        nbs.configure("MTC.TNotebook.Tab",background=C["bg3"],foreground=C["text_dim"],
            font=FB,padding=[12,6])
        nbs.map("MTC.TNotebook.Tab",
            background=[("selected",C["bg2"])],
            foreground=[("selected",C["accent2"])])
        nb=ttk.Notebook(rf,style="MTC.TNotebook"); nb.pack(fill="both",expand=True)

        t1=tk.Frame(nb,bg=C["bg"]); nb.add(t1,text="  Puntaje de Condicion  ")
        h1=tk.Frame(t1,bg=C["bg"]); h1.pack(fill="x",pady=(4,2))
        tk.Label(h1,
            text="  PUNTAJE DE CONDICION POR TIPO DE DETERIORO/FALLA  —  Indice = 1000 - S Puntajes",
            bg=C["bg"],fg=C["accent"],font=FH).pack(side="left")
        lg=tk.Frame(h1,bg=C["bg"]); lg.pack(side="right",padx=10)
        for cl,col in[("E",C["accent2"]),("S",C["accent3"]),("B",C["accent4"])]:
            tk.Label(lg,text=f" {cl} ",bg=col,fg=C["bg"],
                font=("Consolas",8,"bold")).pack(side="left",padx=2)
            tk.Label(lg,text={"E":"Estructural","S":"Superficial","B":"Berma"}[cl],
                bg=C["bg"],fg=col,font=FS).pack(side="left",padx=(0,8))
        self.tabla=TablaMTC(t1)
        self.tabla.pack(fill="both",expand=True)

        t2=tk.Frame(nb,bg=C["bg"]); nb.add(t2,text="  Detalle por Gravedad  ")
        tk.Label(t2,text="  DETALLE POR CODIGO + GRAVEDAD",
            bg=C["bg"],fg=C["accent"],font=FH).pack(anchor="w",pady=(6,2))
        self.tdet=TablaDetalle(t2)
        self.tdet.pack(fill="both",expand=True)

        t3=tk.Frame(nb,bg=C["bg2"]); nb.add(t3,text="  Indice de Condicion  ")
        self.resumen_panel=PanelResumen(t3)
        self.resumen_panel.pack(fill="both",expand=True)

        # ── Tab Diagrama de Torta ────────────────────────────────────────
        t_torta=tk.Frame(nb,bg=C["bg"]); nb.add(t_torta,text="  Diagrama de Fallas  ")
        th=tk.Frame(t_torta,bg=C["bg"]); th.pack(fill="x",pady=(6,2))
        tk.Label(th,text="  DISTRIBUCION DE FALLAS — AREA POR TIPO DE DETERIORO",
            bg=C["bg"],fg=C["accent"],font=FH).pack(side="left")
        tk.Button(th,text="  Exportar PNG  ",command=self._exportar_png,
            bg=C["bg3"],fg=C["accent3"],font=FB,relief="flat",bd=0,
            padx=12,pady=4,cursor="hand2").pack(side="right",padx=12)
        tk.Frame(t_torta,bg=C["border"],height=1).pack(fill="x")
        self.torta_frame=tk.Frame(t_torta,bg=C["bg"]); self.torta_frame.pack(fill="both",expand=True)
        self.torta_canvas_widget=None   # referencia al widget matplotlib
        # placeholder vacío
        tk.Label(self.torta_frame,
            text="Ejecute el Análisis para generar el diagrama.",
            bg=C["card"],fg=C["text_dim"],font=FB).pack(expand=True)

        t4=tk.Frame(nb,bg=C["bg"]); nb.add(t4,text="  Reporte Tecnico  ")
        tk.Label(t4,text="  REPORTE TECNICO MTC 2018",
            bg=C["bg"],fg=C["accent"],font=FH).pack(anchor="w",pady=(6,2))
        self.trep=tk.Text(t4,bg=C["bg3"],fg=C["text"],font=FM,relief="flat",
            state="disabled",wrap="none")
        sr=ttk.Scrollbar(t4,command=self.trep.yview)
        self.trep.configure(yscrollcommand=sr.set)
        self.trep.pack(side="left",fill="both",expand=True); sr.pack(side="right",fill="y")

    def _statusbar(self):
        self.ls=tk.Label(self,
            text="  Listo. Cargue un archivo Excel para comenzar.",
            bg=C["window"],fg=C["text_dim"],font=FS)
        return
        ab=tk.Frame(self,bg=C["border"],height=20); ab.pack(fill="x",side="bottom"); ab.pack_propagate(False)
        tk.Label(ab,
            text="  Autores:  Bach. Miguel Bernardino Quispe Arias     |     Bach. Briza Edith Catachura Aycaya  ",
            bg=C["border"],fg=C["text_dim"],font=FS).pack(side="right",pady=2)
        # Barra de estado
        sb=tk.Frame(self,bg=C["bg2"],height=22); sb.pack(fill="x",side="bottom"); sb.pack_propagate(False)
        self.ls=tk.Label(sb,text="  Listo. Cargue un archivo Excel para comenzar.",
            bg=C["bg2"],fg=C["text_dim"],font=FS)
        self.ls.pack(side="left",pady=2)
        tk.Label(sb,text="MTC 2018 — Manual de Carreteras: Mantenimiento o Conservacion Vial  ",
            bg=C["bg2"],fg=C["text_dim"],font=FS).pack(side="right")

    def _st(self,msg,col=None):
        self.ls.config(text=f"  {msg}",fg=col or C["text_dim"])
        self.update_idletasks()

    def _cargar(self):
        path=filedialog.askopenfilename(title="Seleccionar Excel",
            filetypes=[("Excel","*.xlsx *.xls *.xlsm"),("Todos","*.*")])
        if not path:return
        try:
            self._st("Cargando...",C["accent4"])
            xl=pd.ExcelFile(path)
            hoja=self._sel_hoja(xl.sheet_names) if len(xl.sheet_names)>1 else xl.sheet_names[0]
            if hoja is None:return
            self.df_orig=pd.read_excel(path,sheet_name=hoja,header=0)
            nm=os.path.basename(path)
            self.la.config(
                text=f"  {nm}  ({len(self.df_orig)} filas, {len(self.df_orig.columns)} cols)",
                fg=C["accent3"])
            self._preview()
            self.progs.configurar(self.df_orig,self.mapeo)
            self._st(f"Archivo: {nm}. Configure el mapeo.",C["accent3"])
            self._mapear()
        except Exception as e:
            messagebox.showerror("Error al cargar",str(e))
            self._st("Error al cargar.",C["danger"])

    def _sel_hoja(self,hojas):
        dlg=tk.Toplevel(self); dlg.title("Seleccionar Hoja")
        dlg.configure(bg=C["window"]); dlg.grab_set(); res=[None]
        tk.Label(dlg,text="Seleccione la hoja:",bg=C["window"],fg=C["text"],font=FB).pack(padx=20,pady=12)
        v=tk.StringVar(value=hojas[0])
        ttk.Combobox(dlg,textvariable=v,values=hojas,state="readonly",font=FB,width=32).pack(padx=20,pady=5)
        def ok():res[0]=v.get();dlg.destroy()
        make_button(dlg,"Aceptar",ok,variant="primary",font=FB,padx=14,pady=7).pack(pady=12)
        dlg.wait_window(); return res[0]

    def _preview(self):
        if self.df_orig is None:return
        self.tp.config(state="normal"); self.tp.delete("1.0","end")
        self.tp.insert("end","COLUMNAS:\n  "+" | ".join(str(c) for c in self.df_orig.columns)+"\n\n")
        self.tp.insert("end","PRIMERAS 50 FILAS:\n"+self.df_orig.head(50).to_string(max_colwidth=16))
        self.tp.config(state="disabled")

    def _mapear(self):
        if self.df_orig is None:
            messagebox.showinfo("Aviso","Primero cargue un archivo Excel.");return
        VentanaMapeo(self,self.df_orig.columns,self._rec_mapeo,df=self.df_orig,
                     area_global_inicial=self.ag if self.ag>0 else 0.0)

    def _rec_mapeo(self,mapeo,ag,ov,ign,ov_grav=None,ign_grav=None):
        self.mapeo=mapeo; self.ag=ag; self.ov=ov; self.ign=ign
        self.ov_grav=ov_grav or {}; self.ign_grav=ign_grav or []
        n=sum(1 for v in mapeo.values() if v!="(ninguna)")
        ex=""
        if ov or ign: ex+=f"  |  {len(ov)} nombres val."
        if ov_grav or ign_grav: ex+=f"  |  {len(ov_grav)} gravedades val."
        self.lm.config(text=f"  |  Mapeo: {n} campos{ex}",fg=C["accent3"])
        self.progs.configurar(self.df_orig,self.mapeo)
        self._st("Mapeo configurado. Presione Analizar.",C["accent4"])

    def _filtrar(self,fallas,gravs):
        if not self.tabla_rows:return
        self.tabla.poblar(self.tabla_rows,
            sum(r["_pt"] for r in self.tabla_rows if r["grav"]==2 and r["cod"] in set(fallas)),
            fallas,gravs)
        self.tdet.poblar([r for r in self.detalle if r["codigo"] in set(fallas) and r["grav"] in set(gravs)])

    def _build_result_package(self, rows, det, res, glob, dw, ctx, selector_label):
        return {
            "tabla_rows": rows,
            "detalle": det,
            "resumen": res,
            "glob": glob,
            "df_w": dw,
            "prog_ctx": dict(ctx or {}),
            "selector_label": selector_label,
        }

    def _calcular_paquete_resultado(self, df, ctx, selector_label):
        rows,det,res,glob,dw=Motor.procesar(
            df,self.mapeo,self.ag if self.ag>0 else None,
            overrides=self.ov if self.ov else None)
        return self._build_result_package(rows, det, res, glob, dw, ctx, selector_label)

    def _calcular_resultados_por_progresiva(self, df, columna):
        if df is None or df.empty:
            return []
        if "_prog_ini_m" not in df.columns or "_prog_fin_m" not in df.columns:
            return []
        base = df.dropna(subset=["_prog_ini_m", "_prog_fin_m"]).copy()
        if base.empty:
            return []
        resultados = []
        for (ini, fin), blk in base.groupby(["_prog_ini_m", "_prog_fin_m"], sort=True):
            ini = int(ini)
            fin = int(fin)
            ctx = self._build_prog_ctx("tramo_detalle", columna, ini, fin, blk)
            resultados.append(
                self._calcular_paquete_resultado(
                    blk, ctx, f"Tramo: {ctx.get('desc', '')}"
                )
            )
        return resultados

    def _calcular_resultados_por_bloques(self, df, columna, tam_bloque, prog_ini=None, prog_fin=None):
        if df is None or df.empty or not columna:
            return []
        bloques, _ = AnalizadorProgresivas.bloques_disponibles(
            df, columna, tam_bloque, prog_ini, prog_fin
        )
        if not bloques:
            return []
        resultados = []
        for bloque in bloques:
            blk = AnalizadorProgresivas.filtrar_df(df, columna, bloque["ini"], bloque["fin"])
            if blk.empty:
                continue
            ctx = self._build_prog_ctx("bloques_detalle", columna, bloque["ini"], bloque["fin"], blk)
            ctx["desc"] = bloque["label"]
            resultados.append(
                self._calcular_paquete_resultado(
                    blk, ctx, f"Bloque: {bloque['label']}"
                )
            )
        return resultados

    def _refresh_resultado_selector(self, prefer=None):
        opciones=[]; mapping={}
        desc_actual=""
        modo_actual=""
        if self.resultado_principal:
            desc_actual = self.resultado_principal.get("prog_ctx", {}).get("desc", "")
            modo_actual = self.resultado_principal.get("prog_ctx", {}).get("modo", "")
        if self.resultado_principal and not (modo_actual == "bloques" and self.resultados_bloques):
            label=self.resultado_principal.get("selector_label","Actual")
            opciones.append(label)
            mapping[label]=self.resultado_principal
        if modo_actual == "bloques" and self.resultados_bloques:
            for bloque in self.resultados_bloques:
                label = bloque.get("selector_label", "")
                desc = bloque.get("prog_ctx", {}).get("desc", "")
                if not label or (desc_actual and desc == desc_actual):
                    continue
                opciones.append(label)
                mapping[label] = bloque
        else:
            for tramo in self.resultados_tramos:
                label = tramo.get("selector_label", "")
                desc = tramo.get("prog_ctx", {}).get("desc", "")
                if not label or (desc_actual and desc == desc_actual):
                    continue
                opciones.append(label)
                mapping[label] = tramo
        self.resultado_selector_map = mapping
        self.cb_resultado.configure(values=opciones)
        actual = prefer or self.v_resultado_sel.get()
        if actual not in mapping and opciones:
            actual = opciones[0]
        self.v_resultado_sel.set(actual if opciones else "")
        if opciones:
            if modo_actual == "bloques" and self.resultados_bloques:
                self.lr_resultado.config(
                    text=f"{len(self.resultados_bloques)} bloque(s) calculado(s).",
                    fg=C["accent3"],
                )
            else:
                self.lr_resultado.config(
                    text=f"{len(self.resultados_tramos)} tramo(s) calculado(s).",
                    fg=C["accent3"] if self.resultados_tramos else C["text_dim"],
                )
        else:
            self.lr_resultado.config(text="Sin resultados calculados.", fg=C["text_dim"])
            self._actualizar_indice_resultado(None)

    def _get_resultado_visible(self):
        self._refresh_resultado_selector()
        visible = self.resultado_selector_map.get(self.v_resultado_sel.get())
        if visible:
            return visible
        return self.resultado_principal

    def _actualizar_indice_resultado(self, paquete):
        lbl = getattr(self, "l_indice_resultado", None)
        if lbl is None:
            return
        if not paquete:
            lbl.config(text="Indice de condicion del pavimento: -", fg=C["text_dim"])
            return
        glob = paquete.get("glob", {})
        indice = glob.get("indice")
        if indice is None:
            lbl.config(text="Indice de condicion del pavimento: -", fg=C["text_dim"])
            return
        lbl.config(
            text=f"Indice de condicion del pavimento: {indice:.1f}/1000  |  {glob.get('cond','')}",
            fg=glob.get("color", C["text_dim"]))

    def _aplicar_resultado_visible(self, paquete):
        if not paquete:
            return
        self.tabla_rows = paquete["tabla_rows"]
        self.detalle = paquete["detalle"]
        self.resumen = paquete["resumen"]
        self.glob = paquete["glob"]
        self.df_w = paquete["df_w"]
        self.prog_ctx = dict(paquete.get("prog_ctx") or {})
        fallas,gravs=self.filtros.get()
        self.tabla.poblar(
            self.tabla_rows,
            sum(r["_pt"] for r in self.tabla_rows if r["grav"]==2 and r["cod"] in set(fallas)),
            fallas,gravs)
        self.tdet.poblar([r for r in self.detalle if r["codigo"] in set(fallas) and r["grav"] in set(gravs)])
        self.resumen_panel.actualizar(self.glob)
        self._actualizar_indice_resultado(paquete)
        self._grafico_torta(self.resumen)
        self._reporte(self.resumen,self.glob)

    def _on_resultado_selected(self):
        paquete = self._get_resultado_visible()
        if not paquete:
            return
        self._aplicar_resultado_visible(paquete)

    def _build_prog_ctx(self, modo, columna, ini, fin, df):
        n_img = int(df[columna].astype(str).nunique()) if columna and columna in df.columns else 0
        n_tramos = int(df["_prog_tramo"].replace("", pd.NA).dropna().nunique()) if "_prog_tramo" in df.columns else 0
        return {
            "modo": modo,
            "columna": columna or "",
            "ini": ini,
            "fin": fin,
            "desc": f"{metros_a_prog(ini)} - {metros_a_prog(fin)}" if ini is not None and fin is not None else "Archivo completo",
            "n_reg": int(len(df)),
            "n_img": n_img,
            "n_tramos": n_tramos,
        }

    def _aplicar_filtro_progresiva(self, df):
        cfg = self.progs.obtener_config()
        ctx = {"modo":"todo","columna":"","ini":None,"fin":None,"desc":"Archivo completo","n_reg":int(len(df)),"n_img":0,"n_tramos":0}
        if cfg["modo"] == "todo":
            col = cfg["columna"]
            if col:
                if col not in df.columns:
                    raise ValueError(f"La columna de progresiva '{col}' no existe en el Excel.")
                preparado = AnalizadorProgresivas.preparar_df(df, col)
                return preparado, self._build_prog_ctx("todo", col, None, None, preparado)
            return df, ctx
        col = cfg["columna"]
        if not col:
            raise ValueError("Seleccione la columna que contiene el nombre del archivo o imagen.")
        if col not in df.columns:
            raise ValueError(f"La columna de progresiva '{col}' no existe en el Excel.")
        if cfg["modo"] == "manual":
            if cfg["ini"] is None or cfg["fin"] is None:
                raise ValueError("Ingrese la progresiva inicial y final para el rango manual.")
            filtrado = AnalizadorProgresivas.filtrar_df(df, col, cfg["ini"], cfg["fin"])
            if filtrado.empty:
                raise ValueError("No se encontraron registros dentro del rango de progresivas indicado.")
            return filtrado, self._build_prog_ctx("manual", col, cfg["ini"], cfg["fin"], filtrado)
        if cfg["modo"] == "tramos":
            tramo_ini = cfg.get("tramo_ini")
            tramo_fin = cfg.get("tramo_fin")
            if not tramo_ini or not tramo_fin:
                raise ValueError("Seleccione el tramo inicial y final detectados.")
            ini = tramo_ini["ini"]
            fin = tramo_fin["fin"]
            if fin <= ini:
                raise ValueError("El tramo final debe quedar despues del tramo inicial.")
            filtrado = AnalizadorProgresivas.filtrar_df(df, col, ini, fin)
            if filtrado.empty:
                raise ValueError("No se encontraron registros dentro del rango de tramos seleccionado.")
            return filtrado, self._build_prog_ctx("tramos", col, ini, fin, filtrado)
        if cfg["modo"] == "bloques":
            filtrado = AnalizadorProgresivas.filtrar_df(df, col, cfg["ini"], cfg["fin"])
            if filtrado.empty:
                raise ValueError("No se encontraron registros analizables para los bloques del rango indicado.")
            ini_ctx = int(filtrado["_prog_ini_m"].min()) if "_prog_ini_m" in filtrado.columns else cfg["ini"]
            fin_ctx = int(filtrado["_prog_fin_m"].max()) if "_prog_fin_m" in filtrado.columns else cfg["fin"]
            ctx = self._build_prog_ctx("bloques", col, ini_ctx, fin_ctx, filtrado)
            ctx["desc"] = f"Bloques de {cfg['tam_bloque']} m  |  {metros_a_prog(ini_ctx)} - {metros_a_prog(fin_ctx)}"
            ctx["tam_bloque"] = cfg["tam_bloque"]
            return filtrado, ctx
        return df, ctx

    def _analizar(self):
        if self.df_orig is None:
            messagebox.showinfo("Aviso","Cargue un archivo Excel.");return
        if not self.mapeo:
            messagebox.showinfo("Aviso","Configure el mapeo de columnas.");return
        try:
            self._st("Procesando analisis MTC 2018...",C["accent4"])
            df=self.df_orig.copy()
            if self.ign:
                cn=self.mapeo.get("nombre_falla","(ninguna)")
                if cn!="(ninguna)" and cn in df.columns:
                    mk=df[cn].astype(str).str.strip().isin([str(n).strip() for n in self.ign])
                    df=df[~mk]
            # Aplicar ignorados de gravedad antes de procesar
            if self.ign_grav:
                cg=self.mapeo.get("gravedad","(ninguna)")
                if cg!="(ninguna)" and cg in df.columns:
                    mk=df[cg].astype(str).str.strip().isin([str(g).strip() for g in self.ign_grav])
                    df=df[~mk]
            # Aplicar overrides de gravedad
            if self.ov_grav:
                cg=self.mapeo.get("gravedad","(ninguna)")
                if cg!="(ninguna)" and cg in df.columns:
                    df[cg]=df[cg].apply(
                        lambda x: self.ov_grav.get(str(x).strip(), x)
                    )
            df,self.prog_ctx=self._aplicar_filtro_progresiva(df)
            cfg_prog = self.progs.obtener_config()
            self.resultado_principal = self._calcular_paquete_resultado(
                df, self.prog_ctx,
                f"Actual: {self.prog_ctx.get('desc','Archivo completo')}"
            )
            self.resultados_bloques = []
            self.resultados_tramos = self._calcular_resultados_por_progresiva(
                df, self.prog_ctx.get("columna")
            )
            if cfg_prog.get("modo") == "bloques":
                self.resultados_bloques = self._calcular_resultados_por_bloques(
                    df, self.prog_ctx.get("columna"),
                    cfg_prog.get("tam_bloque", 200),
                    cfg_prog.get("ini"), cfg_prog.get("fin")
                )
            self._refresh_resultado_selector(
                prefer=self.resultado_principal.get("selector_label")
            )
            self._on_resultado_selected()
            visible_pkg = self._get_resultado_visible() or self.resultado_principal
            glob = visible_pkg["glob"]
            ig=""
            if self.ign:ig=f"  |  {len(self.ign)} ignoradas"
            tr=""
            modo_sel = self.prog_ctx.get("modo", "")
            if modo_sel.startswith("bloques"):
                tr=f"  |  Bloque: {self.prog_ctx.get('desc','')}"
            elif modo_sel != "todo":
                tr=f"  |  Progr.: {self.prog_ctx.get('desc','')}"
            dt=""
            if self.resultados_tramos:
                dt=f"  |  Tramos calc.: {len(self.resultados_tramos)}"
            db=""
            if self.resultados_bloques:
                db=f"  |  Bloques calc.: {len(self.resultados_bloques)}"
            self._st(
                f"Analisis completado  |  S Puntajes={glob['suma']:.1f}  "
                f"|  Indice={glob['indice']:.1f}/1000  ->  {glob['cond']}{ig}{tr}{dt}{db}",
                C["accent3"])
        except Exception as e:
            import traceback
            messagebox.showerror("Error",f"{e}\n\n{traceback.format_exc()}")
            self._st("Error en analisis.",C["danger"])

    def _exportar_png(self):
        """Guarda el diagrama de torta actual como PNG."""
        if not hasattr(self,"torta_canvas_widget") or self.torta_canvas_widget is None:
            messagebox.showinfo("Aviso","Ejecute el análisis primero para generar el diagrama.");return
        path=filedialog.asksaveasfilename(
            title="Guardar diagrama como PNG",
            defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg"),("PDF","*.pdf")])
        if not path:return
        try:
            fig=self.torta_canvas_widget.figure
            dpi=150
            fig.savefig(path,dpi=dpi,bbox_inches="tight",
                facecolor=fig.get_facecolor())
            self._st(f"Diagrama guardado: {os.path.basename(path)}",C["accent3"])
            messagebox.showinfo("Exportado","Diagrama guardado en:\n"+str(path))
        except Exception as e:
            messagebox.showerror("Error al exportar PNG",str(e))

    def _grafico_torta(self, res):
        """Genera diagrama de torta por tipo de falla (área total) embebido en tkinter."""
        # Limpiar frame anterior
        for w in self.torta_frame.winfo_children():
            w.destroy()
        self.torta_canvas_widget=None

        # Datos: solo fallas con área > 0
        datos=[(r["nombre"], r["area_tot"], r["clas"])
               for r in res if r["area_tot"]>0]
        if not datos:
            tk.Label(self.torta_frame,
                text="Sin datos de área para graficar.",
                bg=C["bg"],fg=C["text_dim"],font=FB).pack(expand=True)
            return

        nombres=[d[0] for d in datos]
        areas  =[d[1] for d in datos]
        clases =[d[2] for d in datos]

        # Paleta de 11 colores completamente distintos (1 por tipo de falla)
        # Orden fijo: cod 1..11; si hay menos datos, se toman los primeros
        PALETA_11 = [
            "#e63946",  # 1 Piel cocodrilo    — rojo vivo
            "#f4a261",  # 2 Fisuras long.     — naranja
            "#e9c46a",  # 3 Deformacion       — amarillo
            "#2a9d8f",  # 4 Ahuellamiento     — verde azulado
            "#264653",  # 5 Reparaciones      — azul pizarra
            "#457b9d",  # 6 Peladura          — azul medio
            "#a8dadc",  # 7 Baches            — celeste
            "#6a4c93",  # 8 Fisuras trans.    — morado
            "#f77f00",  # 9 Exudacion         — naranja fuerte
            "#4cc9f0",  # 10 Daños puntuales  — azul cielo
            "#80b918",  # 11 Desnivel berma   — lima
        ]
        # Asignar color según posición en FALLAS_MTC (cod 1-11)
        all_cods = list(FALLAS_MTC.keys())  # [1,2,...,11]
        colores=[]
        for r2 in res:
            if r2["area_tot"]>0:
                idx_c = all_cods.index(r2["codigo"]) if r2["codigo"] in all_cods else 0
                colores.append(PALETA_11[idx_c % len(PALETA_11)])

        total=sum(areas)
        pcts =[a/total*100 for a in areas]

        # Figura matplotlib con fondo oscuro
        fig=Figure(figsize=(13,5.8),facecolor=C["bg"])
        fig.subplots_adjust(left=0.02,right=0.60,top=0.92,bottom=0.06)

        ax=fig.add_subplot(111)
        ax.set_facecolor(C["bg"])

        # Etiqueta: solo porcentaje si el slice es grande, nada si pequeño
        def autopct_fn(pct):
            return f"{pct:.1f}%" if pct>=3 else ""

        wedges,texts,autotexts=ax.pie(
            areas, labels=None, autopct=autopct_fn,
            colors=colores, startangle=140,
            wedgeprops=dict(linewidth=0.8, edgecolor=C["bg2"]),
            pctdistance=0.78, textprops=dict(color=C["text_bright"],fontsize=8))

        for at in autotexts:
            at.set_fontsize(7.5)
            at.set_color(C["text_bright"])
            at.set_fontweight("bold")

        ax.set_title("Distribución de área por tipo de deterioro",
            color=C["accent2"],fontsize=10,fontweight="bold",pad=10)

        # ── Leyenda lateral ──────────────────────────────────────────────
        # Ordenar por área descendente para la leyenda
        orden=sorted(range(len(nombres)),key=lambda i:-areas[i])
        leyenda_items=[]
        for i in orden:
            nm=nombres[i][:38]   # truncar si es muy largo
            ar=areas[i]
            pc=pcts[i]
            leyenda_items.append(
                mpatches.Patch(color=colores[i],
                    label=f"{nm}\n  {ar:.2f} m²  ({pc:.1f}%)"))

        leg=ax.legend(
            handles=leyenda_items,
            loc="center left", bbox_to_anchor=(1.02,0.5),
            fontsize=7.5, frameon=True,
            facecolor=C["bg3"], edgecolor=C["border"],
            labelcolor=C["text"], handlelength=1.2, handleheight=1.0,
            borderpad=0.8, labelspacing=0.9)

        # ── Embed en tkinter ─────────────────────────────────────────────
        canvas=FigureCanvasTkAgg(fig,master=self.torta_frame)
        canvas.draw()
        cw=canvas.get_tk_widget()
        cw.configure(bg=C["bg"],highlightthickness=0)
        cw.pack(fill="both",expand=True,padx=4,pady=4)
        self.torta_canvas_widget=canvas

    def _reporte(self,res,gl):
        sep="="*80; sep2="-"*80
        cl={0:"Sin deterioro",1:"Leve",2:"Moderado",3:"Severo"}
        dc=self._get_datos_carretera()
        pc=self.prog_ctx or {}
        lns=[sep,
             "  REPORTE TECNICO DE ANALISIS DE FALLAS EN PAVIMENTO FLEXIBLE",
             "  Manual de Carreteras: Mantenimiento o Conservacion Vial — MTC 2018",
             sep,
             f"  Nombre Carretera  : {dc['Nombre Carretera'] or '(sin datos)'}",
             f"  Tramo             : {dc['Tramo'] or '(sin datos)'}",
             f"  Km Inicial        : {dc['Km Inicial'] or '(sin datos)'}",
             f"  Km Final          : {dc['Km Final'] or '(sin datos)'}",
             f"  Ancho (m)         : {dc['Ancho (m)'] or '(sin datos)'}",
             f"  Largo (m)         : {dc['Largo (m)'] or '(sin datos)'}",
             f"  Unidad Muestreo   : {dc['Unidad de Muestreo'] or '(sin datos)'}",
             f"  Fecha Evaluacion  : {dc['Fecha Evaluacion'] or '(sin datos)'}",
             f"  Progresiva usada  : {pc.get('desc','Archivo completo')}",
             f"  Columna archivo   : {pc.get('columna') or '(no usada)'}",
             sep2,
             f"  Fecha            : {datetime.now():%Y-%m-%d %H:%M:%S}",
             f"  Total registros  : {gl['n']}",
             f"  Tipos de falla   : {gl['tipos']}","",
             sep2,"  PUNTAJES POR CODIGO DE FALLA",sep2,
             f"  {'Cl':>2}  {'Cod':>3}  {'Nombre':<42}  {'N':>4}  {'EFp/N':>10}  {'Condicion':>16}  {'Puntaje':>9}",
             "  "+"-"*90]
        for r in res:
            ep=(f"{r['efp_pct']:.3f}%" if r["codigo"]!=7
                else f"N={r['n_bach'] or 0} bch")
            lns.append(f"  {r['clas']:>2}  {r['codigo']:>3}  {r['nombre']:<42}  {r['n_reg']:>4}  "
                       f"{ep:>10}  {cl.get(r['cond_num'],''):>16}  {r['puntaje']:>9.3f}")
        lns+=["  "+"-"*90,
              f"  {'':>2}  {'':>3}  {'S  SUMA TOTAL DE PUNTAJES':<42}  {'':>4}  "
              f"{'':>10}  {'->':>16}  {gl['suma']:>9.3f}","",
              sep2,
              f"  INDICE = 1000 - S Puntajes  =  1000 - {gl['suma']:.3f}  =  {gl['indice']:.2f}",
              f"  CONDICION VIAL : {gl['cond']}","",
              sep2,"  FORMULAS MTC 2018:",
              "  EFij   = (Aij/As)*100",
              "  EFp    = S(EFij*Aij) / S(Aij)",
              "  Punt.  = interpolacion lineal segun EFp  (o N baches cod.7)",
              "  Indice = 1000 - S Puntajes","",
              "  ESCALA:  >800=BUENO  300<=v<=800=REGULAR  <300=MALO","",sep,"  Fin.",sep]
        self.trep.config(state="normal"); self.trep.delete("1.0","end")
        self.trep.insert("end","\n".join(lns)); self.trep.config(state="disabled")

    def _exportar(self):
        paquete = self._get_resultado_visible() or self.resultado_principal
        if not paquete:
            messagebox.showinfo("Aviso","Ejecute el analisis primero.");return
        path=filedialog.asksaveasfilename(title="Guardar resultados",
            defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")])
        if not path:return
        try:
            cl={0:"Sin deterioro",1:"Leve",2:"Moderado",3:"Severo"}
            resumen = paquete.get("resumen", [])
            detalle = paquete.get("detalle", [])
            glob = paquete.get("glob", {})
            df_proc = paquete.get("df_w")
            pc = dict(paquete.get("prog_ctx") or {})

            df_res=pd.DataFrame(resumen)
            if "cond_num" in df_res.columns:
                df_res["Condicion Texto"]=df_res["cond_num"].map(cl)
            df_res.rename(columns={"codigo":"Codigo","nombre":"Nombre Falla",
                "clas":"Clasificacion","n_reg":"N Registros",
                "n_bach":"N Baches (cod.7)","area_tot":"Area Falla Total(m2)",
                "area_sec":"Area Seccion As(m2)","efp_pct":"EFp(%)","cond_num":"Condicion(0-3)",
                "cond_lbl":"Condicion","puntaje":"Puntaje Interpolado"},inplace=True)
            dc=self._get_datos_carretera()
            prog_meta={
                "Modo Progresiva": pc.get("modo","todo"),
                "Tramo Analizado": pc.get("desc","Archivo completo"),
                "Progresiva Desde": metros_a_prog(pc.get("ini")) if pc.get("ini") is not None else "",
                "Progresiva Hasta": metros_a_prog(pc.get("fin")) if pc.get("fin") is not None else "",
                "Columna Archivo": pc.get("columna",""),
            }
            # Datos de carretera para repetir en cada fila de los DataFrames
            for _df in [df_res]:
                for k,v2 in prog_meta.items():
                    _df.insert(0, k, v2)
                for k,v2 in dc.items():
                    _df.insert(0, k, v2)

            def _clave_paquete(paq):
                if not paq:
                    return None
                pctx = dict(paq.get("prog_ctx") or {})
                return (
                    pctx.get("modo", ""),
                    pctx.get("desc", ""),
                    pctx.get("ini"),
                    pctx.get("fin"),
                )

            def _agregar_meta(df_base, meta, dc_base):
                df = df_base.copy()
                for k,v2 in meta.items():
                    df.insert(0, k, [v2] * len(df.index))
                for k,v2 in dc_base.items():
                    df.insert(0, k, [v2] * len(df.index))
                return df

            def _df_detalle_paquete(paq, nivel):
                df = pd.DataFrame(paq.get("detalle", []))
                df.rename(columns={"codigo":"Codigo","nombre":"Nombre Falla",
                    "clas":"Clasificacion","grav":"Gravedad(1/2/3)","grav_lbl":"Gravedad",
                    "n_reg":"N Registros","area_f":"Area Falla(m2)","area_s":"Area Seccion(m2)",
                    "efij":"SEFij(%)","efp_g":"EFp Gravedad(%)","cn":"Condicion Cod.(0-3)",
                    "cl":"Condicion Codigo","pt":"Puntaje Codigo"},inplace=True)
                pctx = dict(paq.get("prog_ctx") or {})
                meta = {
                    "Nivel Exportado": nivel,
                    "Modo Progresiva": pctx.get("modo","todo"),
                    "Tramo Analizado": pctx.get("desc","Archivo completo"),
                    "Progresiva Desde": metros_a_prog(pctx.get("ini")) if pctx.get("ini") is not None else "",
                    "Progresiva Hasta": metros_a_prog(pctx.get("fin")) if pctx.get("fin") is not None else "",
                    "Columna Archivo": pctx.get("columna",""),
                }
                return _agregar_meta(df, meta, dc)

            def _fila_indice(paq, nivel):
                pctx = dict(paq.get("prog_ctx") or {})
                g = paq.get("glob", {})
                return {
                    "Nombre Carretera":   dc["Nombre Carretera"],
                    "Tramo":              dc["Tramo"],
                    "Km Inicial":         dc["Km Inicial"],
                    "Km Final":           dc["Km Final"],
                    "Ancho (m)":          dc["Ancho (m)"],
                    "Largo (m)":          dc["Largo (m)"],
                    "Area (m2)":          dc["Area (m2)"],
                    "Unidad de Muestreo": dc["Unidad de Muestreo"],
                    "Fecha Evaluacion":   dc["Fecha Evaluacion"],
                    "Nivel Exportado":    nivel,
                    "Modo Progresiva":    pctx.get("modo", "todo"),
                    "Tramo Analizado":    pctx.get("desc", "Archivo completo"),
                    "Progresiva Desde":   metros_a_prog(pctx.get("ini")) if pctx.get("ini") is not None else "",
                    "Progresiva Hasta":   metros_a_prog(pctx.get("fin")) if pctx.get("fin") is not None else "",
                    "Columna Archivo":    pctx.get("columna", ""),
                    "Indice MTC(1000-S)": g.get("indice", 0),
                    "S Puntajes":         g.get("suma", 0),
                    "Condicion Vial":     g.get("cond", ""),
                    "N Registros":        g.get("n", 0),
                    "N Tipos Falla":      g.get("tipos", 0),
                    "Fecha Exportacion":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                }

            lista_paquetes = self.resultados_bloques or self.resultados_tramos
            filas_glob = []
            df_det_partes = []
            vistos = set()

            clave_vista = _clave_paquete(paquete)
            if paquete and clave_vista not in vistos:
                df_det_partes.append(_df_detalle_paquete(paquete, "Vista actual"))
                filas_glob.append(_fila_indice(paquete, "Vista actual"))
                vistos.add(clave_vista)

            for paq in lista_paquetes:
                clave = _clave_paquete(paq)
                if not paq or clave in vistos:
                    continue
                modo_paq = str((paq.get("prog_ctx") or {}).get("modo", "")).lower()
                nivel = "Bloque" if "bloque" in modo_paq else "Tramo"
                df_det_partes.append(_df_detalle_paquete(paq, nivel))
                filas_glob.append(_fila_indice(paq, nivel))
                vistos.add(clave)

            clave_resumen = _clave_paquete(self.resultado_principal)
            if self.resultado_principal and clave_resumen not in vistos:
                df_det_partes.append(_df_detalle_paquete(self.resultado_principal, "Resumen general"))
                filas_glob.append(_fila_indice(self.resultado_principal, "Resumen general"))
                vistos.add(clave_resumen)

            df_det = pd.concat(df_det_partes, ignore_index=True) if df_det_partes else _df_detalle_paquete(paquete, "Vista actual")
            df_glob=pd.DataFrame(filas_glob)
            with pd.ExcelWriter(path,engine="openpyxl") as w:
                df_res.to_excel(w,sheet_name="Puntajes por Codigo",index=False)
                df_det.to_excel(w,sheet_name="Detalle por Gravedad",index=False)
                df_glob.to_excel(w,sheet_name="Indice Condicion",index=False)
                if df_proc is not None:
                    df_proc.to_excel(w,sheet_name="Datos Procesados",index=False)
            self._st(
                f"Exportado: {os.path.basename(path)}  |  {prog_meta['Tramo Analizado']}",
                C["accent3"])
            messagebox.showinfo("Exito",f"Resultados exportados:\n{path}")
        except Exception as e:
            messagebox.showerror("Error al exportar",str(e))

    def _limpiar(self):
        if not messagebox.askyesno("Confirmar","Limpiar todos los datos?"):return
        self.df_orig=self.df_w=None
        self.mapeo={}; self.ov={}; self.ign=[]
        self.ov_grav={}; self.ign_grav=[]
        self.tabla_rows=[]; self.detalle=[]; self.resumen=[]; self.glob={}; self.ag=0.0
        self.resultado_principal=None
        self.resultados_tramos=[]
        self.resultados_bloques=[]
        self.resultado_selector_map={}
        self.v_resultado_sel.set("")
        self.cb_resultado.configure(values=[])
        self.lr_resultado.config(text="Sin resultados calculados.", fg=C["text_dim"])
        self._actualizar_indice_resultado(None)
        self.prog_ctx={"modo":"todo","desc":"Archivo completo","columna":"","ini":None,"fin":None}
        self.la.config(text="  Sin archivo cargado",fg=C["text_dim"])
        self.lm.config(text="  |  Mapeo: pendiente",fg=C["warn"])
        self.progs.resetear()
        for it in self.tabla.tree.get_children():self.tabla.tree.delete(it)
        for it in self.tdet.tree.get_children():self.tdet.tree.delete(it)
        for w in[self.tp,self.trep]:
            w.config(state="normal"); w.delete("1.0","end"); w.config(state="disabled")
        self.resumen_panel.li.config(text="-",fg=C["text_dim"])
        self.resumen_panel.lc.config(text="SIN DATOS",fg=C["text_dim"])
        self.resumen_panel.li2.config(text="")
        # Limpiar diagrama de torta
        for w in self.torta_frame.winfo_children(): w.destroy()
        self.torta_canvas_widget=None
        tk.Label(self.torta_frame,
            text="Ejecute el Análisis para generar el diagrama.",
            bg=C["bg"],fg=C["text_dim"],font=FB).pack(expand=True)
        self._st("Datos limpiados.")

    def _ayuda(self):VentanaAyuda(self)


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app=AppMTC()
    app.update_idletasks()
    sw,sh=app.winfo_screenwidth(),app.winfo_screenheight()
    ww,wh=app.winfo_width(),app.winfo_height()
    app.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
    app.mainloop()
