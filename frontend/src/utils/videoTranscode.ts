// Converte vídeos HEVC (H.265) para H.264 no navegador, antes do upload.
// Celulares gravam em HEVC e tocam normalmente, mas Chrome/Firefox de desktop não decodificam,
// então o site público mostraria o vídeo quebrado. O servidor (0,5 vCPU) não aguenta converter.

const CORE_BASE = 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/esm';
const SCAN_BYTES = 4 * 1024 * 1024;

const decoder = new TextDecoder('latin1');

/** Procura os identificadores de codec no início e no fim do arquivo (onde fica o `moov`). */
export async function isHevcVideo(file: File): Promise<boolean> {
  const head = file.slice(0, SCAN_BYTES);
  const tail = file.size > SCAN_BYTES ? file.slice(-SCAN_BYTES) : null;
  for (const part of [head, tail]) {
    if (!part) continue;
    const text = decoder.decode(await part.arrayBuffer());
    if (/hvc1|hev1|hvcC/.test(text)) return true;
  }
  return false;
}

export async function transcodeToH264(file: File, onProgress: (pct: number) => void): Promise<File> {
  const [{ FFmpeg }, { fetchFile, toBlobURL }] = await Promise.all([
    import('@ffmpeg/ffmpeg'),
    import('@ffmpeg/util'),
  ]);

  const ffmpeg = new FFmpeg();
  ffmpeg.on('progress', ({ progress }) => {
    if (progress >= 0 && progress <= 1) onProgress(Math.round(progress * 100));
  });
  await ffmpeg.load({
    coreURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.js`, 'text/javascript'),
    wasmURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.wasm`, 'application/wasm'),
  });

  const input = 'input' + (file.name.match(/\.[^.]+$/)?.[0] ?? '.mp4');
  try {
    await ffmpeg.writeFile(input, await fetchFile(file));
    const code = await ffmpeg.exec([
      '-i', input,
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '27',
      '-vf', "scale='min(1280,iw)':-2",
      '-pix_fmt', 'yuv420p',
      '-c:a', 'aac', '-b:a', '128k',
      '-movflags', '+faststart',
      'output.mp4',
    ]);
    if (code !== 0) throw new Error(`ffmpeg saiu com código ${code}`);
    const data = await ffmpeg.readFile('output.mp4');
    const bytes = data as Uint8Array;
    const name = file.name.replace(/\.[^.]+$/, '') + '.mp4';
    return new File([bytes.slice()], name, { type: 'video/mp4' });
  } finally {
    ffmpeg.terminate();
  }
}
