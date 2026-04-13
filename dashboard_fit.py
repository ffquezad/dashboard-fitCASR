import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
import io
import gspread
from google.oauth2.service_account import Credentials
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import Image as RLImage
from datetime import date

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

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PehfqMGou02S6F9xGQIRsKmhpTmgoliyt6ODd7Qe2iY/edit"

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
    ws = gc.open_by_url(SPREADSHEET_URL).worksheet("FIT")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    for col in ['Resultado FIT', 'EDAD', 'Dias Bp']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['resultado_num'] = df['Resultado FIT']
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

def has_colono(df_sub):
    return df_sub['F. COLONOSCOPIA'].notna() & (df_sub['F. COLONOSCOPIA'] != '')

# ── Generar PDF ────────────────────────────────────────────────────────────
def generar_pdf(df, pos_n, neg_n, sin_n, con_res, col_pos, col_neg, pend_pos, pend_neg,
                edad_pos, edad_neg, ps, ns):
    AZUL_OSC  = colors.HexColor('#1a1a2e')
    ROJO      = colors.HexColor('#c0392b')
    VERDE     = colors.HexColor('#1a7a4a')
    GRIS_CLAR = colors.HexColor('#f8f7f4')
    GRIS_BOR  = colors.HexColor('#e8e5df')
    GRIS_TXT  = colors.HexColor('#666666')
    ROJO_CLAR = colors.HexColor('#fdf0ef')
    VERDE_CLAR= colors.HexColor('#eef7f1')
    W, H = A4
    PW = W - 3.6*cm

    def e(name, **kw):
        base = dict(fontName='Helvetica', fontSize=9, leading=13, textColor=AZUL_OSC)
        base.update(kw)
        return ParagraphStyle(name, **base)

    s_titulo = e('t', fontSize=18, fontName='Helvetica-Bold', leading=22, textColor=colors.white)
    s_sub    = e('s', fontSize=8, textColor=colors.HexColor('#aaaacc'), leading=11)
    s_sec    = e('sc', fontSize=7, fontName='Helvetica-Bold', textColor=GRIS_TXT, spaceBefore=10, spaceAfter=5)
    s_nota   = e('n', fontSize=7.5, leading=11, textColor=GRIS_TXT)
    s_footer = e('f', fontSize=7, textColor=GRIS_TXT, alignment=TA_CENTER)
    s_ml     = e('ml', fontSize=7.5, leading=10, textColor=GRIS_TXT, alignment=TA_CENTER)
    s_mv_r   = e('mr', fontSize=22, fontName='Helvetica-Bold', leading=26, textColor=ROJO, alignment=TA_CENTER)
    s_mv_g   = e('mg', fontSize=22, fontName='Helvetica-Bold', leading=26, textColor=VERDE, alignment=TA_CENTER)
    s_mv_n   = e('mn', fontSize=22, fontName='Helvetica-Bold', leading=26, textColor=AZUL_OSC, alignment=TA_CENTER)
    s_ms     = e('ms', fontSize=7, leading=9, textColor=GRIS_TXT, alignment=TA_CENTER)
    s_ar_br  = e('abr', fontSize=32, fontName='Helvetica-Bold', leading=36, textColor=ROJO, alignment=TA_CENTER)
    s_ar_bg  = e('abg', fontSize=32, fontName='Helvetica-Bold', leading=36, textColor=VERDE, alignment=TA_CENTER)
    s_ar_lr  = e('alr', fontSize=7.5, fontName='Helvetica-Bold', textColor=colors.HexColor('#922b21'), alignment=TA_CENTER)
    s_ar_lg  = e('alg', fontSize=7.5, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a7a4a'), alignment=TA_CENTER)
    s_ar_d   = e('ard', fontSize=8, leading=11, textColor=GRIS_TXT, alignment=TA_CENTER)
    s_fp     = e('fp', fontSize=8, fontName='Helvetica-Bold', textColor=colors.HexColor('#922b21'), alignment=TA_CENTER)
    s_fn     = e('fn', fontSize=8, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a7a4a'), alignment=TA_CENTER)

    hsr_pos = int(df[df['HOSPITAL']=='HSR']['fit_pos'].sum()) if 'HOSPITAL' in df.columns else 0
    hsr_neg = int(df[df['HOSPITAL']=='HSR']['fit_neg'].sum()) if 'HOSPITAL' in df.columns else 0
    hph_pos = int(df[df['HOSPITAL']=='HPH']['fit_pos'].sum()) if 'HOSPITAL' in df.columns else 0
    hph_neg = int(df[df['HOSPITAL']=='HPH']['fit_neg'].sum()) if 'HOSPITAL' in df.columns else 0

    def fig_to_img(fig, w_cm, h_cm):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return RLImage(buf, width=w_cm*cm, height=h_cm*cm)

    story = []
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)

    # Encabezado
    hdr = Table([[
        Paragraph('Protocolo FIT 2025-2026', s_titulo),
        Paragraph(f'Informe · {date.today().strftime("%d/%m/%Y")}', s_sub),
    ]], colWidths=[PW*0.65, PW*0.35])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),AZUL_OSC),
        ('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),
        ('LEFTPADDING',(0,0),(0,-1),16),('RIGHTPADDING',(-1,0),(-1,-1),16),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(1,-1),'RIGHT'),
        ('ROUNDEDCORNERS',[8]),
    ]))
    story.append(hdr)
    story.append(Spacer(1,0.35*cm))
    sub_tbl = Table([[Paragraph('Correlacion FIT vs Colonoscopia · Positivo definido como >= 20 ng/ml · HSR + HPH', s_nota)]], colWidths=[PW])
    sub_tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GRIS_CLAR),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),10),('BOX',(0,0),(-1,-1),0.5,GRIS_BOR)]))
    story.append(sub_tbl)
    story.append(Spacer(1,0.4*cm))

    # 1. Resumen
    story.append(Paragraph('1. RESUMEN GENERAL', s_sec))
    story.append(HRFlowable(width=PW, thickness=0.5, color=GRIS_BOR, spaceAfter=7))
    metrics = Table([[
        [Paragraph('Total en protocolo', s_ml), Paragraph(f'{len(df):,}', s_mv_n), Paragraph('HSR + HPH', s_ms)],
        [Paragraph('FIT positivo (>= 20)', s_ml), Paragraph(str(pos_n), s_mv_r), Paragraph(f'{pct(pos_n,con_res)}% con resultado', s_ms)],
        [Paragraph('FIT negativo (< 20)', s_ml), Paragraph(str(neg_n), s_mv_g), Paragraph(f'{pct(neg_n,con_res)}% con resultado', s_ms)],
        [Paragraph('Sin resultado', s_ml), Paragraph(str(sin_n), s_mv_n), Paragraph('Pasivos / pendientes', s_ms)],
    ]], colWidths=[PW/4]*4)
    metrics.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,GRIS_BOR),('INNERGRID',(0,0),(-1,-1),0.5,GRIS_BOR),
        ('BACKGROUND',(0,0),(-1,-1),colors.white),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(metrics)
    story.append(Spacer(1,0.3*cm))
    ht = Table([
        ['Hospital','Total','FIT positivo','%','FIT negativo','%'],
        ['HSR',hsr_pos+hsr_neg,hsr_pos,f'{pct(hsr_pos,hsr_pos+hsr_neg)}%',hsr_neg,f'{pct(hsr_neg,hsr_pos+hsr_neg)}%'],
        ['HPH',hph_pos+hph_neg,hph_pos,f'{pct(hph_pos,hph_pos+hph_neg)}%',hph_neg,f'{pct(hph_neg,hph_pos+hph_neg)}%'],
        ['Total',len(df),pos_n,f'{pct(pos_n,con_res)}%',neg_n,f'{pct(neg_n,con_res)}%'],
    ], colWidths=[PW*0.18]*6)
    ht.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),AZUL_OSC),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[colors.white,GRIS_CLAR]),
        ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e8e5df')),
        ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BOX',(0,0),(-1,-1),0.5,GRIS_BOR),('INNERGRID',(0,0),(-1,-1),0.3,GRIS_BOR),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('TEXTCOLOR',(2,1),(2,-1),ROJO),('TEXTCOLOR',(4,1),(4,-1),VERDE),
    ]))
    story.append(ht)
    story.append(Spacer(1,0.4*cm))

    # 2. Alto riesgo
    story.append(Paragraph('2. LESIONES DE ALTO RIESGO · Adenocarcinoma + Polipo >= 10mm · individuos unicos', s_sec))
    story.append(HRFlowable(width=PW, thickness=0.5, color=GRIS_BOR, spaceAfter=7))
    CW = PW/2 - 0.3*cm
    def ar_block(lbl_s, big_s, pct_val, n_val, n_total, adeno, adeno_pct, pol, pol_pct, overlap):
        rows = [
            [Paragraph(f'n={n_total} con colonoscopia', lbl_s)],
            [Paragraph(f'{pct_val}%', big_s)],
            [Paragraph(f'{n_val} pacientes con lesion de alto riesgo (sin duplicar)', s_ar_d)],
            [Paragraph(f'Adenocarcinoma: {adeno} ({adeno_pct}%)', s_ar_d)],
            [Paragraph(f'Polipo >= 10mm: {pol} ({pol_pct}%)', s_ar_d)],
            [Paragraph(f'Ambos criterios (no duplicados): {overlap}', s_ar_d)],
        ]
        t = Table(rows, colWidths=[CW])
        t.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        return t
    ar_main = Table([
        [Paragraph('FIT POSITIVO', s_fp), Paragraph('FIT NEGATIVO', s_fn)],
        [ar_block(s_ar_lr,s_ar_br,ps['alto_pct'],ps['alto'],ps['n'],ps['adeno'],ps['adeno_pct'],ps['pol'],ps['pol_pct'],ps['overlap']),
         ar_block(s_ar_lg,s_ar_bg,ns['alto_pct'],ns['alto'],ns['n'],ns['adeno'],ns['adeno_pct'],ns['pol'],ns['pol_pct'],ns['overlap'])],
    ], colWidths=[PW/2, PW/2])
    ar_main.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),ROJO_CLAR),('BACKGROUND',(1,0),(1,-1),VERDE_CLAR),
        ('BOX',(0,0),(0,-1),0.5,colors.HexColor('#f5c6c2')),
        ('BOX',(1,0),(1,-1),0.5,colors.HexColor('#b8dfc8')),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    story.append(ar_main)
    story.append(Spacer(1,0.4*cm))

    # 3. Correlación
    story.append(Paragraph('3. CORRELACION FIT VS BIOPSIA · solo pacientes con colonoscopia', s_sec))
    story.append(HRFlowable(width=PW, thickness=0.5, color=GRIS_BOR, spaceAfter=7))
    bx_data = [
        ['Hallazgo',f'FIT positivo (n={ps["n"]})', '%', f'FIT negativo (n={ns["n"]})', '%'],
        ['Adenocarcinoma', ps['adeno'], f'{ps["adeno_pct"]}%', ns['adeno'], f'{ns["adeno_pct"]}%'],
        ['ATD / ATV-BG', ps['atd'], f'{ps["atd_pct"]}%', ns['atd'], f'{ns["atd_pct"]}%'],
        ['Polipo >= 10mm', ps['pol'], f'{ps["pol_pct"]}%', ns['pol'], f'{ns["pol_pct"]}%'],
        ['NSTB', int(df[df['fit_pos'] & has_colono(df)]['grupo'].eq('NSTB').sum()), f'{ps["nstb_pct"]}%',
                 int(df[df['fit_neg'] & has_colono(df)]['grupo'].eq('NSTB').sum()), f'{ns["nstb_pct"]}%'],
        ['Otros', ps['otros_pct'], f'{ps["otros_pct"]}%', ns['otros_pct'], f'{ns["otros_pct"]}%'],
        ['Lesion relevante*', ps['rel'], f'{ps["rel_pct"]}%', ns['rel'], f'{ns["rel_pct"]}%'],
    ]
    bx_tbl = Table(bx_data, colWidths=[PW*0.32,PW*0.17,PW*0.09,PW*0.17,PW*0.09])
    bx_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),AZUL_OSC),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),
        ('ALIGN',(1,0),(-1,-1),'CENTER'),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[colors.white,GRIS_CLAR]),
        ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e8e5df')),
        ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BOX',(0,0),(-1,-1),0.5,GRIS_BOR),('INNERGRID',(0,0),(-1,-1),0.3,GRIS_BOR),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(0,-1),8),
        ('TEXTCOLOR',(1,1),(2,1),ROJO),('TEXTCOLOR',(3,1),(4,1),ROJO),
    ]))
    story.append(bx_tbl)
    story.append(Spacer(1,0.15*cm))
    story.append(Paragraph('* Lesion relevante = Adenocarcinoma + ATD/ATV-BG + Polipo >= 10mm (individuos unicos)', s_nota))
    story.append(Spacer(1,0.4*cm))

    # 4. Gráficos
    story.append(Paragraph('4. DISTRIBUCION COMPARATIVA', s_sec))
    story.append(HRFlowable(width=PW, thickness=0.5, color=GRIS_BOR, spaceAfter=7))
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2), facecolor='white')
    grupos = ['Adeno','ATD/ATV-BG','Pol>=10mm','NSTB','Otros']
    pv = [ps['adeno_pct'],ps['atd_pct'],ps['pol_pct'],ps['nstb_pct'],ps['otros_pct']]
    nv = [ns['adeno_pct'],ns['atd_pct'],ns['pol_pct'],ns['nstb_pct'],ns['otros_pct']]
    x = range(len(grupos)); w = 0.35
    ax = axes[0]
    b1 = ax.bar([i-w/2 for i in x], pv, width=w, color='#c0392b', alpha=0.9, label='FIT positivo')
    b2 = ax.bar([i+w/2 for i in x], nv, width=w, color='#1a7a4a', alpha=0.9, label='FIT negativo')
    ax.set_xticks(list(x)); ax.set_xticklabels(grupos, fontsize=7.5)
    ax.set_ylabel('%', fontsize=8); ax.set_title('Hallazgos por grupo FIT', fontsize=9, fontweight='bold', pad=6)
    ax.legend(fontsize=7); ax.spines[['top','right']].set_visible(False)
    ax.set_facecolor('white'); ax.grid(axis='y', alpha=0.3, linewidth=0.5)
    for bar in b1:
        h = bar.get_height()
        if h > 0: ax.text(bar.get_x()+bar.get_width()/2, h+0.3, f'{h}%', ha='center', va='bottom', fontsize=6, color='#c0392b')
    for bar in b2:
        h = bar.get_height()
        if h > 0: ax.text(bar.get_x()+bar.get_width()/2, h+0.3, f'{h}%', ha='center', va='bottom', fontsize=6, color='#1a7a4a')
    ax2 = axes[1]
    bb1 = ax2.bar([0-w/2,1-w/2],[ps['alto_pct'],ps['rel_pct']], width=w, color='#c0392b', alpha=0.9, label='FIT positivo')
    bb2 = ax2.bar([0+w/2,1+w/2],[ns['alto_pct'],ns['rel_pct']], width=w, color='#1a7a4a', alpha=0.9, label='FIT negativo')
    ax2.set_xticks([0,1]); ax2.set_xticklabels(['Alto riesgo','Lesion relevante'], fontsize=8.5)
    ax2.set_ylabel('%', fontsize=8); ax2.set_title('Medidas resumen', fontsize=9, fontweight='bold', pad=6)
    ax2.legend(fontsize=7); ax2.spines[['top','right']].set_visible(False)
    ax2.set_facecolor('white'); ax2.grid(axis='y', alpha=0.3, linewidth=0.5)
    for bar in bb1:
        h = bar.get_height()
        ax2.text(bar.get_x()+bar.get_width()/2, h+0.3, f'{h}%', ha='center', va='bottom', fontsize=8, color='#c0392b', fontweight='bold')
    for bar in bb2:
        h = bar.get_height()
        ax2.text(bar.get_x()+bar.get_width()/2, h+0.3, f'{h}%', ha='center', va='bottom', fontsize=8, color='#1a7a4a', fontweight='bold')
    plt.tight_layout(pad=1.2)
    story.append(fig_to_img(fig, w_cm=PW/cm, h_cm=5.5))
    story.append(Spacer(1,0.4*cm))

    # 5. Avance
    story.append(Paragraph('5. ESTADO DE AVANCE DEL PROTOCOLO', s_sec))
    story.append(HRFlowable(width=PW, thickness=0.5, color=GRIS_BOR, spaceAfter=7))
    av_data = [
        ['','FIT positivo','FIT negativo','Total'],
        ['Total pacientes', pos_n, neg_n, pos_n+neg_n],
        ['Con colonoscopia', f'{col_pos} ({pct(col_pos,pos_n)}%)', f'{col_neg} ({pct(col_neg,neg_n)}%)', f'{col_pos+col_neg}'],
        ['Pendiente', f'{pend_pos} ({pct(pend_pos,pos_n)}%)', f'{pend_neg} ({pct(pend_neg,neg_n)}%)', f'{pend_pos+pend_neg}'],
        ['Dias Bp promedio', f'{ps["dias_prom"]} dias', f'{ns["dias_prom"]} dias', '--'],
        ['Edad promedio', f'{edad_pos} anos', f'{edad_neg} anos', '--'],
    ]
    av_tbl = Table(av_data, colWidths=[PW*0.34,PW*0.22,PW*0.22,PW*0.16])
    av_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),AZUL_OSC),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5),
        ('ALIGN',(1,0),(-1,-1),'CENTER'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,GRIS_CLAR]),
        ('BOX',(0,0),(-1,-1),0.5,GRIS_BOR),('INNERGRID',(0,0),(-1,-1),0.3,GRIS_BOR),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(0,-1),8),
    ]))
    story.append(av_tbl)
    story.append(Spacer(1,0.5*cm))
    story.append(HRFlowable(width=PW, thickness=0.5, color=GRIS_BOR, spaceAfter=5))
    story.append(Paragraph(
        f'Informe generado el {date.today().strftime("%d/%m/%Y")} · Protocolo FIT 2025-26 · '
        'HSR + HPH · FIT positivo >= 20 ng/ml', s_footer))

    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf.read()

