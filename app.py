"""
Shopee 精选联盟数据分析 - Hugging Face Spaces
"""
import gradio as gr
import pandas as pd
import json
from datetime import datetime

def parse_file(file):
    """解析上传的 Excel/CSV 文件"""
    if file is None:
        return None, None, None, None, None, None, None
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file.name, encoding='utf-8-sig')
        else:
            df = pd.read_excel(file.name)
        return df, None, None, None, None, None, None
    except Exception as e:
        return None, str(e), None, None, None, None, None

def analyze_affiliate(file):
    """分析精选联盟数据"""
    if file is None:
        return "请上传文件", {}, {}, {}, {}

    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file.name, encoding='utf-8-sig')
        else:
            df = pd.read_excel(file.name)

        # 标准化列名
        df.columns = [c.strip() for c in df.columns]

        # 找关键列
        date_col = next((c for c in df.columns if 'Waktu Pesanan' in c or '订单时间' in c), None)
        status_col = next((c for c in df.columns if '订单状态' in c), None)
        plat_col = next((c for c in df.columns if c == 'Platform'), None)
        aff_name_col = next((c for c in df.columns if 'Nama Affiliate' in c), None)
        aff_user_col = next((c for c in df.columns if 'Username Affiliate' in c), None)
        comm_col = next((c for c in df.columns if 'Estimasi Komisi Affiliate per Pesanan' in c), None)
        purch_col = next((c for c in df.columns if 'Nilai Pembelian' in c and 'Estimasi' not in c), None)
        prod_col = next((c for c in df.columns if '产品名称' in c), None)
        promo_col = next((c for c in df.columns if 'Jenis Promo' in c), None)
        cut_col = next((c for c in df.columns if 'Status Pemotongan' in c), None)

        # 解析佣金
        def to_num(val):
            try:
                return float(str(val).replace(',', '').replace(' ', ''))
            except:
                return 0.0

        df['_comm'] = df[comm_col].apply(to_num) if comm_col else 0
        df['_purch'] = df[purch_col].apply(to_num) if purch_col else 0
        df['_date'] = pd.to_datetime(df[date_col], errors='coerce') if date_col else pd.NaT
        df['_cut'] = df[cut_col].fillna('') if cut_col else ''

        total = len(df)
        total_comm = df['_comm'].sum()
        settled = df[df['_cut'] == 'Telah Dipotong']['_comm'].sum()
        pending = total_comm - settled

        # 状态统计
        if status_col:
            status_counts = df[status_col].value_counts().to_dict()
        else:
            status_counts = {}

        # 平台统计
        if plat_col:
            plat_stats = df.groupby(plat_col).agg(
                订单数=('_comm', 'count'),
                总佣金=('_comm', 'sum'),
                销售额=('_purch', 'sum')
            ).reset_index()
            plat_stats['均佣金'] = plat_stats['总佣金'] / plat_stats['订单数']
            plat_stats = plat_stats.sort_values('总佣金', ascending=False)
        else:
            plat_stats = pd.DataFrame(columns=['Platform', '订单数', '总佣金', '销售额', '均佣金'])

        # 达人排行
        if aff_name_col and comm_col:
            aff_stats = df.groupby(aff_name_col).agg(
                订单数=('_comm', 'count'),
                总佣金=('_comm', 'sum'),
                销售额=('_purch', 'sum')
            ).reset_index()
            if aff_user_col:
                aff_stats['用户名'] = df.groupby(aff_name_col)[aff_user_col].first().values
            aff_stats['均佣金'] = aff_stats['总佣金'] / aff_stats['订单数']
            aff_stats = aff_stats.sort_values('总佣金', ascending=False).head(20)
        else:
            aff_stats = pd.DataFrame()

        # 每日趋势
        if date_col:
            daily_stats = df.groupby(df['_date'].dt.strftime('%Y-%m-%d')).agg(
                订单数=('_comm', 'count'),
                总佣金=('_comm', 'sum')
            ).reset_index()
            daily_stats.columns = ['日期', '订单数', '佣金']
            daily_stats = daily_stats.sort_values('日期')
        else:
            daily_stats = pd.DataFrame()

        # 促销类型
        if promo_col:
            promo_stats = df.groupby(promo_col).agg(
                订单数=('_comm', 'count'),
                总佣金=('_comm', 'sum')
            ).reset_index().sort_values('总佣金', ascending=False)
        else:
            promo_stats = pd.DataFrame()

        # 日期范围
        if date_col:
            date_range = f"{df['_date'].min().strftime('%Y-%m-%d')} ~ {df['_date'].max().strftime('%Y-%m-%d')}"
        else:
            date_range = "未知"

        unique_aff = df[aff_name_col].nunique() if aff_name_col else 0
        unique_plat = df[plat_col].nunique() if plat_col else 0

        # 返回概览文本
        overview = f"""**📊 数据概览**
- 总订单：**{total} 条**
- 日期范围：{date_range}
- 预计总佣金：**Rp {total_comm:,.0f}**
- 已结算佣金：Rp {settled:,.0f}
- 待结算佣金：Rp {pending:,.0f}
- 合作达人：{unique_aff} 位
- 推广平台：{unique_plat} 个"""

        return overview, plat_stats, aff_stats, daily_stats, promo_stats, status_counts, df

    except Exception as e:
        import traceback
        return f"解析错误：{str(e)}\n{traceback.format_exc()}", pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, None


# Gradio UI
with gr.Blocks(title="Shopee 精选联盟数据分析", theme=gr.themes.Slate()) as demo:
    gr.Markdown("# 🎯 Shopee 精选联盟数据分析")

    with gr.Row():
        file_input = gr.File(
            label="上传精选联盟数据 (.xlsx / .xls / .csv)",
            file_count=1,
            file_types=[".xlsx", ".xls", ".csv"]
        )
        analyze_btn = gr.Button("开始分析", variant="primary")

    with gr.Tabs():
        with gr.TabItem("📊 概览"):
            overview_out = gr.Markdown()
        with gr.TabItem("📱 平台对比"):
            plat_out = gr.DataFrame(label="平台分布")
        with gr.TabItem("🏆 达人排行"):
            aff_out = gr.DataFrame(label="TOP 20 达人")
        with gr.TabItem("📈 每日趋势"):
            daily_out = gr.DataFrame(label="每日数据")
        with gr.TabItem("🎁 促销类型"):
            promo_out = gr.DataFrame(label="促销类型佣金")

    analyze_btn.click(
        fn=analyze_affiliate,
        inputs=[file_input],
        outputs=[overview_out, plat_out, aff_out, daily_out, promo_out]
    )

demo.launch(server_name="0.0.0.0", server_port=7860)
