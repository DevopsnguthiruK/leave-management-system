# Leave Management System

## 📦 Requirements
- Python 3.11
- Flask
- wkhtmltopdf (for PDF generation)

## 🚀 Render Deployment

This project uses `wkhtmltopdf` for generating PDFs with `pdfkit`. To install `wkhtmltopdf` during deployment:

1. Ensure the `render-build.sh` script is present and executable.
2. Add this line in your Render build settings:
   ```bash
   ./render-build.sh
