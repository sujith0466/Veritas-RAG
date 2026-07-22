const fs = require('fs');
const path = require('path');

const map = {
  'slate-50': 'surface',
  'slate-100': 'foreground',
  'slate-200': 'foreground',
  'slate-300': 'foreground',
  'slate-400': 'muted-foreground',
  'slate-500': 'muted-foreground',
  'slate-600': 'muted-foreground',
  'slate-700': 'border',
  'slate-800': 'border',
  'slate-900': 'surface',
  'slate-950': 'background',
};

const mapRegex = new RegExp('([a-z]+-)?slate-(\\d+)(\\/\\d+)?', 'g');

function processFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;
  
  content = content.replace(mapRegex, (match, prefix, num, opacity) => {
    changed = true;
    const replacement = map['slate-' + num] || 'muted-foreground';
    let res = prefix ? prefix + replacement : replacement;
    // We can map bg-slate-900 -> bg-surface, text-slate-100 -> text-foreground
    return res + (opacity ? opacity : '');
  });

  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log('Processed', filePath);
  }
}

function walk(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const full = path.join(dir, file);
    if (fs.statSync(full).isDirectory()) {
      walk(full);
    } else if (full.endsWith('.tsx') || full.endsWith('.ts')) {
      processFile(full);
    }
  }
}

walk(path.join(__dirname, 'src'));
