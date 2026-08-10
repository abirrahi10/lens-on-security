const feedRows = document.querySelector('[data-feed-rows]');
const addFeed = document.querySelector('[data-add-feed]');

function renumberFeeds() {
  feedRows?.querySelectorAll('.feed-row').forEach((row, index) => {
    const legend = row.querySelector('legend');
    if (legend) legend.textContent = `Feed ${index + 1}`;
  });
}

addFeed?.addEventListener('click', () => {
  const firstRow = feedRows?.querySelector('.feed-row');
  if (!feedRows || !firstRow) return;
  const newRow = firstRow.cloneNode(true);
  newRow.querySelectorAll('input').forEach((input) => { input.value = ''; });
  newRow.querySelectorAll('select').forEach((select) => {
    select.value = select.name === 'feed_status' ? 'public' : '';
  });
  feedRows.append(newRow);
  renumberFeeds();
  newRow.querySelector('input')?.focus();
});

feedRows?.addEventListener('click', (event) => {
  const removeButton = event.target.closest('[data-remove-feed]');
  if (!removeButton) return;
  const rows = feedRows.querySelectorAll('.feed-row');
  if (rows.length === 1) {
    rows[0].querySelectorAll('input').forEach((input) => { input.value = ''; });
    rows[0].querySelectorAll('select').forEach((select) => {
      select.value = select.name === 'feed_status' ? 'public' : '';
    });
  } else {
    removeButton.closest('.feed-row')?.remove();
  }
  renumberFeeds();
});
