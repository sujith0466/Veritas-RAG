import os, json, random
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

DEPARTMENTS = [
    'hr', 'engineering', 'it', 'security', 'product', 
    'finance', 'legal', 'customer_support', 'sales', 'marketing'
]

FORMATS = {'md': 0.25, 'docx': 0.15, 'pdf': 0.15, 'txt': 0.10, 'html': 0.05, 'json': 0.05, 'yaml': 0.05, 'csv': 0.05, 'xml': 0.05, 'py': 0.05, 'js': 0.05}

def get_format():
    fmt = random.choices(list(FORMATS.keys()), weights=list(FORMATS.values()), k=1)[0]
    if fmt == 'docx' and not HAS_DOCX: return 'md'
    if fmt == 'pdf' and not HAS_REPORTLAB: return 'md'
    return fmt

out_dir = '/app/enterprise_demo_dataset'
os.makedirs(out_dir, exist_ok=True)
for d in DEPARTMENTS: os.makedirs(os.path.join(out_dir, d), exist_ok=True)

for i in range(120):
    dept = random.choice(DEPARTMENTS)
    fmt = get_format()
    title = fake.catch_phrase()
    slug = title.lower().replace(' ', '_').replace('/', '_')[:30] + '_' + str(i)
    path = os.path.join(out_dir, dept, f'{slug}.{fmt}')
    
    paragraphs = [title] + [fake.paragraph(nb_sentences=random.randint(5, 15)) for _ in range(random.randint(4, 10))]
    
    if fmt == 'pdf':
        doc = SimpleDocTemplate(path, pagesize=letter)
        story = [Paragraph(title, getSampleStyleSheet()['Heading1'])]
        for p in paragraphs[1:]:
            story.append(Paragraph(p, getSampleStyleSheet()['Normal']))
            story.append(Spacer(1, 10))
        doc.build(story)
    elif fmt == 'docx':
        doc = Document()
        doc.add_heading(title, 0)
        for p in paragraphs[1:]: doc.add_paragraph(p)
        doc.save(path)
    elif fmt == 'json':
        with open(path, 'w') as f: json.dump({'title': title, 'content': paragraphs[1:]}, f)
    elif fmt == 'yaml':
        with open(path, 'w') as f: f.write(f'title: {title}\ncontent:\n' + '\n'.join([f'  - {p}' for p in paragraphs[1:]]))
    elif fmt == 'csv':
        with open(path, 'w') as f: f.write('ID,Content\n' + '\n'.join([f'{i},{p}' for i, p in enumerate(paragraphs[1:])]))
    elif fmt == 'xml':
        with open(path, 'w', encoding='utf-8') as f: f.write(f'<document><title>{title}</title><content>' + ''.join([f'<p>{p}</p>' for p in paragraphs[1:]]) + '</content></document>')
    elif fmt == 'html':
        with open(path, 'w', encoding='utf-8') as f: f.write(f'<html><head><title>{title}</title></head><body><h1>{title}</h1>' + ''.join([f'<p>{p}</p>' for p in paragraphs[1:]]) + '</body></html>')
    elif fmt == 'py':
        with open(path, 'w', encoding='utf-8') as f: f.write(f'\"\"\"{title}\"\"\"\n\ndef get_data():\n' + '\n'.join([f'    # {p}' for p in paragraphs[1:]]) + '\n    return True')
    elif fmt == 'js':
        with open(path, 'w', encoding='utf-8') as f: f.write(f'/* {title} */\n\nfunction getData() {{\n' + '\n'.join([f'    // {p}' for p in paragraphs[1:]]) + '\n    return true;\n}')
    else:
        with open(path, 'w', encoding='utf-8') as f: f.write('\n\n'.join(paragraphs))

print('Generated 120 files in enterprise_demo_dataset/')
