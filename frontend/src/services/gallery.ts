import api from './api';

export interface GalleryMedia {
  id: number;
  name: string;
  description: string;
  file_url: string;
  mime_type: string;
  media_type: 'IMAGE' | 'VIDEO' | 'DOCUMENT' | 'AUDIO';
  size_bytes: number;
  created_at: string;
}

export const galleryService = {
  list: (mediaType?: 'IMAGE' | 'VIDEO' | 'DOCUMENT' | 'AUDIO'): Promise<GalleryMedia[]> => {
    const params = mediaType ? { media_type: mediaType } : {};
    return api
      .get<GalleryMedia[] | { results: GalleryMedia[] }>('/gallery/', { params })
      .then(r => Array.isArray(r.data) ? r.data : r.data.results);
  },

  upload: (file: File, name?: string, description?: string): Promise<GalleryMedia> => {
    const form = new FormData();
    form.append('file', file);
    if (name) form.append('name', name);
    if (description) form.append('description', description);
    return api.post<GalleryMedia>('/gallery/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  update: (id: number, data: { name?: string; description?: string }): Promise<GalleryMedia> =>
    api.patch<GalleryMedia>(`/gallery/${id}/`, data).then(r => r.data),

  remove: (id: number): Promise<void> =>
    api.delete(`/gallery/${id}/`).then(() => undefined),
};
