"""ReportLab で法規検討計算書PDFを生成する"""
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from core.site_model import SiteModel
from core.boundary_classifier import BoundaryEdge, extract_edges
from calculations.coverage_far import CoverageFARResult
from calculations.setback_shadow import RoadSlopeResult, AdjacentSlopeResult, ShadowResult


def _register_font() -> str:
    for path, name in [
        ("C:/Windows/Fonts/msgothic.ttc", "MSGothic"),
        ("C:/Windows/Fonts/meiryo.ttc", "Meiryo"),
        ("C:/Windows/Fonts/YuGothR.ttc", "YuGothic"),
    ]:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return "Helvetica"


def _make_table(data, font, col_widths=None):
    style = [
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8f5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle(style))
    return t


def generate_boundary_check_pdf(polygon, output_path: str | Path, edges: list | None = None) -> Path:
    """境界確認用PDF（番号付き敷地図）CADソフト不要で辺番号を確認できる"""
    output_path = Path(output_path)
    font = _register_font()

    PAGE_W, PAGE_H = A4          # 595 x 842 pt
    MARGIN = 30 * mm
    DRAW_W = PAGE_W - MARGIN * 2
    DRAW_H = PAGE_H - MARGIN * 2 - 30 * mm   # 上部にタイトル領域

    if edges is None:
        edges = extract_edges(polygon)

    # 座標スケーリング: ポリゴンを描画領域に収める
    coords = list(polygon.exterior.coords)
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0
    scale = min(DRAW_W / span_x, DRAW_H / span_y) * 0.85   # 85% に収める

    # 描画領域の中心に配置するオフセット
    draw_cx = MARGIN + DRAW_W / 2
    draw_cy = MARGIN + DRAW_H / 2 + 10 * mm
    site_cx = (min_x + max_x) / 2
    site_cy = (min_y + max_y) / 2

    def tx(x):   # 実座標 → PDF pt
        return draw_cx + (x - site_cx) * scale

    def ty(y):   # 実座標 → PDF pt（Y軸反転）
        return draw_cy + (y - site_cy) * scale

    c = rl_canvas.Canvas(str(output_path), pagesize=A4)
    c.setFont(font, 14)
    c.setFillColorRGB(0.1, 0.22, 0.36)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 20 * mm, "境界確認図（辺番号確認用）")
    c.setFont(font, 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 26 * mm,
                        "道路境界・隣地境界を番号で指定するための参考図です")

    # 凡例
    legend_x = MARGIN
    legend_y = 22 * mm
    c.setFont(font, 8)
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(1.0, 0.85, 0.0)
    c.setLineWidth(1.5)
    c.line(legend_x, legend_y, legend_x + 15, legend_y)
    c.setFillColorRGB(1.0, 0.85, 0.0)
    c.drawString(legend_x + 18, legend_y - 3, "道路境界")
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.line(legend_x + 60, legend_y, legend_x + 75, legend_y)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(legend_x + 78, legend_y - 3, "隣地境界（未設定含む）")

    # 敷地ポリゴン
    path = c.beginPath()
    path.moveTo(tx(coords[0][0]), ty(coords[0][1]))
    for cx_, cy_ in coords[1:]:
        path.lineTo(tx(cx_), ty(cy_))
    path.close()
    c.setFillColorRGB(0.93, 0.96, 1.0)
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.setLineWidth(0.5)
    c.drawPath(path, fill=1, stroke=1)

    # 各辺を描画して番号・距離を注記
    for e in edges:
        sx, sy = e.start
        ex, ey = e.end

        # 辺の色（設定済みの場合は道路=黄、隣地=グレー）
        if e.kind == "道路":
            c.setStrokeColorRGB(1.0, 0.85, 0.0)
            c.setLineWidth(2.5)
        else:
            c.setStrokeColorRGB(0.3, 0.3, 0.3)
            c.setLineWidth(1.5)

        c.line(tx(sx), ty(sy), tx(ex), ty(ey))

        # 中点・外向き法線
        mid = e.midpoint
        dx = ey - sy
        dy = -(ex - sx)
        length = (dx**2 + dy**2) ** 0.5
        offset_m = e.length_m * 0.08
        if length > 0:
            nx = dx / length * offset_m * scale * 1.8
            ny = dy / length * offset_m * scale * 1.8
        else:
            nx, ny = offset_m * scale, offset_m * scale

        label_x = tx(mid.x) + nx
        label_y = ty(mid.y) + ny

        # 番号ラベル（円囲み）
        font_size = max(7.0, min(11.0, e.length_m * scale * 0.06))
        radius = font_size * 0.85
        c.setFillColorRGB(0.1, 0.22, 0.36)
        c.setStrokeColorRGB(1, 1, 1)
        c.setLineWidth(0.5)
        c.circle(label_x, label_y + radius * 0.3, radius, fill=1, stroke=1)
        c.setFont(font, font_size * 0.9)
        c.setFillColorRGB(1, 1, 1)
        c.drawCentredString(label_x, label_y, str(e.index))

        # 距離ラベル
        dist_font = max(6.0, font_size * 0.85)
        c.setFont(font, dist_font)
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.drawCentredString(label_x, label_y - radius * 2.2, f"{e.length_m:.1f}m")

    # 注釈テーブル（辺番号・長さ）
    table_x = PAGE_W - MARGIN - 55 * mm
    table_y = MARGIN + DRAW_H - 5 * mm
    c.setFont(font, 7)
    c.setFillColorRGB(0.1, 0.22, 0.36)
    c.drawString(table_x, table_y, "辺番号一覧")
    row_h = 4.5 * mm
    for i, e in enumerate(edges):
        ry = table_y - (i + 1) * row_h
        if e.kind == "道路":
            c.setFillColorRGB(1.0, 0.95, 0.7)
            c.rect(table_x, ry - 1 * mm, 50 * mm, row_h, fill=1, stroke=0)
            label = "道路"
            c.setFillColorRGB(0.5, 0.3, 0)
        elif e.kind == "隣地":
            c.setFillColorRGB(0.95, 0.95, 0.95)
            c.rect(table_x, ry - 1 * mm, 50 * mm, row_h, fill=1, stroke=0)
            label = "隣地"
            c.setFillColorRGB(0.2, 0.2, 0.2)
        else:
            c.setFillColorRGB(0.98, 0.98, 0.98)
            c.rect(table_x, ry - 1 * mm, 50 * mm, row_h, fill=1, stroke=0)
            label = "未設定"
            c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont(font, 7)
        c.drawString(table_x + 2 * mm, ry, f"辺{e.index}: {e.length_m:.2f}m  [{label}]")

    c.save()
    return output_path


