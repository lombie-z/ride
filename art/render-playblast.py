"""Low-res preview of the journey for the camera-path gate: JourneyCam, every other frame, RGBA PNGs.
blender -b art/micro-biome.blend -P art/render-playblast.py -- <out_dir>   then composite onto plaster with ffmpeg."""
import sys

import bpy

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
scene.camera = bpy.data.objects['JourneyCam']
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 8
scene.render.film_transparent = True
scene.render.resolution_x, scene.render.resolution_y = 640, 360
scene.render.resolution_percentage = 100
scene.frame_step = 2
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = out.rstrip('/') + '/f'
bpy.ops.render.render(animation=True)
