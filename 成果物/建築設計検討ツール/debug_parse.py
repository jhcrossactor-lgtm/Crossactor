import sys, json
sys.path.insert(0, '.')
from core.pdf_parser import parse_site_pdf

result = parse_site_pdf(r'C:\Users\hosokawa\Desktop\旭区高殿2丁目_merged.pdf')
print(json.dumps(result, ensure_ascii=False, indent=2))
