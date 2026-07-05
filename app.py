"""
Shopee 精选联盟数据分析 - HF Spaces
"""
import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

def analyze_affiliate(file):
    """分析精选联盟数据"""
    if file is None:
        return None, None, None, None, None, None

    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file.name, encoding='utf-8-sig')
        else:
            df = pd.read_excel(file.name)
        df.columns = [c.strip() for c in df.columns]

        # 列名映射
        def find_col(key): 
            return next((c for c in df.columns if key in c), None)

        date_c   = find_col('Waktu Pesanan')
        status_c = find_col('订单状态')
        plat_c   = 'Platform'
        aff_nm   = find_col('Nama Affiliate')
        aff_un   = find_col('Username Affiliate')
        comm_c   = find_col('Estimasi Komisi Affiliate per Pesanan')
        purch_c  = find_col('Nilai Pembelian')
        prod_c   = find_col('产品名称')
        promo_c  = find_col('Jenis Promo')
        cut_c    = find_col('Status Pemotongan')

        def to_num(v):
            try: return float(str(v).replace(',','').replace(' ',''))
            except: return 0.0

        df['_comm']  = df[comm_c].apply(to_num) if comm_c else 0
        df['_purch'] = df[purch_c].apply(to_num) if purch_c else 0
        df['_date']  = pd.to_datetime(df[date_c], errors='coerce') if date_c else pd.NaT
        df['_cut']   = df[cut_c].fillna('') if cut_c else ''

        total      = len(df)
        total_comm = df['_comm'].sum()
        settled    = df[df['_cut'] == 'Telah Dipotong']['_comm'].sum()
        pending    = total_comm - settled
        unique_aff= df[aff_nm].nunique() if aff_nm else 0
        unique_plat= df[plat_c].nunique() if plat_c else 0
        date_range = (f"{df['_date'].min().strftime('%Y-%m-%d')} ~ {df['_date'].max().strftime('%Y-%m-%d')}" 
                     if date_c and not df['_date'].isna().all() else "未知")

        # --- 概览表格 ---
        summary_data = {
            '指标': ['总订单', '日期范围', '预计总佣金', '已结算佣金', '待结算佣金', '合作达人', '推广平台'],
            '数值': [
                str(total), date_range,
                f"Rp {total_comm:,.0f}", f"Rp {settled:,.0f}", f"Rp {pending:,.0f}",
                str(unique_aff), str(unique_plat)
            ]
        }
        summary_df = pd.DataFrame(summary_data)

        # --- 平台分布图表 ---
        if plat_c:
            plat_df = df.groupby(plat_c).agg(
                订单数=('_comm','count'), 总佣金=('_comm','sum'), 销售额=('_purch','sum')
            ).reset_index().sort_values('总佣金', ascending=False)
            plat_df['均佣金'] = plat_df['总佣金'] / plat_df['订单数']
            plat_df.columns = ['平台', '订单数', '总佣金', '销售额', '均佣金']
            plat_df['总佣金_万'] = plat_df['总佣金'] / 10000

            fig_plat = make_subplots(rows=1, cols=2, subplot_titles=('平台佣金分布 (万Rp)', '平台订单数'))
            colors = px.colors.qualitative.Set2[:len(plat_df)]
            fig_plat.add_trace(go.Bar(
                x=plat_df['平台'], y=plat_df['总佣金_万'],
                marker_color=colors, hovertemplate='%{x}<br>%{y:.1f}万Rp<extra></extra>'
            ), row=1, col=1)
            fig_plat.add_trace(go.Bar(
                x=plat_df['平台'], y=plat_df['订单数'],
                marker_color=colors, hovertemplate='%{x}<br>%{y}单<extra></extra>'
            ), row=1, col=2)
            fig_plat.update_layout(title_text='📱 平台分布', showlegend=False, height=400)
            fig_plat.update_xaxes(tickangle=30)
        else:
            fig_plat = None

        # --- 达人排行图表 ---
        if aff_nm:
            aff_df = df.groupby(aff_nm).agg(
                订单数=('_comm','count'), 总佣金=('_comm','sum'), 销售额=('_purch','sum')
            ).reset_index().sort_values('总佣金', ascending=False).head(20)
            aff_df['均佣金'] = aff_df['总佣金'] / aff_df['订单数']
            if aff_un:
                aff_df['用户名'] = df.groupby(aff_nm)[aff_un].first().values
            aff_df.columns = ['达人', '订单数', '总佣金', '销售额', '均佣金', '用户名'][:len(aff_df.columns)]
            if '用户名' in aff_df.columns:
                aff_df['达人'] = aff_df['达人'] + '<br><span style="font-size:11px;color:#888">@' + aff_df['用户名'].astype(str) + '</span>'
            aff_df['总佣金_万'] = aff_df['总佣金'] / 10000
            fig_aff = px.bar(
                aff_df, x='总佣金_万', y='达人', orientation='h',
                title='🏆 达人佣金排行榜 TOP 20',
                color='总佣金_万', color_continuous_scale='Greens',
                hovertemplate='%{y}<br>%{x:.1f}万Rp<extra></extra>'
            )
            fig_aff.update_layout(showlegend=False, height=max(500, len(aff_df)*28))
            fig_aff.update_yaxes(autorange='reversed')
        else:
            fig_aff = None

        # --- 每日趋势 ---
        if date_c:
            daily_df = df.groupby(df['_date'].dt.strftime('%Y-%m-%d')).agg(
                订单数=('_comm','count'), 总佣金=('_comm','sum')
            ).reset_index().sort_values('_date')
            daily_df.columns = ['日期', '订单数', '佣金']
            daily_df['佣金_万'] = daily_df['佣金'] / 10000
            fig_daily = make_subplots(rows=2, cols=1, subplot_titles=('每日佣金 (万Rp)', '每日订单数'))
            fig_daily.add_trace(go.Scatter(
                x=daily_df['日期'], y=daily_df['佣金_万'],
                mode='lines+markers', fill='tozeroy', line=dict(color='#0ea5e9'),
                hovertemplate='%{x}<br>%{y:.1f}万Rp<extra></extra>'
            ), row=1, col=1)
            fig_daily.add_trace(go.Bar(
                x=daily_df['日期'], y=daily_df['订单数'],
                marker_color='#22c55e', hovertemplate='%{x}<br>%{y}单<extra></extra>'
            ), row=2, col=1)
            fig_daily.update_layout(title_text='📈 每日趋势', showlegend=False, height=450)
            fig_daily.update_xaxes(tickangle=30)
        else:
            fig_daily = None

        # --- 促销类型 ---
        if promo_c:
            promo_df = df.groupby(promo_c).agg(
                订单数=('_comm','count'), 总佣金=('_comm','sum')
            ).reset_index().sort_values('总佣金', ascending=False)
            promo_df.columns = ['促销类型', '订单数', '总佣金']
            promo_df['总佣金_万'] = promo_df['总佣金'] / 10000
            fig_promo = px.pie(
                promo_df, values='总佣金_万', names='促销类型',
                title='🎁 促销类型佣金占比',
                hole=0.4, hovertemplate='%{label}<br>%{percent}<br>%{value:.1f}万Rp<extra></extra>'
            )
            fig_promo.update_layout(height=400)
        else:
            fig_promo = None

        return summary_df, fig_plat, fig_aff, fig_daily, fig_promo, None

    except Exception as e:
        import traceback
        return None, None, None, None, None, f"错误：{str(e)}\n{traceback.format_exc()}"


