"""Excel (.xlsx) lead exporter using openpyxl with professional styling."""

from pathlib import Path
from typing import Any
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from lid.exporter.csv_exporter import EXPORT_COLUMNS, build_row_dict


class ExcelLeadExporter:
    def export(self, leads: list[dict[str, Any]], output_path: Path | str) -> Path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Qualified Leads"

        # Styles
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        regular_font = Font(name="Segoe UI", size=9)
        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0"),
        )
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

        # Write Header
        ws.row_dimensions[1].height = 28
        for col_idx, col_name in enumerate(EXPORT_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border

        # Write Data Rows
        for row_idx, lead in enumerate(leads, start=2):
            ws.row_dimensions[row_idx].height = 24
            row_data = build_row_dict(lead)
            for col_idx, col_name in enumerate(EXPORT_COLUMNS, start=1):
                val = row_data.get(col_name, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = regular_font
                cell.border = thin_border
                
                # Alignments based on column
                if col_name in ("Qualification score", "Signal date", "Research date", "Human review status", "Verification status"):
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                # Limit length calculation to avoid overly wide columns
                line_len = max([len(line) for line in val.split("\n")]) if val else 0
                if line_len > max_len:
                    max_len = line_len
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

        wb.save(out_file)
        return out_file
