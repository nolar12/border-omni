import { useEffect, useState } from 'react';

interface Props {
  src: string;
  className?: string;
  /** Time in seconds to seek to. Defaults to 1s (or 25% of duration if shorter). */
  seekTo?: number;
}

/**
 * Renders a thumbnail for a video by capturing a frame via canvas.
 * Falls back to a play-icon placeholder while loading or on error.
 */
export default function VideoThumbnail({ src, className = '', seekTo }: Props) {
  const [thumb, setThumb] = useState<string | null>(null);

  useEffect(() => {
    if (!src) return;
    let revoked = false;

    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.muted = true;
    video.preload = 'metadata';
    video.src = src;

    const capture = () => {
      if (revoked) return;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 320;
      canvas.height = video.videoHeight || 180;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      try {
        setThumb(canvas.toDataURL('image/jpeg', 0.75));
      } catch {
        // CORS / codec issue — keep placeholder
      }
      video.src = '';
    };

    video.addEventListener('loadedmetadata', () => {
      const target = seekTo !== undefined
        ? Math.min(seekTo, video.duration)
        : video.duration * 0.5;
      video.currentTime = target;
    });
    video.addEventListener('seeked', capture, { once: true });
    video.addEventListener('error', () => { video.src = ''; });

    return () => {
      revoked = true;
      video.src = '';
    };
  }, [src, seekTo]);

  if (!thumb) {
    return (
      <div className={`w-full h-full flex flex-col items-center justify-center gap-1.5 bg-gradient-to-br from-slate-700 to-slate-900 ${className}`}>
        <svg className="w-8 h-8 text-white/60 animate-pulse" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z"/>
        </svg>
      </div>
    );
  }

  return (
    <div className={`relative w-full h-full ${className}`}>
      <img src={thumb} alt="" className="w-full h-full object-cover" />
      <div className="absolute inset-0 flex items-center justify-center bg-black/20 hover:bg-black/30 transition-colors">
        <div className="w-8 h-8 rounded-full bg-black/50 flex items-center justify-center">
          <svg className="w-4 h-4 text-white ml-0.5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
          </svg>
        </div>
      </div>
    </div>
  );
}
