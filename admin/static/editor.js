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
