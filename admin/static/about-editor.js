const cropper = document.querySelector('[data-portrait-cropper]');
const canvas = cropper?.querySelector('canvas');
const context = canvas?.getContext('2d');
const fileInput = document.querySelector('[data-portrait-file]');
const zoomInput = document.querySelector('[data-crop-zoom]');
const focalXInput = document.querySelector('[data-crop-x]');
const focalYInput = document.querySelector('[data-crop-y]');
const zoomValueInput = document.querySelector('[data-crop-zoom-value]');

if (cropper && canvas && context && zoomInput && focalXInput && focalYInput && zoomValueInput) {
  const state = {
    image: new Image(),
    focalX: 0.5,
    focalY: 0.5,
    zoom: 1,
    dragging: false,
    startPointerX: 0,
    startPointerY: 0,
    startFocalX: 0.5,
    startFocalY: 0.5,
    objectUrl: null,
  };

  const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

  function sourceCrop() {
    const imageRatio = state.image.naturalWidth / state.image.naturalHeight;
    const targetRatio = canvas.width / canvas.height;
    let baseWidth;
    let baseHeight;
    if (imageRatio > targetRatio) {
      baseHeight = state.image.naturalHeight;
      baseWidth = baseHeight * targetRatio;
    } else {
      baseWidth = state.image.naturalWidth;
      baseHeight = baseWidth / targetRatio;
    }
    const width = baseWidth / state.zoom;
    const height = baseHeight / state.zoom;
    const centerX = clamp(state.focalX * state.image.naturalWidth, width / 2, state.image.naturalWidth - width / 2);
    const centerY = clamp(state.focalY * state.image.naturalHeight, height / 2, state.image.naturalHeight - height / 2);
    return { x: centerX - width / 2, y: centerY - height / 2, width, height };
  }

  function render() {
    if (!state.image.complete || !state.image.naturalWidth) return;
    const crop = sourceCrop();
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(state.image, crop.x, crop.y, crop.width, crop.height, 0, 0, canvas.width, canvas.height);
    focalXInput.value = state.focalX.toFixed(5);
    focalYInput.value = state.focalY.toFixed(5);
    zoomValueInput.value = state.zoom.toFixed(2);
  }

  function loadImage(source, reset = true) {
    state.image.onload = () => {
      if (reset) {
        state.focalX = 0.5;
        state.focalY = 0.5;
        state.zoom = 1;
        zoomInput.value = '1';
      }
      render();
    };
    state.image.src = source;
  }

  loadImage(cropper.dataset.currentImage, true);

  fileInput?.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
    state.objectUrl = URL.createObjectURL(file);
    loadImage(state.objectUrl, true);
  });

  zoomInput.addEventListener('input', () => {
    state.zoom = Number(zoomInput.value);
    render();
  });

  canvas.addEventListener('pointerdown', (event) => {
    if (!state.image.naturalWidth) return;
    state.dragging = true;
    state.startPointerX = event.clientX;
    state.startPointerY = event.clientY;
    state.startFocalX = state.focalX;
    state.startFocalY = state.focalY;
    canvas.setPointerCapture(event.pointerId);
    canvas.classList.add('dragging');
  });

  canvas.addEventListener('pointermove', (event) => {
    if (!state.dragging) return;
    const crop = sourceCrop();
    const deltaX = event.clientX - state.startPointerX;
    const deltaY = event.clientY - state.startPointerY;
    state.focalX = clamp(state.startFocalX - (deltaX / canvas.clientWidth) * (crop.width / state.image.naturalWidth), 0, 1);
    state.focalY = clamp(state.startFocalY - (deltaY / canvas.clientHeight) * (crop.height / state.image.naturalHeight), 0, 1);
    render();
  });

  const finishDrag = (event) => {
    if (!state.dragging) return;
    state.dragging = false;
    canvas.classList.remove('dragging');
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  };
  canvas.addEventListener('pointerup', finishDrag);
  canvas.addEventListener('pointercancel', finishDrag);
}

const profileLinkRows = document.querySelector('[data-profile-link-rows]');
const addProfileLink = document.querySelector('[data-add-profile-link]');

addProfileLink?.addEventListener('click', () => {
  const firstRow = profileLinkRows?.querySelector('.profile-link-row');
  if (!profileLinkRows || !firstRow) return;
  const newRow = firstRow.cloneNode(true);
  newRow.querySelectorAll('input').forEach((input) => {
    input.value = '';
  });
  profileLinkRows.append(newRow);
  newRow.querySelector('input')?.focus();
});

profileLinkRows?.addEventListener('click', (event) => {
  const removeButton = event.target.closest('[data-remove-profile-link]');
  if (!removeButton) return;
  removeButton.closest('.profile-link-row')?.remove();
});