with gr.Blocks(title="Shopee 精选联盟数据分析", theme=gr.themes.Slate(
    primary_hue="blue", secondary_hue="green"
)) as demo:
    gr.Markdown("# 🎯 Shopee 精选联盟数据分析\n\n上传从 Shopee 精选联盟导出的「达人转化报告」进行分析")
    
    with gr.Row():
        file_input = gr.File(
            label="上传文件 (.xlsx / .xls / .csv)",
            file_count=1, file_types=[".xlsx", ".xls", ".csv"],
            scale=3
        )
        analyze_btn = gr.Button("🔍 开始分析", variant="primary", scale=1)

    with gr.Tabs():
        with gr.TabItem("📊 数据概览"):
            overview_out = gr.DataFrame(label="核心指标")
        with gr.TabItem("📱 平台对比"):
            plat_out = gr.Plot()
        with gr.TabItem("🏆 达人排行"):
            aff_out = gr.Plot()
        with gr.TabItem("📈 每日趋势"):
            daily_out = gr.Plot()
        with gr.TabItem("🎁 促销类型"):
            promo_out = gr.Plot()
        with gr.TabItem("⚠️ 错误信息"):
            err_out = gr.Textbox(label="错误信息", lines=10)

    analyze_btn.click(
        fn=analyze_affiliate,
        inputs=[file_input],
        outputs=[overview_out, plat_out, aff_out, daily_out, promo_out, err_out]
    )

demo.launch(server_name="0.0.0.0", server_port=7860)