# ── Cargar datos ────────────────────────────────────────────────────────────
try:
    df = cargar_datos()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

pos_n    = int(df['fit_pos'].sum())
neg_n    = int(df['fit_neg'].sum())
sin_n    = int(df['sin_res'].sum())
con_res  = pos_n + neg_n
col_pos  = int((df[df['fit_pos']]['F. COLONOSCOPIA'].notna() & (df[df['fit_pos']]['F. COLONOSCOPIA'] != '')).sum())
col_neg  = int((df[df['fit_neg']]['F. COLONOSCOPIA'].notna() & (df[df['fit_neg']]['F. COLONOSCOPIA'] != '')).sum())
pend_pos = int((df[df['fit_pos']]['F. COLONOSCOPIA'].isna() | (df[df['fit_pos']]['F. COLONOSCOPIA'] == '')).sum())
pend_neg = int((df[df['fit_neg']]['F. COLONOSCOPIA'].isna() | (df[df['fit_neg']]['F. COLONOSCOPIA'] == '')).sum())
edad_pos = round(df[df['fit_pos']]['EDAD'].mean(),1) if 'EDAD' in df.columns else 0
edad_neg = round(df[df['fit_neg']]['EDAD'].mean(),1) if 'EDAD' in df.columns else 0
ps = seg(df[df['fit_pos'] & has_colono(df)].copy())
ns = seg(df[df['fit_neg'] & has_colono(df)].copy())