def generate_pdf(site, far_result, road_slope, adj_slope, shadow, boundary, output_path):
    output_path = Path(output_path)
    font = _register_font()

    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    title_s = ParagraphStyle("T", fontName=font, fontSize=16, spaceAfter=6,
                              textColor=colors.HexColor("#1a3a5c"), leading=20)
    sec_s   = ParagraphStyle("S", fontName=font, fontSize=11, spaceAfter=4,
                              textColor=colors.HexColor("#1a3a5c"), leading=16)
    body_s  = ParagraphStyle("B", fontName=font, fontSize=9, spaceAfter=2, leading=14)
    note_s  = ParagraphStyle("N", fontName=font, fontSize=8, textColor=colors.grey,
                              spaceAfter=2, leading=12)

    story = []
    story.append(Paragraph("建築法規検討計算書", title_s))
    story.append(Paragraph(
        f"作成日: {datetime.now().strftime('%Y年%m月%d日')}　所在地: {site.address}", body_s))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("1. 敷地概要", sec_s))
    parcels = " + ".join(site.parcel_numbers) if site.parcel_numbers else "—"
    story.append(_make_table([
        ["項目", "内容"],
        ["地番", parcels],
        ["所在地", site.address],
        ["用途地域", site.zone_info.zone_name],
        ["防火地域", site.fire_zone or "指定なし"],
        ["敷地面積", f"{site.site_area_m2:.2f} m²"],
        ["前面道路幅員", f"{site.main_road.width_m:.1f} m ({site.main_road.direction})" if site.main_road else "不明"],
    ], font, [50*mm, 120*mm]))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("2. 建蔽率・容積率（建築基準法第52・53条）", sec_s))
    story.append(_make_table([
        ["項目", "規制値", "計算値"],
        ["建蔽率", f"{site.zone_info.coverage_ratio*100:.0f}%",
         f"{far_result.max_coverage_ratio*100:.0f}%"],
        ["最大建築面積", "—", f"{far_result.max_building_area_m2:.2f} m²"],
        ["容積率（指定）", f"{site.zone_info.floor_area_ratio*100:.0f}%", f"{far_result.max_far*100:.0f}%"],
        ["容積率（道路制限）", "—", f"{far_result.road_far_limit*100:.0f}%"],
        ["容積率（有効）", "—", f"{far_result.effective_far*100:.0f}%"],
        ["最大延床面積", "—", f"{far_result.effective_total_floor_area_m2:.2f} m²"],
    ], font))
    for n in far_result.notes:
        story.append(Paragraph(f"※ {n}", note_s))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("3. 道路斜線制限（建築基準法第56条第1項第1号）", sec_s))
    if road_slope and road_slope.road_width_m > 0:
        story.append(_make_table([
            ["項目", "内容"],
            ["前面道路幅員", f"{road_slope.road_width_m:.1f} m"],
            ["斜線勾配", f"1 : {road_slope.slope_ratio}"],
            ["道路境界での最大高さ", f"{road_slope.max_height_at_boundary_m:.1f} m"],
            ["適用水平距離", f"{road_slope.applicable_distance_m:.0f} m"],
        ], font, [70*mm, 100*mm]))
        for n in road_slope.notes:
            story.append(Paragraph(f"※ {n}", note_s))
    else:
        story.append(Paragraph("前面道路データ未入力のため省略", body_s))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("4. 隣地斜線制限（建築基準法第56条第1項第2号）", sec_s))
    for n in adj_slope.notes:
        story.append(Paragraph(f"※ {n}", body_s))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("5. 日影規制（建築基準法第56条の2）", sec_s))
    if shadow.regulated:
        story.append(_make_table([
            ["項目", "内容"],
            ["測定面高さ", f"{shadow.measurement_height_m} m"],
            ["規制トリガー", shadow.trigger],
            ["5m ラインの制限時間", f"{shadow.limit_5m} 時間"],
            ["10m ラインの制限時間", f"{shadow.limit_10m} 時間"],
        ], font, [70*mm, 100*mm]))
    else:
        story.append(Paragraph(shadow.notes[0] if shadow.notes else "対象外", body_s))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("6. 隣地境界距離（民法第234条）", sec_s))
    story.append(Paragraph(
        f"必要距離: {boundary['required_distance_m']} m 以上　根拠: {boundary['law_reference']}", body_s))
    story.append(Paragraph(f"※ {boundary['note']}", note_s))

    doc.build(story)
    return output_path
