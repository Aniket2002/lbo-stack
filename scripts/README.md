# Scripts Directory

This directory contains utility scripts for generating reports, analysis, and validation.

## PDF Generation Scripts
- `generate_final_pdf.py` - Main PDF generation script
- `generate_final_analysis.py` - Complete analysis with PDF output
- `generate_latest_pdf.py` - Latest version PDF generator
- `generate_internal_memo_pdf.py` - Internal memo format
- `generate_pe_vp_pdf.py` - PE VP specific format
- `generate_pdf_with_fixes.py` - PDF with applied fixes
- `create_latest_pdf.py` - Create latest PDF version

## Analysis & Validation
- `compare_models.py` - Model comparison utilities
- `final_validation.py` - Final validation checks

## Usage
Run scripts from the project root directory:
```bash
python scripts/generate_final_pdf.py
python scripts/final_validation.py
```

## Note
These scripts generate output to the `output/` directory to keep the root clean.