# ── Pestañas ────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 Dashboard", "📄 Descargar informe PDF"])

# ═══════════════════════════════════════════════════════════════════════════
# PESTAÑA 1: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("""
    <div style="background:#1a1a2e;color:white;padding:1.2rem 1.8rem;border-radius:12px;margin-bottom:1.5rem">
      <div style="font-size:1.2rem;font-weight:600">🔬 Protocolo FIT 2025–2026</div>
      <div style="font-size:0.78rem;color:rgba(255,255,255,0.55);margin-top:2px">Correlación FIT vs Colonoscopia · HSR + HPH · Positivo ≥ 20 ng/ml · Actualizado automáticamente desde Google Sheets</div>
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

# ═══════════════════════════════════════════════════════════════════════════
# PESTAÑA 2: DESCARGA PDF
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("""
    <div style="background:#1a1a2e;color:white;padding:1.2rem 1.8rem;border-radius:12px;margin-bottom:1.5rem">
      <div style="font-size:1.2rem;font-weight:600">📄 Descargar informe PDF</div>
      <div style="font-size:0.78rem;color:rgba(255,255,255,0.55);margin-top:2px">Genera un informe institucional con los datos actuales del protocolo</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    El informe incluye:
    - Resumen general por hospital
    - Lesiones de alto riesgo (Adenocarcinoma + Pólipo ≥ 10mm)
    - Correlación FIT vs biopsia
    - Gráficos comparativos
    - Estado de avance del protocolo
    """)

    st.markdown("---")

    if st.button("⚙️ Generar informe PDF", type="primary", use_container_width=True):
        with st.spinner("Generando informe... esto toma unos segundos"):
            pdf_bytes = generar_pdf(
                df, pos_n, neg_n, sin_n, con_res,
                col_pos, col_neg, pend_pos, pend_neg,
                edad_pos, edad_neg, ps, ns
            )
        st.success("✅ Informe generado correctamente")
        st.download_button(
            label="⬇️ Descargar PDF",
            data=pdf_bytes,
            file_name=f"Informe_FIT_{date.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
