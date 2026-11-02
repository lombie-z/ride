#!/bin/sh
# Adds the sticker outline (white band + thin dark rim, as in components/three/silhouette-outline.tsx)
# to the fallback still, using the letter-free mask from export-micro-biome.py. Far-side ring letters go under
# the band, everything else over it. Writes micro-biome.webp.
set -e
cd "$(dirname "$0")/../public/images/3d"
# The still is 1200px for a ~640px stage, so ~1.9 render px per CSS px: 12px band, 2.5px rim.
magick micro-biome-mask.png -alpha extract -morphology Dilate Disk:23 -blur 0x1 band.png
magick micro-biome-mask.png -alpha extract -morphology Dilate Disk:28 -blur 0x1 rim.png
magick -size 1200x1200 xc:'#2f2a27' rim.png -alpha off -compose CopyOpacity -composite rim-layer.png
magick -size 1200x1200 xc:white band.png -alpha off -compose CopyOpacity -composite band-layer.png
magick micro-biome-back.png rim-layer.png -compose Over -composite band-layer.png -compose Over -composite micro-biome.png -compose Over -composite \
  -resize 1000x1000 -quality 84 -define webp:alpha-quality=90 micro-biome.webp
rm band.png rim.png rim-layer.png band-layer.png micro-biome.png micro-biome-mask.png micro-biome-back.png
