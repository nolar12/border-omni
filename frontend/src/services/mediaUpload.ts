import api from './api';

export interface UploadedMedia {
  url: string;
  name: string;
  mime: string;
}

export const mediaUploadService = {
  async upload(file: File): Promise<UploadedMedia> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<UploadedMedia>('/upload-media/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};
