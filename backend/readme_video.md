Método simples (com lista de arquivos)

Se os vídeos forem:

1.mp4
2.mp4
3.mp4

Crie o arquivo lista.txt:

printf "file '1.mp4'\nfile '2.mp4'\nfile '3.mp4'\n" > lista.txt

Depois junte os vídeos:

ffmpeg -f concat -safe 0 -i lista.txt -c:v libx264 -c:a aac -movflags +faststart video_final.mp4

Resultado:

video_final.mp4
2️⃣ Método automático (melhor)

Se os vídeos estão todos na pasta:

1.mp4
2.mp4
3.mp4

Use este comando:

for f in *.mp4; do echo "file '$f'"; done | sort -V > lista.txt
ffmpeg -f concat -safe 0 -i lista.txt -c:v libx264 -c:a aac -movflags +faststart video_final.mp4

Isso:

1️⃣ cria a lista automaticamente
2️⃣ junta todos os vídeos
3️⃣ gera um arquivo final.