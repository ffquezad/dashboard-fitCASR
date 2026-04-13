import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import re
from pathlib import Path

# ─── Configuración de página ───────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard FIT 2025-26",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Estilos ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .main { background-color: #f8f7f4; }
    .block-container { padding: 2rem 2.5rem; max-width: 1400px; }

    .header-bar {
        background: #1a1a2e;
        color: white;
        padding: 1.2rem 1.8rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .header-title { font-size: 1.2rem; font-weight: 600; letter-spacing: -0.02em; margin: 0; }
    .header-sub { font-size: 0.78rem; color: rgba(255,255,255,0.55); margin-top: 2px; font-family: 'IBM Plex Mono', monospace; }

    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        border: 1px solid #e8e5df;
        height: 100%;
    }
    .metric-label { font-size: 0.72rem; font-weight: 500; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
    .metric-value { font-size: 2rem; font-weight: 600; line-height: 1; color: #1a1a2e; }
    .metric-sub { font-size: 0.72rem; color: #aaa; margin-top: 4px; }
    .metric-red .metric-value { color: #c0392b; }
    .metric-green .metric-value { color: #1a7a4a; }

    .section-title {
        font-size: 0.7rem; font-weight: 600; color: #999;
        text-transform: uppercase; letter-spacing: 0.1em;
        border-bottom: 1px solid #e8e5df;
        padding-bottom: 6px; margin: 1.5rem 0 1rem;
    }

    .alto-riesgo-pos {
        background: #fdf0ef;
        border: 1px solid #f5c6c2;
        border-radius: 12px;
        padding: 1.6rem;
        height: 100%;
    }
    .alto-riesgo-neg {
        background: #eef7f1;
        border: 1px solid #b8dfc8;
        border-radius: 12px;
        padding: 1.6rem;
        height: 100%;
    }
    .ar-tag { font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
    .ar-tag-pos { color: #922b21; }
    .ar-tag-neg { color: #1a7a4a; }
    .ar-big { font-size: 3.2rem; font-weight: 600; line-height: 1; margin-bottom: 2px; }
    .ar-big-pos { color: #c0392b; }
    .ar-big-neg { color: #1a7a4a; }
    .ar-desc { font-size: 0.78rem; color: #666; margin-bottom: 14px; }
    .ar-row { display: flex; justify-content: space-between; font-size: 0.8rem; padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.07); }
    .ar-row:last-child { border-bottom: none; }
    .ar-row-label { color: #666; }
    .ar-row-val-pos { color: #922b21; font-weight: 600; }
    .ar-row-val-neg { color: #1a7a4a; font-weight: 600; }

    .info-box {
        background: #fffbf0;
        border: 1px solid #f0e0a0;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.78rem;
        color: #7a6020;
        margin-bottom: 1rem;
    }

    div[data-testid="stFileUploader"] {
        background: white;
        border-radius: 10px;
        border: 1px dashed #ccc;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── Funciones de procesamiento ─────────────────────────────────────────────
def extract_mm(val):
    if pd.isna(val):
        return None
    m = re.search(r'(\d+)', str(val))
    return int(m.group(1)) if m else None

def clasificar_biopsia(b):
    if pd.isna(b):
        return 'Sin biopsia'
    b = str(b).upper()
    if 'ADENOCARCINOMA' in b:
        return 'Adenocarcinoma'
    if 'NSTB' in b:
        return 'NSTB'
    if 'ATD' in b or 'ATV' in b:
        return 'ATD/ATV-BG'
    return 'Otros'

@st.cache_data
def cargar_datos(file):
    df = pd.read_excel(file, sheet_name='FIT')
    cols = ['HOSPITAL', 'FECHA', 'GENERO', 'EDAD',
            'Resultado FIT', 'F. COLONOSCOPIA', 'FECHA BP',
            'BIOPSIA', 'POLIPO MAS GRANDE', 'Dias Bp', 'IC', 'CITACION']
    df = df[[c for c in cols if c in df.columns]]

    df['resultado_num'] = pd.to_numeric(df['Resultado FIT'], errors='coerce')
    df['fit_pos']  = df['resultado_num'] >= 20
    df['fit_neg']  = (df['resultado_num'] < 20) & df['resultado_num'].notna()
    df['sin_res']  = df['resultado_num'].isna()

    df['polipo_mm']     = df['POLIPO MAS GRANDE'].apply(extract_mm)
    df['polipo_grande'] = df['polipo_mm'].apply(lambda x: x >= 10 if pd.notna(x) else False)
    df['grupo']         = df['BIOPSIA'].apply(clasificar_biopsia)
    df['es_adeno']      = df['grupo'] == 'Adenocarcinoma'
    df['es_atd']        = df['grupo'] == 'ATD/ATV-BG'

    df['lesion_alto_riesgo'] = df['es_adeno'] | df['polipo_grande']
    df['lesion_relevante']   = df['es_adeno'] | df['es_atd'] | df['polipo_grande']
    return df

def calcular_stats(df):
    total   = len(df)
    pos_n   = df['fit_pos'].sum()
    neg_n   = df['fit_neg'].sum()
    sin_n   = df['sin_res'].sum()
    con_res = pos_n + neg_n

    pos = df[df['fit_pos'] & df['F. COLONOSCOPIA'].notna()].copy()
    neg = df[df['fit_neg'] & df['F. COLONOSCOPIA'].notna()].copy()

    def seg(sub):
        n = len(sub)
        if n == 0:
            return {}
        adeno    = sub['es_adeno'].sum()
        atd      = sub['es_atd'].sum()
        pol      = sub['polipo_grande'].sum()
        alto     = sub['lesion_alto_riesgo'].sum()
        relevante= sub['lesion_relevante'].sum()
        overlap_ar = (sub['es_adeno'] & sub['polipo_grande']).sum()
        dias = pd.to_numeric(sub['Dias Bp'], errors='coerce')
        dias_v = dias[(dias >= 0) & (dias < 365)]
        return dict(
            n=n, adeno=adeno, atd=atd, pol=pol,
            alto=alto, alto_pct=round(alto/n*100,1),
            relevante=relevante, relevante_pct=round(relevante/n*100,1),
            overlap_ar=overlap_ar,
            adeno_pct=round(adeno/n*100,1),
            atd_pct=round(atd/n*100,1),
            pol_pct=round(pol/n*100,1),
            otros=(sub['grupo']=='Otros').sum(),
            otros_pct=round((sub['grupo']=='Otros').sum()/n*100,1),
            nstb=(sub['grupo']=='NSTB').sum(),
            nstb_pct=round((sub['grupo']=='NSTB').sum()/n*100,1),
            sin_bx=(sub['grupo']=='Sin biopsia').sum(),
            sin_bx_pct=round((sub['grupo']=='Sin biopsia').sum()/n*100,1),
            dias_prom=round(dias_v.mean(),1) if len(dias_v) else 0,
            dias_med=round(dias_v.median(),1) if len(dias_v) else 0,
        )

    return dict(
        total=total, pos_n=int(pos_n), neg_n=int(neg_n), sin_n=int(sin_n),
        con_res=int(con_res),
        pos_pct=round(pos_n/con_res*100,1) if con_res else 0,
        neg_pct=round(neg_n/con_res*100,1) if con_res else 0,
        col_pos=int(df[df['fit_pos']]['F. COLONOSCOPIA'].notna().sum()),
        col_neg=int(df[df['fit_neg']]['F. COLONOSCOPIA'].notna().sum()),
        pend_pos=int(df[df['fit_pos']]['F. COLONOSCOPIA'].isna().sum()),
        pend_neg=int(df[df['fit_neg']]['F. COLONOSCOPIA'].isna().sum()),
        edad_pos=round(df[df['fit_pos']]['EDAD'].mean(),1) if 'EDAD' in df.columns else 0,
        edad_neg=round(df[df['fit_neg']]['EDAD'].mean(),1) if 'EDAD' in df.columns else 0,
        hospitales=df['HOSPITAL'].value_counts().to_dict() if 'HOSPITAL' in df.columns else {},
        pos_stats=seg(pos),
        neg_stats=seg(neg),
    )

# ─── Colores Plotly ────────────────────────────────────────────────────────
COL = {
    'adeno':  '#c0392b',
    'atd':    '#1a7a4a',
    'pol':    '#d35400',
    'nstb':   '#2471a3',
    'otros':  '#b7950b',
    'sinbx':  '#aab7b8',
    'pos':    '#c0392b',
    'neg':    '#1a7a4a',
    'pend':   '#d5d8dc',
}

# ─── UI ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div>
    <div class="header-title">🔬 Protocolo FIT 2025–2026</div>
    <div class="header-sub">Correlación FIT vs Colonoscopia · HSR + HPH · Positivo ≥ 20 ng/ml</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Carga de archivo ──────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Sube el archivo Excel actualizado para refrescar el dashboard",
    type=["xlsx"],
    label_visibility="collapsed"
)

if uploaded is None:
    st.markdown('<div class="info-box">⬆️ Sube el archivo <b>FIT_2025-26.xlsx</b> para visualizar el dashboard. Cada vez que lo actualices, vuelve a subirlo aquí.</div>', unsafe_allow_html=True)
    st.stop()

df  = cargar_datos(uploaded)
s   = calcular_stats(df)
ps  = s['pos_stats']
ns  = s['neg_stats']

# ─── Tarjetas resumen ──────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
cards = [
    (c1, "Total en protocolo", s['total'], f"Colonoscopias: {s['col_pos']+s['col_neg']}", ""),
    (c2, "FIT positivo (≥ 20 ng/ml)", s['pos_n'], f"{s['pos_pct']}% de los con resultado", "metric-red"),
    (c3, "FIT negativo (< 20 ng/ml)", s['neg_n'], f"{s['neg_pct']}% de los con resultado", "metric-green"),
    (c4, "Sin resultado", s['sin_n'], "Pasivos / pendientes", ""),
]
for col, label, val, sub, cls in cards:
    with col:
        st.markdown(f"""
        <div class="metric-card {cls}">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{val:,}</div>
          <div class="metric-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

# ─── Lesiones de alto riesgo ───────────────────────────────────────────────
st.markdown('<div class="section-title">Lesiones de alto riesgo · Adenocarcinoma + Pólipo ≥ 10mm · individuos únicos · solo con colonoscopia</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""
    <div class="alto-riesgo-pos">
      <div class="ar-tag ar-tag-pos">FIT Positivo · n={ps['n']} con colonoscopia</div>
      <div class="ar-big ar-big-pos">{ps['alto_pct']}%</div>
      <div class="ar-desc">{ps['alto']} pacientes con lesión de alto riesgo (sin duplicar)</div>
      <div class="ar-row"><span class="ar-row-label">Adenocarcinoma</span><span class="ar-row-val-pos">{ps['adeno']} ({ps['adeno_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Pólipo ≥ 10mm</span><span class="ar-row-val-pos">{ps['pol']} ({ps['pol_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Ambos criterios (no duplicados)</span><span class="ar-row-val-pos">{ps['overlap_ar']}</span></div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="alto-riesgo-neg">
      <div class="ar-tag ar-tag-neg">FIT Negativo · n={ns['n']} con colonoscopia</div>
      <div class="ar-big ar-big-neg">{ns['alto_pct']}%</div>
      <div class="ar-desc">{ns['alto']} pacientes con lesión de alto riesgo (sin duplicar)</div>
      <div class="ar-row"><span class="ar-row-label">Adenocarcinoma</span><span class="ar-row-val-neg">{ns['adeno']} ({ns['adeno_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Pólipo ≥ 10mm</span><span class="ar-row-val-neg">{ns['pol']} ({ns['pol_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Ambos criterios (no duplicados)</span><span class="ar-row-val-neg">{ns['overlap_ar']}</span></div>
    </div>""", unsafe_allow_html=True)

# ─── Correlación hallazgos ─────────────────────────────────────────────────
st.markdown('<div class="section-title">Correlación FIT vs hallazgo de biopsia · solo pacientes con colonoscopia realizada</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)

with c1:
    fig = go.Figure()
    grupos  = ['ATD/ATV-BG', 'Adenocarcinoma', 'Otros', 'Sin biopsia']
    colores = [COL['atd'], COL['adeno'], COL['otros'], COL['sinbx']]
    pos_vals = [ps['atd_pct'], ps['adeno_pct'], ps['otros_pct'], ps['sin_bx_pct']]
    neg_vals = [ns['atd_pct'], ns['adeno_pct'], ns['otros_pct'], ns['sin_bx_pct']]
    for g, c, pv, nv in zip(grupos, colores, pos_vals, neg_vals):
        fig.add_trace(go.Bar(
            name=g, x=['FIT positivo', 'FIT negativo'],
            y=[pv, nv], marker_color=c,
            text=[f'{pv}%', f'{nv}%'], textposition='inside',
            textfont=dict(size=10, color='white')
        ))
    fig.update_layout(
        barmode='stack', height=280,
        margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0, font=dict(size=11)),
        yaxis=dict(ticksuffix='%', range=[0,100], gridcolor='#f0ede8'),
        xaxis=dict(gridcolor='#f0ede8'),
        font=dict(family='IBM Plex Sans')
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name='FIT positivo', x=['Adenocarcinoma', 'ATD/ATV-BG', 'Pólipo ≥ 10mm'],
        y=[ps['adeno_pct'], ps['atd_pct'], ps['pol_pct']],
        marker_color=COL['pos'],
        text=[f'{ps["adeno_pct"]}%', f'{ps["atd_pct"]}%', f'{ps["pol_pct"]}%'],
        textposition='outside'
    ))
    fig2.add_trace(go.Bar(
        name='FIT negativo', x=['Adenocarcinoma', 'ATD/ATV-BG', 'Pólipo ≥ 10mm'],
        y=[ns['adeno_pct'], ns['atd_pct'], ns['pol_pct']],
        marker_color=COL['neg'],
        text=[f'{ns["adeno_pct"]}%', f'{ns["atd_pct"]}%', f'{ns["pol_pct"]}%'],
        textposition='outside'
    ))
    fig2.update_layout(
        barmode='group', height=280,
        margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0, font=dict(size=11)),
        yaxis=dict(ticksuffix='%', gridcolor='#f0ede8'),
        xaxis=dict(gridcolor='#f0ede8'),
        font=dict(family='IBM Plex Sans')
    )
    st.plotly_chart(fig2, use_container_width=True)

# ─── Medida resumen lesión relevante + pólipo ≥10mm ──────────────────────
st.markdown('<div class="section-title">Medida resumen · lesión relevante = Adenocarcinoma + ATD/ATV-BG + pólipo ≥ 10mm · individuos únicos</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    fig3 = go.Figure(go.Bar(
        x=['FIT positivo', 'FIT negativo'],
        y=[ps['relevante_pct'], ns['relevante_pct']],
        marker_color=[COL['pos'], COL['neg']],
        text=[f"{ps['relevante_pct']}%<br>({ps['relevante']} pac.)", f"{ns['relevante_pct']}%<br>({ns['relevante']} pac.)"],
        textposition='outside', textfont=dict(size=12)
    ))
    fig3.update_layout(
        height=240, margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        yaxis=dict(ticksuffix='%', range=[0,65], gridcolor='#f0ede8'),
        xaxis=dict(gridcolor='#f0ede8'),
        font=dict(family='IBM Plex Sans'),
        showlegend=False
    )
    st.plotly_chart(fig3, use_container_width=True)

with c2:
    fig4 = go.Figure(go.Bar(
        x=['FIT positivo', 'FIT negativo'],
        y=[ps['alto_pct'], ns['alto_pct']],
        marker_color=[COL['pos'], COL['neg']],
        text=[f"{ps['alto_pct']}%<br>({ps['alto']} pac.)", f"{ns['alto_pct']}%<br>({ns['alto']} pac.)"],
        textposition='outside', textfont=dict(size=12)
    ))
    fig4.update_layout(
        height=240, margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        yaxis=dict(ticksuffix='%', range=[0,45], gridcolor='#f0ede8'),
        xaxis=dict(gridcolor='#f0ede8'),
        font=dict(family='IBM Plex Sans'),
        showlegend=False,
        title=dict(text='Lesiones de alto riesgo (Adenoca + Pólipo ≥ 10mm)', font=dict(size=12), x=0)
    )
    st.plotly_chart(fig4, use_container_width=True)

# ─── Avance protocolo ──────────────────────────────────────────────────────
st.markdown('<div class="section-title">Estado de avance del protocolo</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    fig5 = go.Figure(go.Pie(
        labels=['Con colonoscopia', 'Pendiente'],
        values=[s['col_pos'], s['pend_pos']],
        hole=0.65,
        marker_colors=[COL['pos'], COL['pend']],
        textinfo='percent', textfont=dict(size=12)
    ))
    fig5.update_layout(
        height=220, margin=dict(l=0,r=0,t=30,b=0),
        paper_bgcolor='white',
        title=dict(text=f"FIT positivos (n={s['pos_n']})", font=dict(size=12), x=0.5),
        showlegend=False, font=dict(family='IBM Plex Sans'),
        annotations=[dict(text=f"{s['col_pos']}<br>colono", x=0.5, y=0.5, font_size=13, showarrow=False)]
    )
    st.plotly_chart(fig5, use_container_width=True)

with c2:
    fig6 = go.Figure(go.Pie(
        labels=['Con colonoscopia', 'Pendiente'],
        values=[s['col_neg'], s['pend_neg']],
        hole=0.65,
        marker_colors=[COL['neg'], COL['pend']],
        textinfo='percent', textfont=dict(size=12)
    ))
    fig6.update_layout(
        height=220, margin=dict(l=0,r=0,t=30,b=0),
        paper_bgcolor='white',
        title=dict(text=f"FIT negativos (n={s['neg_n']})", font=dict(size=12), x=0.5),
        showlegend=False, font=dict(family='IBM Plex Sans'),
        annotations=[dict(text=f"{s['col_neg']}<br>colono", x=0.5, y=0.5, font_size=13, showarrow=False)]
    )
    st.plotly_chart(fig6, use_container_width=True)

with c3:
    st.markdown(f"""
    <div class="metric-card" style="margin-top:0">
      <div class="metric-label">Perfil clínico</div>
      <div style="margin-top:10px">
        {''.join([f'<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f0ede8;font-size:0.82rem"><span style="color:#888">{l}</span><span style="font-weight:500">{v}</span></div>' for l,v in [
          ("Edad prom. positivos", f"{s['edad_pos']} años"),
          ("Edad prom. negativos", f"{s['edad_neg']} años"),
          ("Días Bp prom. positivos", f"{ps.get('dias_prom','—')} días"),
          ("Días Bp prom. negativos", f"{ns.get('dias_prom','—')} días"),
          ("Colonoscopias totales", f"{s['col_pos']+s['col_neg']}"),
          ("Pendientes totales", f"{s['pend_pos']+s['pend_neg']}"),
        ]])}
      </div>
    </div>""", unsafe_allow_html=True)

# ─── Footer ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:2rem;padding-top:1rem;border-top:1px solid #e8e5df;font-size:0.72rem;color:#bbb;text-align:center">
  Dashboard FIT 2025–26 · Positivo definido como ≥ 20 ng/ml · Solo pacientes con colonoscopia realizada para análisis de biopsia
</div>""", unsafe_allow_html=True)
