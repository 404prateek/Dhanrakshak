import { api } from './api';

const controllers = {};
const statuses = {};
const listeners = new Set();

function emit(fileId) {
  const payload = { fileId, status: statuses[fileId] };
  for (const l of listeners) l(payload);
}

export function subscribe(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export async function startUploads(caseId, files = []) {
  for (const f of files) {
    // skip already uploaded
    if (statuses[f.id]?.uploaded) continue;
    const controller = new AbortController();
    controllers[f.id] = controller;
    statuses[f.id] = { progress: 0, uploading: true, uploaded: false, error: false, name: f.name };
    emit(f.id);

    // fire-and-forget
    api.uploadDocument(caseId, f.file, (pct) => {
      statuses[f.id].progress = pct;
      emit(f.id);
    }, controller.signal).then(() => {
      statuses[f.id].uploaded = true;
      statuses[f.id].uploading = false;
      statuses[f.id].progress = 100;
      delete controllers[f.id];
      emit(f.id);
    }).catch((err) => {
      if (controller.signal.aborted) {
        statuses[f.id].error = true;
        statuses[f.id].uploading = false;
      } else {
        statuses[f.id].error = true;
        statuses[f.id].uploading = false;
      }
      delete controllers[f.id];
      emit(f.id);
    });
  }
}

export function cancelUpload(fileId) {
  const c = controllers[fileId];
  if (c) {
    try { c.abort(); } catch (e) { }
    delete controllers[fileId];
  }
  if (statuses[fileId]) {
    statuses[fileId].uploading = false;
    statuses[fileId].error = true;
    emit(fileId);
  }
}

export function retryUpload(caseId, fileObj) {
  // start a fresh upload for this single file
  if (!fileObj) return;
  return startUploads(caseId, [fileObj]);
}

export function getStatus(fileId) {
  return statuses[fileId];
}

export function getAllStatuses() {
  return { ...statuses };
}

export default {
  startUploads,
  cancelUpload,
  retryUpload,
  subscribe,
  getStatus,
  getAllStatuses,
};
