import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Dashboard FIT 2025-26", page_icon="🔬", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .block-container { padding: 2rem 2.5rem; max-width: 1400px; }
    .metric-card { background: white; border-radius: 10px; padding: 1.1rem 1.3rem; border: 1px solid #e8e5df; height: 100%; }
    .metric-label { font-size: 0.72rem; font-weight: 500; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
    .metric-value { font-size: 2rem; font-weight: 600; line-height: 1; color: #1a1a2e; }
    .metric-sub { font-size: 0.72rem; color: #aaa; margin-top: 4px; }
    .metric-red .metric-value { color: #c0392b; }
    .metric-green .metric-value { color: #1a7a4a; }
    .section-title { font-size: 0.7rem; font-weight: 600; color: #999; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid #e8e5df; padding-bottom: 6px; margin: 1.5rem 0 1rem; }
    .alto-riesgo-pos { background: #fdf0ef; border: 1px solid #f5c6c2; border-radius: 12px; padding: 1.6rem; height: 100%; }
    .alto-riesgo-neg { background: #eef7f1; border: 1px solid #b8dfc8; border-radius: 12px; padding: 1.6rem; height: 100%; }
    .ar-tag { font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
    .ar-tag-pos { color: #922b21; } .ar-tag-neg { color: #1a7a4a; }
    .ar-big { font-size: 3.2rem; font-weight: 600; line-height: 1; margin-bottom: 2px; }
    .ar-big-pos { color: #c0392b; } .ar-big-neg { color: #1a7a4a; }
    .ar-desc { font-size: 0.78rem; color: #666; margin-bottom: 14px; }
    .ar-row { display: flex; justify-content: space-between; font-size: 0.8rem; padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.07); }
    .ar-row:last-child { border-bottom: none; }
    .ar-row-label { color: #666; }
    .ar-row-val-pos { color: #922b21; font-weight: 600; }
    .ar-row-val-neg { color: #1a7a4a; font-weight: 600; }
    .mini-stat { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0ede8; font-size: 0.82rem; }
    .mini-stat:last-child { border-bottom: none; }
    .mini-label { color: #888; } .mini-val { font-weight: 500; }
</style>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1PYnTTE5DO9VNXOwwjJKTUHcPw93TtcLJ"

@st.cache_data(ttl=300)
def cargar_datos():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("FIT")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    df['resultado_num'] = pd.to_numeric(df['Resultado FIT'], errors='coerce')
    df['fit_pos'] = df['resultado_num'] >= 20
    df['fit_neg'] = (df['resultado_num'] < 20) & df['resultado_num'].notna()
    df['sin_res'] = df['resultado_num'].isna()

    def extract_mm(v):
        if pd.isna(v): return None
        m = re.search(r'(\d+)', str(v))
        return int(m.group(1)) if m else None

    def clasificar(b):
        if pd.isna(b): return 'Sin biopsia'
        b = str(b).upper()
        if 'ADENOCARCINOMA' in b: return 'Adenocarcinoma'
        if 'NSTB' in b: return 'NSTB'
        if 'ATD' in b or 'ATV' in b: return 'ATD/ATV-BG'
        return 'Otros'

    df['polipo_mm']     = df['POLIPO MAS GRANDE'].apply(extract_mm)
    df['polipo_grande'] = df['polipo_mm'].apply(lambda x: x >= 10 if pd.notna(x) else False)
    df['grupo']         = df['BIOPSIA'].apply(clasificar)
    df['es_adeno']      = df['grupo'] == 'Adenocarcinoma'
    df['es_atd']        = df['grupo'] == 'ATD/ATV-BG'
    df['lesion_alto']   = df['es_adeno'] | df['polipo_grande']
    df['lesion_rel']    = df['es_adeno'] | df['es_atd'] | df['polipo_grande']
    return df

def pct(n, d): return round(n/d*100, 1) if d else 0

def seg(sub):
    n = len(sub)
    if n == 0: return {k: 0 for k in ['n','adeno','atd','pol','alto','rel','overlap','alto_pct','rel_pct','adeno_pct','atd_pct','pol_pct','nstb_pct','otros_pct','sinbx_pct','dias_prom']}
    adeno = int(sub['es_adeno'].sum())
    atd   = int(sub['es_atd'].sum())
    pol   = int(sub['polipo_grande'].sum())
    alto  = int(sub['lesion_alto'].sum())
    rel   = int(sub['lesion_rel'].sum())
    over  = int((sub['es_adeno'] & sub['polipo_grande']).sum())
    dias  = pd.to_numeric(sub['Dias Bp'], errors='coerce')
    dias_v = dias[(dias >= 0) & (dias < 365)]
    return dict(n=n, adeno=adeno, atd=atd, pol=pol, alto=alto, rel=rel, overlap=over,
        alto_pct=pct(alto,n), rel_pct=pct(rel,n), adeno_pct=pct(adeno,n),
        atd_pct=pct(atd,n), pol_pct=pct(pol,n),
        nstb_pct=pct((sub['grupo']=='NSTB').sum(),n),
        otros_pct=pct((sub['grupo']=='Otros').sum(),n),
        sinbx_pct=pct((sub['grupo']=='Sin biopsia').sum(),n),
        dias_prom=round(dias_v.mean(),1) if len(dias_v) else 0)

try:
    df = cargar_datos()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

pos_n   = int(df['fit_pos'].sum())
neg_n   = int(df['fit_neg'].sum())
sin_n   = int(df['sin_res'].sum())
con_res = pos_n + neg_n
col_pos = int(df[df['fit_pos']]['F. COLONOSCOPIA'].notna().sum())
col_neg = int(df[df['fit_neg']]['F. COLONOSCOPIA'].notna().sum())
pend_pos= int(df[df['fit_pos']]['F. COLONOSCOPIA'].isna().sum())
pend_neg= int(df[df['fit_neg']]['F. COLONOSCOPIA'].isna().sum())
edad_pos= round(df[df['fit_pos']]['EDAD'].mean(),1) if 'EDAD' in df.columns else 0
edad_neg= round(df[df['fit_neg']]['EDAD'].mean(),1) if 'EDAD' in df.columns else 0
ps = seg(df[df['fit_pos'] & df['F. COLONOSCOPIA'].notna()].copy())
ns = seg(df[df['fit_neg'] & df['F. COLONOSCOPIA'].notna()].copy())

# ── UI ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#1a1a2e;color:white;padding:1.2rem 1.8rem;border-radius:12px;margin-bottom:1.5rem">
  <div style="font-size:1.2rem;font-weight:600">🔬 Protocolo FIT 2025–2026</div>
  <div style="font-size:0.78rem;color:rgba(255,255,255,0.55);margin-top:2px">Correlación FIT vs Colonoscopia · HSR + HPH · Positivo ≥ 20 ng/ml · Se actualiza automáticamente desde Google Sheets</div>
</div>
""", unsafe_allow_html=True)

if st.button("🔄 Actualizar datos ahora"):
    st.cache_data.clear()
    st.rerun()

c1,c2,c3,c4 = st.columns(4)
for col,label,val,sub,cls in [
    (c1,"Total en protocolo",len(df),f"Colonoscopias: {col_pos+col_neg}",""),
    (c2,"FIT positivo (≥ 20 ng/ml)",pos_n,f"{pct(pos_n,con_res)}% de los con resultado","metric-red"),
    (c3,"FIT negativo (< 20 ng/ml)",neg_n,f"{pct(neg_n,con_res)}% de los con resultado","metric-green"),
    (c4,"Sin resultado",sin_n,"Pasivos / pendientes",""),
]:
    with col:
        st.markdown(f'<div class="metric-card {cls}"><div class="metric-label">{label}</div><div class="metric-value">{val:,}</div><div class="metric-sub">{sub}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Lesiones de alto riesgo · Adenocarcinoma + Pólipo ≥ 10mm · individuos únicos · solo con colonoscopia</div>', unsafe_allow_html=True)
c1,c2 = st.columns(2)
with c1:
    st.markdown(f"""<div class="alto-riesgo-pos">
      <div class="ar-tag ar-tag-pos">FIT Positivo · n={ps['n']} con colonoscopia</div>
      <div class="ar-big ar-big-pos">{ps['alto_pct']}%</div>
      <div class="ar-desc">{ps['alto']} pacientes con lesión de alto riesgo (sin duplicar)</div>
      <div class="ar-row"><span class="ar-row-label">Adenocarcinoma</span><span class="ar-row-val-pos">{ps['adeno']} ({ps['adeno_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Pólipo ≥ 10mm</span><span class="ar-row-val-pos">{ps['pol']} ({ps['pol_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Ambos criterios (no duplicados)</span><span class="ar-row-val-pos">{ps['overlap']}</span></div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="alto-riesgo-neg">
      <div class="ar-tag ar-tag-neg">FIT Negativo · n={ns['n']} con colonoscopia</div>
      <div class="ar-big ar-big-neg">{ns['alto_pct']}%</div>
      <div class="ar-desc">{ns['alto']} pacientes con lesión de alto riesgo (sin duplicar)</div>
      <div class="ar-row"><span class="ar-row-label">Adenocarcinoma</span><span class="ar-row-val-neg">{ns['adeno']} ({ns['adeno_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Pólipo ≥ 10mm</span><span class="ar-row-val-neg">{ns['pol']} ({ns['pol_pct']}%)</span></div>
      <div class="ar-row"><span class="ar-row-label">Ambos criterios (no duplicados)</span><span class="ar-row-val-neg">{ns['overlap']}</span></div>
    </div>""", unsafe_allow_html=True)

st.markdown('<div class="section-title">Correlación FIT vs hallazgo de biopsia · solo pacientes con colonoscopia realizada</div>', unsafe_allow_html=True)
c1,c2 = st.columns(2)
with c1:
    fig = go.Figure()
    for lbl,pv,nv,color in [
        ('ATD/ATV-BG',ps['atd_pct'],ns['atd_pct'],'#1a7a4a'),
        ('Adenocarcinoma',ps['adeno_pct'],ns['adeno_pct'],'#c0392b'),
        ('Otros',ps['otros_pct'],ns['otros_pct'],'#b7950b'),
        ('Sin biopsia',ps['sinbx_pct'],ns['sinbx_pct'],'#aab7b8'),
    ]:
        fig.add_trace(go.Bar(name=lbl,x=['FIT positivo','FIT negativo'],y=[pv,nv],
            marker_color=color,text=[f'{pv}%',f'{nv}%'],textposition='inside',textfont=dict(size=10,color='white')))
    fig.update_layout(barmode='stack',height=280,margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor='white',plot_bgcolor='white',
        legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='left',x=0,font=dict(size=11)),
        yaxis=dict(ticksuffix='%',range=[0,100],gridcolor='#f0ede8'),xaxis=dict(gridcolor='#f0ede8'))
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name='FIT positivo',x=['Adenocarcinoma','ATD/ATV-BG','Pólipo ≥ 10mm'],
        y=[ps['adeno_pct'],ps['atd_pct'],ps['pol_pct']],marker_color='#c0392b',
        text=[f'{ps["adeno_pct"]}%',f'{ps["atd_pct"]}%',f'{ps["pol_pct"]}%'],textposition='outside'))
    fig2.add_trace(go.Bar(name='FIT negativo',x=['Adenocarcinoma','ATD/ATV-BG','Pólipo ≥ 10mm'],
        y=[ns['adeno_pct'],ns['atd_pct'],ns['pol_pct']],marker_color='#1a7a4a',
        text=[f'{ns["adeno_pct"]}%',f'{ns["atd_pct"]}%',f'{ns["pol_pct"]}%'],textposition='outside'))
    fig2.update_layout(barmode='group',height=280,margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor='white',plot_bgcolor='white',
        legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='left',x=0,font=dict(size=11)),
        yaxis=dict(ticksuffix='%',gridcolor='#f0ede8'),xaxis=dict(gridcolor='#f0ede8'))
    st.plotly_chart(fig2, use_container_width=True)

st.markdown('<div class="section-title">Medida resumen · lesión relevante = Adenocarcinoma + ATD/ATV-BG + Pólipo ≥ 10mm · individuos únicos</div>', unsafe_allow_html=True)
c1,c2 = st.columns(2)
with c1:
    fig3 = go.Figure(go.Bar(x=['FIT positivo','FIT negativo'],y=[ps['rel_pct'],ns['rel_pct']],
        marker_color=['#c0392b','#1a7a4a'],
        text=[f"{ps['rel_pct']}%<br>({ps['rel']} pac.)",f"{ns['rel_pct']}%<br>({ns['rel']} pac.)"],
        textposition='outside',textfont=dict(size=12)))
    fig3.update_layout(height=240,margin=dict(l=0,r=0,t=30,b=0),showlegend=False,
        title=dict(text='Lesión relevante',font=dict(size=12),x=0),
        paper_bgcolor='white',plot_bgcolor='white',
        yaxis=dict(ticksuffix='%',range=[0,65],gridcolor='#f0ede8'))
    st.plotly_chart(fig3, use_container_width=True)
with c2:
    fig4 = go.Figure(go.Bar(x=['FIT positivo','FIT negativo'],y=[ps['alto_pct'],ns['alto_pct']],
        marker_color=['#c0392b','#1a7a4a'],
        text=[f"{ps['alto_pct']}%<br>({ps['alto']} pac.)",f"{ns['alto_pct']}%<br>({ns['alto']} pac.)"],
        textposition='outside',textfont=dict(size=12)))
    fig4.update_layout(height=240,margin=dict(l=0,r=0,t=30,b=0),showlegend=False,
        title=dict(text='Lesiones de alto riesgo (Adenoca + Pólipo ≥ 10mm)',font=dict(size=12),x=0),
        paper_bgcolor='white',plot_bgcolor='white',
        yaxis=dict(ticksuffix='%',range=[0,45],gridcolor='#f0ede8'))
    st.plotly_chart(fig4, use_container_width=True)

st.markdown('<div class="section-title">Estado de avance del protocolo</div>', unsafe_allow_html=True)
c1,c2,c3 = st.columns(3)
with c1:
    fig5 = go.Figure(go.Pie(labels=['Con colonoscopia','Pendiente'],values=[col_pos,pend_pos],
        hole=0.65,marker_colors=['#c0392b','#d5d8dc'],textinfo='percent',textfont=dict(size=12)))
    fig5.update_layout(height=220,margin=dict(l=0,r=0,t=30,b=0),showlegend=False,
        title=dict(text=f"FIT positivos (n={pos_n})",font=dict(size=12),x=0.5),
        paper_bgcolor='white',annotations=[dict(text=f"{col_pos}<br>colono",x=0.5,y=0.5,font_size=13,showarrow=False)])
    st.plotly_chart(fig5, use_container_width=True)
with c2:
    fig6 = go.Figure(go.Pie(labels=['Con colonoscopia','Pendiente'],values=[col_neg,pend_neg],
        hole=0.65,marker_colors=['#1a7a4a','#d5d8dc'],textinfo='percent',textfont=dict(size=12)))
    fig6.update_layout(height=220,margin=dict(l=0,r=0,t=30,b=0),showlegend=False,
        title=dict(text=f"FIT negativos (n={neg_n})",font=dict(size=12),x=0.5),
        paper_bgcolor='white',annotations=[dict(text=f"{col_neg}<br>colono",x=0.5,y=0.5,font_size=13,showarrow=False)])
    st.plotly_chart(fig6, use_container_width=True)
with c3:
    st.markdown(f"""<div class="metric-card"><div class="metric-label">Perfil clínico</div><div style="margin-top:10px">
      <div class="mini-stat"><span class="mini-label">Edad prom. positivos</span><span class="mini-val">{edad_pos} años</span></div>
      <div class="mini-stat"><span class="mini-label">Edad prom. negativos</span><span class="mini-val">{edad_neg} años</span></div>
      <div class="mini-stat"><span class="mini-label">Días Bp prom. positivos</span><span class="mini-val">{ps['dias_prom']} días</span></div>
      <div class="mini-stat"><span class="mini-label">Días Bp prom. negativos</span><span class="mini-val">{ns['dias_prom']} días</span></div>
      <div class="mini-stat"><span class="mini-label">Colonoscopias totales</span><span class="mini-val">{col_pos+col_neg}</span></div>
      <div class="mini-stat"><span class="mini-label">Pendientes totales</span><span class="mini-val">{pend_pos+pend_neg}</span></div>
    </div></div>""", unsafe_allow_html=True)

st.markdown('<div style="margin-top:2rem;padding-top:1rem;border-top:1px solid #e8e5df;font-size:0.72rem;color:#bbb;text-align:center">Dashboard FIT 2025–26 · Positivo ≥ 20 ng/ml · Datos actualizados automáticamente desde Google Sheets cada 5 minutos</div>', unsafe_allow_html=True)
