const titleInput = document.querySelector('[data-title]');
const slugInput = document.querySelector('[data-slug]');
let slugWasEdited = Boolean(slugInput?.value);

slugInput?.addEventListener('input', () => {
  slugWasEdited = true;
});

titleInput?.addEventListener('input', () => {
  if (!slugInput || slugWasEdited) return;
  slugInput.value = titleInput.value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
});

const uploads = document.querySelector('#image-uploads');
document.querySelector('#add-image')?.addEventListener('click', () => {
  const first = uploads?.querySelector('.image-upload');
  if (!uploads || !first) return;
  const copy = first.cloneNode(true);
  copy.querySelectorAll('input, textarea').forEach((field) => {
    field.value = '';
  });
  uploads.append(copy);
});

const richEditor = document.querySelector('[data-rich-editor]');
const bodyEditor = richEditor?.querySelector('[data-body-editor]');
const previewPane = richEditor?.querySelector('[data-rich-preview]');
const csrfToken = document.querySelector('input[name="csrf_token"]');
let previewTimer;
let previewRequest;

function emitEditorInput() {
  bodyEditor?.dispatchEvent(new Event('input', { bubbles: true }));
}

function replaceSelection(before, after, placeholder) {
  if (!bodyEditor) return;
  const start = bodyEditor.selectionStart;
  const end = bodyEditor.selectionEnd;
  const selected = bodyEditor.value.slice(start, end) || placeholder;
  const replacement = `${before}${selected}${after}`;
  bodyEditor.setRangeText(replacement, start, end, 'end');
  bodyEditor.focus();
  bodyEditor.setSelectionRange(start + before.length, start + before.length + selected.length);
  emitEditorInput();
}

function formatSelectedLines(formatLine, placeholder) {
  if (!bodyEditor) return;
  const selectionStart = bodyEditor.selectionStart;
  const selectionEnd = bodyEditor.selectionEnd;
  const lineStart = bodyEditor.value.lastIndexOf('\n', Math.max(0, selectionStart - 1)) + 1;
  const nextBreak = bodyEditor.value.indexOf('\n', selectionEnd);
  const lineEnd = nextBreak === -1 ? bodyEditor.value.length : nextBreak;
  const current = bodyEditor.value.slice(lineStart, lineEnd) || placeholder;
  const formatted = current.split('\n').map(formatLine).join('\n');
  bodyEditor.setRangeText(formatted, lineStart, lineEnd, 'end');
  bodyEditor.focus();
  bodyEditor.setSelectionRange(lineStart, lineStart + formatted.length);
  emitEditorInput();
}

function insertDivider() {
  if (!bodyEditor) return;
  const position = bodyEditor.selectionStart;
  const prefix = position > 0 && !bodyEditor.value.slice(0, position).endsWith('\n\n') ? '\n\n' : '';
  const suffix = bodyEditor.value.slice(position).startsWith('\n\n') ? '' : '\n\n';
  const divider = `${prefix}---${suffix}`;
  bodyEditor.setRangeText(divider, position, bodyEditor.selectionEnd, 'end');
  bodyEditor.focus();
  emitEditorInput();
}

function insertLink() {
  if (!bodyEditor) return;
  const start = bodyEditor.selectionStart;
  const end = bodyEditor.selectionEnd;
  const label = bodyEditor.value.slice(start, end) || 'link text';
  const url = 'https://example.com';
  const replacement = `[${label}](${url})`;
  bodyEditor.setRangeText(replacement, start, end, 'end');
  const urlStart = start + label.length + 3;
  bodyEditor.focus();
  bodyEditor.setSelectionRange(urlStart, urlStart + url.length);
  emitEditorInput();
}

function applyFormat(format) {
  const actions = {
    heading2: () => formatSelectedLines((line) => `## ${line.replace(/^#{1,6}\s+/, '')}`, 'Section heading'),
    heading3: () => formatSelectedLines((line) => `### ${line.replace(/^#{1,6}\s+/, '')}`, 'Subheading'),
    bold: () => replaceSelection('**', '**', 'bold text'),
    italic: () => replaceSelection('*', '*', 'italic text'),
    quote: () => formatSelectedLines((line) => `> ${line.replace(/^>\s?/, '')}`, 'Quotation'),
    'unordered-list': () => formatSelectedLines((line) => `- ${line.replace(/^[-*+]\s+/, '')}`, 'List item'),
    'ordered-list': () => {
      let index = 0;
      formatSelectedLines((line) => `${++index}. ${line.replace(/^\d+\.\s+/, '')}`, 'List item');
    },
    link: insertLink,
    code: () => replaceSelection('`', '`', 'code'),
    divider: insertDivider,
    highlight: () => replaceSelection('<mark>', '</mark>', 'highlighted text'),
  };
  actions[format]?.();
}

function setEditorView(view) {
  if (!richEditor || !['write', 'split', 'preview'].includes(view)) return;
  richEditor.dataset.view = view;
  richEditor.querySelectorAll('[data-editor-view]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.editorView === view));
  });
  if (view !== 'write') schedulePreview(0);
}

async function updatePreview() {
  if (!richEditor || !bodyEditor || !previewPane || !csrfToken) return;
  if (!bodyEditor.value.trim()) {
    previewPane.innerHTML = '<p class="preview-placeholder">Your formatted article will appear here.</p>';
    return;
  }
  previewRequest?.abort();
  const currentRequest = new AbortController();
  previewRequest = currentRequest;
  const form = new URLSearchParams({ csrf_token: csrfToken.value, body: bodyEditor.value });
  previewPane.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(richEditor.dataset.previewUrl, {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      signal: currentRequest.signal,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    });
    if (!response.ok) throw new Error('Preview unavailable');
    previewPane.innerHTML = await response.text();
  } catch (error) {
    if (error.name !== 'AbortError') {
      previewPane.innerHTML = '<p class="preview-placeholder">Preview could not load. Your draft is still safe.</p>';
    }
  } finally {
    if (previewRequest === currentRequest) previewPane.removeAttribute('aria-busy');
  }
}

function schedulePreview(delay = 320) {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(updatePreview, delay);
}

richEditor?.querySelectorAll('[data-format]').forEach((button) => {
  button.addEventListener('click', () => applyFormat(button.dataset.format));
});

richEditor?.querySelector('[data-text-color]')?.addEventListener('change', (event) => {
  if (!event.target.value) return;
  replaceSelection(`<span class="${event.target.value}">`, '</span>', 'colored text');
  event.target.value = '';
});

richEditor?.querySelectorAll('[data-editor-view]').forEach((button) => {
  button.addEventListener('click', () => setEditorView(button.dataset.editorView));
});

bodyEditor?.addEventListener('keydown', (event) => {
  if (!(event.ctrlKey || event.metaKey)) return;
  const shortcut = event.key.toLowerCase();
  if (!['b', 'i', 'k'].includes(shortcut)) return;
  event.preventDefault();
  applyFormat({ b: 'bold', i: 'italic', k: 'link' }[shortcut]);
});

bodyEditor?.addEventListener('input', () => schedulePreview());

if (richEditor) {
  setEditorView(window.matchMedia('(max-width: 720px)').matches ? 'write' : 'split');
  schedulePreview(0);
}
